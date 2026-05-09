"""Settings, sourced from environment via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API keys. Secret to avoid accidental logging.
    anthropic_api_key: SecretStr = SecretStr("")
    tavily_api_key: SecretStr = SecretStr("")
    langfuse_public_key: SecretStr = SecretStr("")
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"

    # Models. Defaults track May 2026 line-up.
    planner_model: str = "claude-haiku-4-5-20251001"
    synthesizer_model: str = "claude-sonnet-4-6"
    critic_model: str = "claude-sonnet-4-6"

    # Behavior
    max_critic_retries: int = Field(default=1, ge=0, le=3)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    http_timeout_seconds: float = Field(default=15.0, gt=0)
    tavily_max_results: int = Field(default=8, ge=1, le=20)

    # Storage
    sqlite_path: str = "./data/ops_agent.db"
    # WAL is fastest on local disks but loses ``-wal`` files between cold
    # starts on network-backed volumes (e.g. Modal). Override with DELETE
    # for those environments.
    sqlite_journal_mode: Literal["WAL", "DELETE", "TRUNCATE", "MEMORY"] = "WAL"

    # App
    app_env: Literal["development", "docker", "modal", "test"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    cors_origins: str = "http://localhost:3000"
    cors_origin_regex: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def cors_origin_regex_or_none(self) -> str | None:
        """Starlette's CORSMiddleware does NOT treat strings like
        ``https://*.vercel.app`` as wildcards, it compares exact strings.
        Pass a regex via ``allow_origin_regex`` to match preview deploys.
        """
        return self.cors_origin_regex.strip() or None

    @property
    def langfuse_enabled(self) -> bool:
        return bool(
            self.langfuse_public_key.get_secret_value()
            and self.langfuse_secret_key.get_secret_value()
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
