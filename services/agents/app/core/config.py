"""agents — settings (env-driven)."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def _find_env_file() -> str:
    name = f".env.{os.getenv('APP_ENV', 'local')}"
    for parent in Path(__file__).resolve().parents:
        candidate = parent / name
        if candidate.exists():
            return str(candidate)
    return name  # not found; pydantic-settings silently skips missing files


_env_file = _find_env_file()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_file, extra="ignore")

    app_name: str = "stock-trader-agents"
    env: str = "local"
    redis_url: str = ""
    anthropic_api_key: str = ""
    analysis_url: str = "http://localhost:8001"
    rag_url: str = "http://localhost:8002"
    ingest_url: str = "http://localhost:8003"
    risk_engine_url: str = "http://localhost:3001"
    # F6.3 알림 — 실 토큰은 Keychain/Vault 주입. 미설정 시 no-op.
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    # F6.3 양방향 제어 — 인바운드 명령 인증 시크릿(Keychain/Vault). 미설정 시 전 제어 거부(안전 기본).
    control_secret: str = ""


settings = Settings()
