from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    OPENAI_API_KEY: str | None = None
    MODEL_DEFAULT: str = "gpt-4o"
    
    # Vector Store Configuration (REQUIRED)
    # Use DOC_VECTOR_STORE_ID as the primary vector store
    DOC_VECTOR_STORE_ID: str = Field(
        ...,  # Required - no default
        description="Primary document vector store ID (e.g., vs_6910a0f29b548191befd180730d968ee)"
    )
    
    # Knowledge Graph GCS Paths (REQUIRED for each domain)
    # Format: gs://bucket-name/path/to/file.json
    WEALTH_MANAGEMENT_KG_PATH: str = Field(
        ...,  # Required - no default
        description="GCS path to wealth management KG (e.g., gs://my-bucket/kg/wealth_product_kg.json)"
    )
    APF_KG_PATH: str = Field(
        ...,  # Required - no default
        description="GCS path to APF KG (e.g., gs://my-bucket/kg/apf_kg.json)"
    )
    
    # Optional: Domain-specific vector store overrides (defaults to DOC_VECTOR_STORE_ID)
    WEALTH_MANAGEMENT_VECTOR_STORE_ID: str | None = None
    APF_VECTOR_STORE_ID: str | None = None
    
    CACHE_DIR: str = "/tmp/ekg_cache"
    LOG_LEVEL: str = "INFO"
    MAX_CACHE_SIZE: int = 1000
    CACHE_TTL: int = 3600
    SESSION_SECRET_KEY: str = Field(
        "change-me",
        description="Secret used to sign session cookies. Override in production.",
    )
    SESSION_COOKIE_NAME: str = "ekg_admin_session"
    SESSION_COOKIE_SECURE: bool = Field(
        default=True,
        description="Set to False for local development (HTTP). True for production (HTTPS)."
    )
    SESSION_COOKIE_SAMESITE: str = "lax"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = (
        "$2b$12$4LnAjeX8ZBpBVyvrucwYcOGWvrEU6fCgtqlDJbw6yCmKjfir7k0AS"
    )  # Hash for 'ChangeMe123!'
    GOOGLE_SERVICE_ACCOUNT_FILE: str | None = None
    CORS_ORIGINS: str = Field(
        default="*",
        description="CORS allowed origins (comma-separated). Use '*' for all, or specific domains for production."
    )
    GOOGLE_ALLOWED_MIME_TYPES: list[str] = Field(
        default_factory=lambda: [
            "application/pdf",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
            "text/markdown",
            "text/csv",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ]
    )
    
    @field_validator("DOC_VECTOR_STORE_ID")
    @classmethod
    def validate_vectorstore_id(cls, v: str) -> str:
        if not v or not v.startswith("vs_"):
            raise ValueError("DOC_VECTOR_STORE_ID must start with 'vs_'")
        return v
    
    @field_validator("WEALTH_MANAGEMENT_KG_PATH", "APF_KG_PATH")
    @classmethod
    def validate_gcs_or_local_path(cls, v: str) -> str:
        """
        Accept either:
        - GCS paths (gs://...) for production
        - Existing local file paths for local/dev usage
        """
        if v.startswith("gs://"):
            return v
        from pathlib import Path
        p = Path(v)
        if p.exists() and p.is_file():
            return str(p.resolve())
        raise ValueError("KG paths must be gs://... or an existing local file path")

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def validate_openai_key(cls, v: str | None) -> str | None:
        if v and not v.startswith("sk-"):
            raise ValueError("Invalid OpenAI API key format")
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return v.upper()

    @field_validator("MAX_CACHE_SIZE")
    @classmethod
    def validate_cache_size(cls, v: int) -> int:
        if v < 10 or v > 10000:
            raise ValueError("MAX_CACHE_SIZE must be between 10 and 10000")
        return v

    @field_validator("CACHE_TTL")
    @classmethod
    def validate_cache_ttl(cls, v: int) -> int:
        if v < 60 or v > 86400:  # 1 minute to 24 hours
            raise ValueError("CACHE_TTL must be between 60 and 86400 seconds")
        return v

    @field_validator("SESSION_COOKIE_SAMESITE")
    @classmethod
    def validate_same_site(cls, v: str) -> str:
        allowed = {"lax", "strict", "none"}
        if v.lower() not in allowed:
            raise ValueError("SESSION_COOKIE_SAMESITE must be one of: lax, strict, none")
        return v.lower()

    model_config = {
        "env_file": ".env",
        "extra": "ignore",
    }


settings = Settings()
