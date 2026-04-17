"""
Structured data extractor using OpenRouter LLM.

Sends OCR text + doc_type to an LLM and returns a typed JSON map
of the fields relevant to that document category.
"""
import json
import os
import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "openai/gpt-4o-mini"

# Per-doc-type field definitions: key → human description for the prompt
_FIELD_MAP = {
    "passport": {
        "full_name":       "Full name as printed on passport",
        "dob":             "Date of birth (YYYY-MM-DD)",
        "document_number": "Passport number",
        "expiry":          "Expiry date (YYYY-MM-DD)",
        "nationality":     "Nationality",
        "place_of_birth":  "Place of birth",
        "gender":          "Gender (M/F)",
        "document_date":   "Document issue/creation date (YYYY-MM-DD)",
    },
    "driver": {
        "name_on_card":   "Full name on licence",
        "address":        "Home address",
        "license_number": "Licence/card number",
        "dob":            "Date of birth (YYYY-MM-DD)",
        "expiry":         "Expiry date",
        "state":          "Issuing state/territory",
        "license_class":  "Licence class (e.g. C, R)",
        "document_date":  "Document issue/creation date (YYYY-MM-DD)",
    },
    "bank": {
        "account_holder":     "Account holder full name",
        "address":            "Account holder address",
        "account_number":     "Account number (mask middle digits, e.g. xxxx-4455)",
        "bsb":                "BSB number",
        "bank_name":          "Bank or institution name",
        "statement_period":   "Statement period (start date – end date)",
        "opening_balance":    "Opening balance",
        "closing_balance":    "Closing balance",
        "statement_end_date": "End date of statement period (YYYY-MM-DD)",
        "document_date":      "Document issue/creation date (YYYY-MM-DD)",
    },
    "tax return": {
        "full_name":     "Taxpayer full name",
        "address":       "Home address",
        "tax_year":      "Tax year (e.g. 2023-24)",
        "tfn":           "Tax File Number (mask as xxx-xxx-xxx)",
        "employer_name": "Primary employer name",
        "gross_income":  "Total gross income",
        "tax_withheld":  "Total tax withheld",
        "refund_amount": "Refund or amount payable",
        "document_date": "Document issue/creation date (YYYY-MM-DD)",
    },
    "payslip": {
        "full_name":      "Employee full name",
        "employer_name":  "Employer name",
        "employer_abn":   "Employer ABN",
        "pay_period":     "Pay period (start – end date)",
        "gross_pay":      "Gross pay this period",
        "net_pay":        "Net pay this period",
        "ytd_gross":      "Year to date gross earnings",
        "pay_period_end": "End date of pay period (YYYY-MM-DD)",
        "document_date":  "Document issue/creation date (YYYY-MM-DD)",
    },
    "birth certificate": {
        "full_name":           "Full name on certificate",
        "dob":                 "Date of birth (YYYY-MM-DD)",
        "place_of_birth":      "Place/hospital of birth",
        "registration_number": "Registration number",
        "parent_names":        "Parent(s) full name(s)",
        "issuing_state":       "Issuing state/territory",
        "document_date":       "Document issue/creation date (YYYY-MM-DD)",
    },
    "citizenship": {
        "full_name":         "Full name",
        "dob":               "Date of birth (YYYY-MM-DD)",
        "certificate_number":"Certificate number",
        "grant_date":        "Date citizenship was granted",
        "document_date":     "Document issue/creation date (YYYY-MM-DD)",
    },
    "medicare": {
        "card_holder":      "Primary card holder name",
        "medicare_number":  "Medicare card number (mask as xxxx-xxxxx-x)",
        "expiry":           "Card expiry (MM/YYYY)",
        "reference_number": "Individual reference number",
        "document_date":    "Document issue/creation date (YYYY-MM-DD)",
    },
    "centrelink": {
        "full_name":      "Full name",
        "crn":            "Centrelink Reference Number (CRN, masked)",
        "payment_type":   "Payment type (e.g. JobSeeker, Age Pension)",
        "payment_amount": "Payment amount",
        "period":         "Payment period",
        "document_date":  "Document issue/creation date (YYYY-MM-DD)",
    },
}


def _fields_for(doc_type: str) -> dict:
    """Return the best-matching field map for a given doc_type string."""
    doc_lower = doc_type.lower()
    for key, fields in _FIELD_MAP.items():
        if key in doc_lower:
            return fields
    # Generic fallback for unknown types
    return {
        "full_name":       "Full name found in the document",
        "document_number": "Any document or reference number",
        "date":            "Any significant date present",
        "address":         "Address if present",
        "issuer":          "Issuing organisation or authority",
        "document_date":   "Document issue/creation date (YYYY-MM-DD)",
    }


def extract_structured_data(full_text: str, doc_type: str, filename: str) -> dict:
    """
    Call OpenRouter LLM to extract structured fields from OCR text.

    Returns a dict with the extracted fields, or {"_error": msg} on failure.
    Returns {} if text is empty or API key is not set.
    """
    if not full_text or not full_text.strip():
        return {}

    api_key = OPENROUTER_API_KEY
    if not api_key:
        return {"_error": "OPENROUTER_API_KEY not set"}

    fields = _fields_for(doc_type)
    field_lines = "\n".join(f'  "{k}": <{desc}>' for k, desc in fields.items())

    system_prompt = (
        "You are a document data extraction assistant for Australian mortgage compliance. "
        "Extract only the fields listed. Return a single valid JSON object. "
        "Use null for missing fields. Never invent values. No markdown, no explanation."
    )

    user_prompt = (
        f"Document type: {doc_type}\n"
        f"Filename: {filename}\n\n"
        f"Extract these fields:\n{{\n{field_lines}\n}}\n\n"
        f"OCR text (first 4000 chars):\n{full_text[:4000]}"
    )

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://mortgagedoc.ai",
                "X-Title": "MortgageDoc AI",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 600,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()

        # Strip markdown fences if model wraps in ```json ... ```
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:].lstrip()

        return json.loads(content)

    except requests.exceptions.Timeout:
        return {"_error": "OpenRouter request timed out"}
    except requests.exceptions.HTTPError as e:
        return {"_error": f"OpenRouter HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except json.JSONDecodeError as e:
        return {"_error": f"LLM returned non-JSON: {str(e)}"}
    except Exception as e:
        return {"_error": str(e)}
