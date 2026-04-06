"""
Configuration management using Pydantic settings.

Loads configuration from environment variables and .env file.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or .env file.
    """

    # Database configuration
    # PostgreSQL connection string in the format:
    # postgresql+psycopg://user:password@host:port/database
    # For local development, you can also use SQLite:
    # sqlite+aiosqlite:///./protein_annotation.db
    database_url: str = Field(
        default="postgresql+psycopg://pat_user:pat_password@localhost:5432/protein_annotation_db",
        description="Database connection URL (PostgreSQL or SQLite)"
    )

    # Optional Redis cache
    # Set to None to disable caching
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis connection URL for caching (optional)"
    )

    # API base URLs
    # These should rarely need to change
    uniprot_api_base: str = Field(
        default="https://rest.uniprot.org",
        description="UniProt REST API base URL"
    )

    kegg_api_base: str = Field(
        default="https://rest.kegg.jp",
        description="KEGG REST API base URL"
    )

    blast_api_base: str = Field(
        default="https://blast.ncbi.nlm.nih.gov/blast/Blast.cgi",
        description="NCBI BLAST API base URL"
    )

    # Performance settings
    # Control concurrent API requests and batch sizes
    max_concurrent_requests: int = Field(
        default=50,
        description="Maximum number of concurrent API requests"
    )

    request_timeout: int = Field(
        default=30,
        description="HTTP request timeout in seconds"
    )

    batch_size: int = Field(
        default=100,
        description="Default batch size for database operations"
    )

    # Logging configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )

    log_format: str = Field(
        default="console",
        description="Log format: 'console' for human-readable, 'json' for structured"
    )

    # NCBI BLAST configuration (optional)
    # Required only for submitting new BLAST searches
    ncbi_email: Optional[str] = Field(
        default=None,
        description="Email address for NCBI API (required for BLAST submission)"
    )

    # Pydantic configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore unknown environment variables
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get application settings singleton.

    Settings are cached after first load for performance.

    Returns:
        Settings: Application configuration
    """
    return Settings()
