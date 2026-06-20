"""F6.3 양방향 제어 API — 인바운드 명령 수신(웹훅) → risk-engine 제어.

POST /control/command — 일반 명령(시크릿 본문 첨부).
POST /control/telegram — Telegram 웹훅 update(시크릿 query/header). 봇 중지·청산 원격 제어.
"""
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.control import authorized, execute_command, parse_command

router = APIRouter(prefix="/control", tags=["control"])


class CommandRequest(BaseModel):
    secret: str = ""
    text: str                 # 예: "/stop", "/liquidate"
    prices: dict = {}         # /liquidate 시 종목별 청산 기준가


@router.post("/command")
def command(req: CommandRequest) -> dict:
    """일반 인바운드 명령 — 시크릿 인증 후 risk-engine 제어 실행."""
    if not authorized(req.secret):
        raise HTTPException(status_code=403, detail="unauthorized control command")
    cmd = parse_command(req.text)
    if cmd is None:
        raise HTTPException(status_code=400, detail=f"unknown command: {req.text}")
    return execute_command(cmd, req.prices)


class TelegramUpdate(BaseModel):
    message: dict = {}        # Telegram update 의 message 객체


@router.post("/telegram")
def telegram(
    update: TelegramUpdate,
    secret: str = "",
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Telegram 웹훅 — 봇이 보낸 명령 메시지 수신. 시크릿: query 또는 Telegram 헤더."""
    token = x_telegram_bot_api_secret_token or secret
    if not authorized(token):
        raise HTTPException(status_code=403, detail="unauthorized control command")
    text = (update.message or {}).get("text", "")
    cmd = parse_command(text)
    if cmd is None:
        raise HTTPException(status_code=400, detail=f"unknown command: {text}")
    return execute_command(cmd)
