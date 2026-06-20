"""F6.3 알림 API."""
from pydantic import BaseModel
from fastapi import APIRouter

from app.services.notifier import notify

router = APIRouter(prefix="/notify", tags=["notify"])


class NotifyRequest(BaseModel):
    event: str
    payload: dict = {}


@router.post("/")
def send_notification(req: NotifyRequest) -> dict:
    """Telegram/Discord 알림 송출. 미설정 채널은 false (no-op)."""
    return notify(req.event, req.payload)
