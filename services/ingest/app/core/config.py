"""ingest — settings (env-driven)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    app_name: str = "stock-trader-ingest"
    env: str = "local"
    database_url: str = "sqlite:///./local.db"
    redis_url: str = ""
    broker_ws_url: str = ""
    broker_protocol: str = "generic"  # generic | kis
    # 브로커 인증 — 실 키는 Keychain/Vault 주입. 파일 기재 금지.
    broker_api_key: str = ""
    broker_api_secret: str = ""
    broker_max_retries: int = -1  # -1 = 무한 재연결
    broker_heartbeat_interval: float = 20.0  # ping 주기(초)
    broker_heartbeat_timeout: float = 60.0   # 무활동 stale 판정(초)
    # KRX OPEN API — 실 키는 Keychain/Vault 주입. 파일 기재 금지.
    krx_open_api_key: str = ""
    krx_api_rate_limit: float = 0.5   # 호출 최소 간격(초)
    # 배치 스케줄러 (Phase A-2)
    scheduler_enabled: bool = True
    scheduler_tickers: list[str] = []  # 예: ["005930","000660"]
    scheduler_hour: int = 15
    scheduler_minute: int = 40


settings = Settings()
