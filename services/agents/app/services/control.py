"""F6.3 양방향 제어 — 알림 채널(Telegram/Discord) 인바운드 명령 수신·실행.

지원 명령: /status · /stop(긴급 중지) · /resume · /liquidate(긴급 청산).
무권한 거래/제어 방지(전자금융거래법 §정신) 위해 공유 시크릿(control_secret) 정확 일치 필수.
시크릿 미설정 시 전 인바운드 명령 거부(안전 기본). 실행은 risk-engine 제어 엔드포인트 호출.
"""
import httpx

from app.core.config import settings

COMMANDS = {"/status", "/stop", "/resume", "/liquidate"}


def parse_command(text: str) -> str | None:
    """입력 텍스트 첫 토큰이 지원 명령이면 정규화 반환, 아니면 None."""
    if not text:
        return None
    token = text.strip().split()[0].lower()
    return token if token in COMMANDS else None


def authorized(secret: str | None) -> bool:
    """제어 인증 — 시크릿 미설정이면 항상 거부, 설정 시 정확 일치만 허용."""
    return bool(settings.control_secret) and secret == settings.control_secret


def execute_command(cmd: str, prices: dict | None = None) -> dict:
    """명령을 risk-engine 제어 엔드포인트로 위임. 장애 시 error 반환(degrade)."""
    base = settings.risk_engine_url
    try:
        if cmd == "/status":
            r = httpx.get(f"{base}/control/status", timeout=5.0)
            return {"command": cmd, "result": r.json()}
        if cmd == "/stop":
            r = httpx.post(f"{base}/control/halt", json={"halted": True}, timeout=5.0)
            return {"command": cmd, "result": r.json()}
        if cmd == "/resume":
            r = httpx.post(f"{base}/control/halt", json={"halted": False}, timeout=5.0)
            return {"command": cmd, "result": r.json()}
        if cmd == "/liquidate":
            r = httpx.post(f"{base}/control/liquidate", json={"prices": prices or {}}, timeout=10.0)
            return {"command": cmd, "result": r.json()}
    except Exception as exc:
        return {"command": cmd, "error": str(exc)}
    return {"command": cmd, "error": "unsupported command"}
