"""rag — settings (env-driven)."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_file = str(Path(__file__).resolve().parents[4] / f".env.{os.getenv('APP_ENV', 'local')}")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    app_name: str = "stock-trader-rag"
    env: str = "local"
    database_url: str = "sqlite:///./local.db"
    redis_url: str = ""
    anthropic_api_key: str = ""


settings = Settings()
