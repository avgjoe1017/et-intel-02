"""
Configuration management for ET Intelligence system.
Loads settings from environment variables.
"""

from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/et_intel"
    
    # OpenAI API (optional)
    openai_api_key: str | None = None
    
    # Sentiment Backend
    sentiment_backend: Literal["rule_based", "openai", "hybrid"] = "rule_based"
    
    # Logging
    log_level: str = "INFO"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )


# Global settings instance
settings = Settings()

