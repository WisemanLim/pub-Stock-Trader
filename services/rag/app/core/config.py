"""rag — settings (env-driven)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    app_name: str = "stock-trader-rag"
    env: str = "local"
    database_url: str = "sqlite:///./local.db"
    redis_url: str = ""
    anthropic_api_key: str = ""


settings = Settings()
