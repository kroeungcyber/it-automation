# src/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    anthropic_api_key: str
    ollama_base_url: str
    local_model: str = "gemma3:latest"
    cloud_model: str = "claude-sonnet-4-6"
    log_level: str = "INFO"
    jwt_secret: str = "change-me-in-production"
    jwt_expiry_seconds: int = 28800  # 8 hours
