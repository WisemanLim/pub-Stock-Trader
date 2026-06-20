"""analysis — settings (env-driven)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env.local", extra="ignore")

    app_name: str = "stock-trader-analysis"
    env: str = "local"
    database_url: str = "sqlite:///./local.db"
    redis_url: str = ""
    ingest_url: str = "http://localhost:8003"   # 뉴스 센티먼트 소스
    macro_index: str = "KS11"                    # 단일 거시 지표 폴백
    macro_indices: str = "KS11,USD/KRW"          # 다지표 합성(콤마): 지수·환율·금리
    macro_combine: str = "mean"                  # mean | weighted | pca
    macro_weights: str = ""                      # weighted 모드 가중치(콤마, 심볼 순서)
    finbert_enabled: bool = False                # True 시 FinBERT 모델 센티먼트
    finbert_model: str = "ProsusAI/finbert"      # KR: snunlp/KR-FinBert-SC


settings = Settings()
