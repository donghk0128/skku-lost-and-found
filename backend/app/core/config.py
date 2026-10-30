from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from backend/.env or environment variables."""

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14
    post_image_dir: str = "post_images"
    cors_allowed_origins: list[str] = ["http://localhost:8081", "http://127.0.0.1:8081"]

    email_delivery_mode: str = "console"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "SKKU 찾자"
    smtp_use_tls: bool = True

    email_verification_expire_minutes: int = 5
    email_verification_resend_seconds: int = 60
    allowed_email_domain: str = "skku.edu"

    ai_provider: Literal["ollama", "openai"] = "ollama"
    ai_model: str = "llama3.2:3b"
    ai_timeout_seconds: float = 120
    ai_reasoning_effort: Literal["none", "low", "medium", "high", "xhigh", "max"] = "none"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://127.0.0.1:11434"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
