from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ROOT_ENV_FILE = PROJECT_ROOT / ".env"
BACKEND_ENV_FILE = PROJECT_ROOT / "backend" / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(ROOT_ENV_FILE), str(BACKEND_ENV_FILE), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = Field(
        default="", description="Azure AI Document Intelligence Endpoint"
    )
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = Field(
        default="", description="Azure AI Document Intelligence Key"
    )
    AZURE_API_VERSION: str = Field(
        default="2024-11-30", description="Azure Document Intelligence API version"
    )
    ACADEMIC_TERM_START: str = Field(
        default="2026-08-01", description="Academic term start date YYYY-MM-DD"
    )
    ACADEMIC_TERM_END: str = Field(
        default="2026-12-31", description="Academic term end date YYYY-MM-DD"
    )
    CONFIDENCE_THRESHOLD: float = Field(
        default=0.85, description="Confidence threshold for low-confidence warnings"
    )
    DATABASE_URL: str = Field(
        default="sqlite:///./fee_auditor.db", description="SQLite database URL"
    )
    BACKEND_PORT: int = Field(default=8000, description="FastAPI server port")

    # Security configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated list of allowed CORS origins",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=20,
        description="Maximum upload size per file in megabytes",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Return list of allowed CORS origins stripped of whitespace."""
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        """Return maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def canonical_azure_endpoint(self) -> str:
        """Return normalized Azure Document Intelligence endpoint with trailing slashes removed."""
        return self.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT.strip().rstrip("/")


settings = Settings()
