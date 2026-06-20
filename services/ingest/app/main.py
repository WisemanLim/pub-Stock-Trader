"""ingest — 실시간 시세·뉴스·FastMCP 데이터 수집 서비스 (F1)."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import esg, intraday, krx, market, news, orderbook, scheduler as scheduler_api
from app.core.config import settings
from app.db import init_db
from app.services import batch_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────
    init_db()  # ohlcv_daily / investor_flow_daily 테이블 생성 (멱등)
    if settings.scheduler_enabled:
        batch_scheduler.start()
    yield
    # ── shutdown ─────────────────────────────────
    batch_scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    description="F1: 시세·호가창·뉴스 REST API + WebSocket 스트리밍 + FastMCP 서버 + 배치 스케줄러",
    version="0.3.0",
    lifespan=lifespan,
)

app.include_router(market.router)
app.include_router(orderbook.router)
app.include_router(news.router)
app.include_router(krx.router)
app.include_router(scheduler_api.router)
app.include_router(esg.router)        # D-1: ESG 점수
app.include_router(intraday.router)   # D-3: 분봉 데이터


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "ingest", "env": settings.env}
