"""rag — settings (env-driven)."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    name = f".env.{os.getenv('APP_ENV', 'local')}"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / name
        if candidate.exists():
            return str(candidate)
    return name


_env_file = _find_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    app_name: str = "stock-trader-rag"
    env: str = "local"
    database_url: str = "sqlite:///./local.db"
    redis_url: str = ""
    anthropic_api_key: str = ""


settings = Settings()
