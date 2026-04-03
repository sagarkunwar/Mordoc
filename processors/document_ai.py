"""
Google Document AI integration.

Sends PDFs to the OCR processor, extracts per-page text, TFNs, and person names.
Bounding box data is captured at token level so Prompt 2 redaction can use it
without re-processing documents.
"""
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional

from config import config
from processors.tfn_validator import TFNMatch, BoundingBox, extract_tfns_from_text
from processors.name_extractor import extract_names_from_text, extract_names_from_entities


@dataclass
class PageResult:
    page_number: int
    text: str
    tfns: List[TFNMatch] = field(default_factory=list)
    char_count: int = 0


@dataclass
class DocumentResult:
    filename: str
    total_pages: int
    pages: List[PageResult] = field(default_factory=list)
    all_tfns: List[TFNMatch] = field(default_factory=list)
    names: List[str] = field(default_factory=list)
    status: str = "processed"   # "processed" | "error"
    error: Optional[str] = None
    file_size_bytes: int = 0
    raw_document: Optional[Any] = None  # google Document object (used by Prompt 2)


# ── helpers ──────────────────────────────────────────────────────────────────

def _layout_to_text(layout, full_text: str) -> str:
    """Extract the text segment referenced by a Document AI layout object."""
    if not layout or not layout.text_anchor or not layout.text_anchor.text_segments:
        return ""
    result = ""
    for seg in layout.text_anchor.text_segments:
        start = int(seg.start_index) if seg.start_index else 0
        end = int(seg.end_index) if seg.end_index else len(full_text)
        result += full_text[start:end]
    return result


def _normalized_box_to_bbox(vertices, page_num: int) -> Optional[BoundingBox]:
    """Convert Document AI normalized_vertices to a BoundingBox."""
    if not vertices or len(vertices) < 2:
        return None
    xs = [v.x for v in vertices]
    ys = [v.y for v in vertices]
    x = min(xs)
    y = min(ys)
    return BoundingBox(
        x=x,
        y=y,
        width=max(xs) - x,
        height=max(ys) - y,
        page=page_num,
    )


def _attach_bounding_boxes(tfn_matches: List[TFNMatch], page, full_text: str) -> None:
    """
    For each TFN match on this page, scan the page tokens to find which tokens
    make up the TFN and attach their bounding boxes.
    This is used by Prompt 2 for precise redaction rectangles.
    """
    if not page.tokens or not tfn_matches:
        return

    # Build a list of (token_text, bounding_box) for this page
    token_spans = []
    for token in page.tokens:
        token_text = _layout_to_text(token.layout, full_text)
        if not token_text:
            continue
        bb = None
        if token.layout and token.layout.bounding_poly:
            bb = _normalized_box_to_bbox(
                token.layout.bounding_poly.normalized_vertices, page.page_number
            )
        token_spans.append((token_text.strip(), bb))

    # For each TFN, look for a run of tokens whose concatenated digits match
    for tfn in tfn_matches:
        target = tfn.normalized  # 9-digit string
        boxes: List[BoundingBox] = []

        for i, (tok_text, bb) in enumerate(token_spans):
            digits_in_tok = "".join(c for c in tok_text if c.isdigit())
            if not digits_in_tok:
                continue
            # Try to build the TFN from consecutive digit-containing tokens
            collected = digits_in_tok
            candidate_boxes = [bb] if bb else []
            for j in range(i + 1, min(i + 5, len(token_spans))):
                next_text, next_bb = token_spans[j]
                next_digits = "".join(c for c in next_text if c.isdigit())
                collected += next_digits
                if next_bb:
                    candidate_boxes.append(next_bb)
                if collected == target:
                    boxes = [b for b in candidate_boxes if b is not None]
                    break
                if len(collected) > 9:
                    break
            if collected == target and boxes:
                tfn.bounding_boxes = boxes
                break


# ── public API ───────────────────────────────────────────────────────────────

def _get_client():
    from google.cloud import documentai_v1 as documentai
    from google.api_core.client_options import ClientOptions

    key_path = config.SERVICE_ACCOUNT_KEY_PATH
    if key_path and key_path != "path/to/service-account-key.json":
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path

    opts = ClientOptions(api_endpoint=f"{config.LOCATION}-documentai.googleapis.com")
    return documentai.DocumentProcessorServiceClient(client_options=opts)


def process_document_with_ocr(
    pdf_bytes: bytes, filename: str, file_size: int = 0
) -> DocumentResult:
    """
    Send a PDF to the Document AI OCR processor.
    Returns a DocumentResult with per-page text, TFN matches, and person names.
    """
    if not config.is_configured:
        return DocumentResult(
            filename=filename,
            total_pages=0,
            status="error",
            error=(
                "Google Cloud credentials not configured. "
                "Copy .env.example to .env and fill in your project ID, "
                "processor IDs, and path to service account key."
            ),
            file_size_bytes=file_size,
        )

    try:
        from google.cloud import documentai_v1 as documentai

        client = _get_client()
        raw_doc = documentai.RawDocument(content=pdf_bytes, mime_type="application/pdf")
        request = documentai.ProcessRequest(
            name=config.ocr_processor_name,
            raw_document=raw_doc,
        )
        response = client.process_document(request=request)
        document = response.document
        full_text = document.text or ""

        pages: List[PageResult] = []
        all_tfns: List[TFNMatch] = []
        seen_tfns: set = set()

        for page in document.pages:
            page_num = page.page_number

            # Get page text from layout text anchor
            page_text = _layout_to_text(page.layout, full_text) if page.layout else ""

            # Fallback: concatenate block texts
            if not page_text.strip() and page.blocks:
                for block in page.blocks:
                    page_text += _layout_to_text(block.layout, full_text)

            # Extract and deduplicate TFNs
            raw_tfns = extract_tfns_from_text(page_text, page_num)
            page_tfns: List[TFNMatch] = []
            for tfn in raw_tfns:
                if tfn.normalized not in seen_tfns:
                    seen_tfns.add(tfn.normalized)
                    page_tfns.append(tfn)
                    all_tfns.append(tfn)

            # Attach bounding boxes for future redaction (Prompt 2)
            _attach_bounding_boxes(page_tfns, page, full_text)

            pages.append(PageResult(
                page_number=page_num,
                text=page_text,
                tfns=page_tfns,
                char_count=len(page_text),
            ))

        # Names: Document AI entities first, regex fallback
        names = extract_names_from_entities(document.entities)
        if not names:
            names = extract_names_from_text(full_text)

        # Deduplicate preserving order, cap at 20 to reduce noise
        seen_names: set = set()
        unique_names: List[str] = []
        for n in names:
            if n.lower() not in seen_names:
                seen_names.add(n.lower())
                unique_names.append(n)
        unique_names = unique_names[:20]

        return DocumentResult(
            filename=filename,
            total_pages=len(pages),
            pages=pages,
            all_tfns=all_tfns,
            names=unique_names,
            status="processed",
            file_size_bytes=file_size,
            raw_document=document,
        )

    except Exception as exc:
        return DocumentResult(
            filename=filename,
            total_pages=0,
            status="error",
            error=str(exc),
            file_size_bytes=file_size,
        )
