"""agents — LLM 멀티에이전트 오케스트레이터 (F3.1) + 자가교정(F3.3) + 양방향 제어(F6.3)."""
from fastapi import FastAPI

from app.api import agents, control, notify
from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    description="F3.1 멀티에이전트 + F3.3 자가교정 + F6.3 알림·양방향 제어(Telegram/Discord)",
    version="0.3.0",
)

app.include_router(agents.router)
app.include_router(notify.router)
app.include_router(control.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "agents", "env": settings.env}
