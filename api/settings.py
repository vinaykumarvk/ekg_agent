from __future__ import annotations
from typing import Optional, List

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    MODEL_DEFAULT: str = "gpt-4o"
    KG_PATH: str = ""
    CACHE_DIR: str = "/tmp/ekg_cache"
    LOG_LEVEL: str = "INFO"
    MAX_CACHE_SIZE: int = 1000
    CACHE_TTL: int = 3600
    SESSION_SECRET_KEY: str = Field(
        "change-me",
        description="Secret used to sign session cookies. Override in production.",
    )
    SESSION_COOKIE_NAME: str = "ekg_admin_session"
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SAMESITE: str = "lax"
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = (
        "$2b$12$4LnAjeX8ZBpBVyvrucwYcOGWvrEU6fCgtqlDJbw6yCmKjfir7k0AS"
    )  # Hash for 'ChangeMe123!'
    GOOGLE_SERVICE_ACCOUNT_FILE: Optional[str] = None
    GOOGLE_ALLOWED_MIME_TYPES: List[str] = Field(
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
    # Vector Store IDs - can be set via environment variables or Google Cloud Secret Manager
    DOC_VECTOR_STORE_ID: Optional[str] = Field(
        None,
        description="Document vector store ID (shared across domains). Can be set via DOC_VECTOR_STORE_ID env var or Secret Manager."
    )
    KG_VECTOR_STORE_ID: Optional[str] = Field(
        None,
        description="Knowledge Graph vector store ID. Can be set via KG_VECTOR_STORE_ID env var or Secret Manager."
    )
    # Domain-specific vector store IDs (optional, fallback to DOC_VECTOR_STORE_ID)
    WEALTH_MANAGEMENT_VECTOR_STORE_ID: Optional[str] = Field(
        None,
        description="Wealth management domain vector store ID. Falls back to DOC_VECTOR_STORE_ID if not set."
    )
    APF_VECTOR_STORE_ID: Optional[str] = Field(
        None,
        description="APF domain vector store ID. Falls back to DOC_VECTOR_STORE_ID if not set."
    )

    @field_validator("OPENAI_API_KEY")
    @classmethod
    def validate_openai_key(cls, v: Optional[str]) -> Optional[str]:
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

