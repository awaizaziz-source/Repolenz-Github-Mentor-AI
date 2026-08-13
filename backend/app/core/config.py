from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_ignore_empty=True, extra="ignore")

    app_name: str = "GitHub Mentor AI"
    app_env: Literal["development", "test", "production"] = "development"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = "http://localhost:3000"
    database_url: str = "sqlite+aiosqlite:///./data/repo_lens.db"
    redis_url: str = "redis://localhost:6379/0"
    repository_storage_path: str = "./data/repositories"
    github_token: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
