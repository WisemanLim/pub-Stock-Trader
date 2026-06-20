"""analysis — 기술지표·시계열예측·스크리너 서비스 (F2)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import backtest, breadth, indicators, intraday_indicators, prediction, screener
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 실 거시·뉴스 채널 provider 연결 (lstm_model 멀티변량 입력).
    from app.services.channels import register
    register()
    yield


app = FastAPI(
    title=settings.app_name,
    description="F2: 기술지표 + 선형/LSTM/Transformer 예측(멀티변량) + 스크리너 + F5 백테스팅",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(indicators.router)
app.include_router(prediction.router)
app.include_router(screener.router)
app.include_router(backtest.router)
app.include_router(breadth.router)
app.include_router(intraday_indicators.router)  # D-4: 분봉 지표


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "analysis", "env": settings.env}
