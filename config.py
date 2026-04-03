import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    PROJECT_ID: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT_ID", "YOUR_PROJECT_ID")
    )
    LOCATION: str = field(
        default_factory=lambda: os.getenv("GOOGLE_CLOUD_LOCATION", "us")
    )
    OCR_PROCESSOR_ID: str = field(
        default_factory=lambda: os.getenv("OCR_PROCESSOR_ID", "YOUR_OCR_PROCESSOR_ID")
    )
    FORM_PARSER_PROCESSOR_ID: str = field(
        default_factory=lambda: os.getenv("FORM_PARSER_PROCESSOR_ID", "YOUR_FORM_PARSER_ID")
    )
    SERVICE_ACCOUNT_KEY_PATH: str = field(
        default_factory=lambda: os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", "path/to/service-account-key.json"
        )
    )

    @property
    def is_configured(self) -> bool:
        return (
            self.PROJECT_ID not in ("YOUR_PROJECT_ID", "", None)
            and self.OCR_PROCESSOR_ID not in ("YOUR_OCR_PROCESSOR_ID", "", None)
            and os.path.exists(self.SERVICE_ACCOUNT_KEY_PATH)
        )

    @property
    def ocr_processor_name(self) -> str:
        return (
            f"projects/{self.PROJECT_ID}"
            f"/locations/{self.LOCATION}"
            f"/processors/{self.OCR_PROCESSOR_ID}"
        )

    @property
    def form_parser_processor_name(self) -> str:
        return (
            f"projects/{self.PROJECT_ID}"
            f"/locations/{self.LOCATION}"
            f"/processors/{self.FORM_PARSER_PROCESSOR_ID}"
        )


config = Config()
