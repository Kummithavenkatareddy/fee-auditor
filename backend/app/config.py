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
        default="sqlite:///data/fee_auditor.db", description="Database connection URL (sqlite:///data/fee_auditor.db for local dev, or postgresql://... for production)"
    )
    BACKEND_PORT: int = Field(default=8000, description="FastAPI server port")

    # Environment and Demo Mode configuration
    ENVIRONMENT: str = Field(
        default="development", description="Environment: 'development', 'staging', or 'production'"
    )
    DEMO_MODE: bool = Field(
        default=True, description="Enable demo verification code generation when live delivery channels are unconfigured"
    )
    SMTP_CONFIGURED: bool = Field(
        default=False, description="Whether live institutional SMTP email delivery is configured"
    )
    SMS_CONFIGURED: bool = Field(
        default=False, description="Whether live SMS gateway delivery is configured"
    )

    # Azure Blob Storage for persistent document files
    AZURE_STORAGE_CONNECTION_STRING: str = Field(
        default="", description="Azure Blob Storage connection string for production document persistence"
    )
    AZURE_STORAGE_CONTAINER: str = Field(
        default="fee-auditor-documents", description="Azure Blob Storage container name"
    )

    # Security configuration
    CORS_ORIGINS: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://fee-auditor-frontend.vercel.app",
        description="Comma-separated list of allowed CORS origins",
    )
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=20,
        description="Maximum upload size per file in megabytes",
    )

    # Azure AI Content Safety configuration
    CONTENT_SAFETY_ENDPOINT: str = Field(
        default="", description="Azure AI Content Safety Endpoint"
    )
    CONTENT_SAFETY_KEY: str = Field(
        default="", description="Azure AI Content Safety Key"
    )
    CONTENT_SAFETY_ENABLED: bool = Field(
        default=True, description="Enable or disable Content Safety screening"
    )
    CONTENT_SAFETY_TIMEOUT: float = Field(
        default=10.0, description="Content Safety API call timeout in seconds"
    )
    CONTENT_SAFETY_FAILURE_POLICY: str = Field(
        default="fail_closed",
        description="Policy when screening fails: 'fail_closed' (reject) or 'fail_open' (allow)",
    )
    CONTENT_SAFETY_DEFAULT_THRESHOLD: int = Field(
        default=4,
        description="Default severity threshold (0, 2, 4, 6) for rejection (severity >= threshold)",
    )
    CONTENT_SAFETY_THRESHOLD_SEXUAL: int = Field(
        default=4, description="Severity threshold for Sexual category"
    )
    CONTENT_SAFETY_THRESHOLD_HATE: int = Field(
        default=4, description="Severity threshold for Hate category"
    )
    CONTENT_SAFETY_THRESHOLD_VIOLENCE: int = Field(
        default=4, description="Severity threshold for Violence category"
    )
    CONTENT_SAFETY_THRESHOLD_SELF_HARM: int = Field(
        default=4, description="Severity threshold for SelfHarm category"
    )
    CONTENT_SAFETY_BLOCKLIST_NAMES: str = Field(
        default="", description="Comma-separated Azure AI Content Safety blocklist names"
    )
    CONTENT_SAFETY_CUSTOM_TERMS: str = Field(
        default="",
        description="Comma-separated custom prohibited terms / profanities",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Return list of allowed CORS origins stripped of whitespace and trailing slashes."""
        if not self.CORS_ORIGINS:
            origins = []
        else:
            origins = [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]
        deployed_frontend = "https://fee-auditor-frontend.vercel.app"
        if deployed_frontend not in origins:
            origins.append(deployed_frontend)
        return origins

    @property
    def max_upload_size_bytes(self) -> int:
        """Return maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    @property
    def canonical_azure_endpoint(self) -> str:
        """Return normalized Azure Document Intelligence endpoint with trailing slashes removed."""
        return self.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT.strip().rstrip("/")

    @property
    def canonical_content_safety_endpoint(self) -> str:
        """Return normalized Azure Content Safety endpoint with trailing slashes removed."""
        return self.CONTENT_SAFETY_ENDPOINT.strip().rstrip("/")

    @property
    def blocklist_names_list(self) -> List[str]:
        """Return list of Azure blocklist names."""
        if not self.CONTENT_SAFETY_BLOCKLIST_NAMES:
            return []
        return [b.strip() for b in self.CONTENT_SAFETY_BLOCKLIST_NAMES.split(",") if b.strip()]

    @property
    def custom_terms_list(self) -> List[str]:
        """Return list of custom prohibited terms (lowercased)."""
        if not self.CONTENT_SAFETY_CUSTOM_TERMS:
            return []
        return [t.strip().lower() for t in self.CONTENT_SAFETY_CUSTOM_TERMS.split(",") if t.strip()]

    @property
    def category_thresholds(self) -> dict:
        """Return category to severity threshold mapping."""
        return {
            "Sexual": self.CONTENT_SAFETY_THRESHOLD_SEXUAL,
            "Hate": self.CONTENT_SAFETY_THRESHOLD_HATE,
            "Violence": self.CONTENT_SAFETY_THRESHOLD_VIOLENCE,
            "SelfHarm": self.CONTENT_SAFETY_THRESHOLD_SELF_HARM,
        }


settings = Settings()
