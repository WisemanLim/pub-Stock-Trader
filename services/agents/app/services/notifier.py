"""F6.3 시스템 알림 — Telegram / Discord webhook.

토큰·webhook URL 은 env(Keychain/Vault 주입). 미설정 시 no-op(로그만) → 안전.
매매 결과 브리핑·긴급 경보 송출. 양방향 제어(봇 중지/청산)는 후속.
"""
import httpx

from app.core.config import settings


def _format_message(event: str, payload: dict) -> str:
    lines = [f"[stock-trader] {event}"]
    for k, v in payload.items():
        lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return False
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=5.0,
        )
        return r.status_code == 200
    except Exception:
        return False


def send_discord(text: str) -> bool:
    url = settings.discord_webhook_url
    if not url:
        return False
    try:
        r = httpx.post(url, json={"content": text}, timeout=5.0)
        return r.status_code in (200, 204)
    except Exception:
        return False


def notify(event: str, payload: dict) -> dict:
    """모든 설정된 채널로 송출. 반환: 채널별 성공 여부."""
    text = _format_message(event, payload)
    return {
        "message": text,
        "telegram": send_telegram(text),
        "discord": send_discord(text),
    }
