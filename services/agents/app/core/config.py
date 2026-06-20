"""agents — settings (env-driven)."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# config.py: <root>/services/agents/app/core/config.py → parents[4] = repo root
_env_file = str(Path(__file__).resolve().parents[4] / f".env.{os.getenv('APP_ENV', 'local')}")


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
