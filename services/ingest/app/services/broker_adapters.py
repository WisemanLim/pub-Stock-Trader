"""F1.2 브로커 프로토콜 어댑터 — 증권사별 WS 메시지 → 표준 틱 정규화.

브로커마다 WS 메시지 포맷이 다름. 어댑터가 raw 메시지를 표준 dict
{ticker, price, change_pct, timestamp, source} 로 변환.
실 키/시크릿은 어댑터가 보관하지 않음 — 연결 계층(env/Keychain)에서 주입.

지원: kis(한국투자증권 유사), generic(JSON {price,...}).
신규 브로커 = register_adapter 로 추가(코드 수정 최소).
"""
import json
from datetime import datetime, timezone
from typing import Callable

Adapter = Callable[[str, str], dict | None]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _generic(ticker: str, raw: str) -> dict | None:
    """범용 JSON: {"price":.., "change_pct":.., "timestamp":..}."""
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if "price" not in msg:
        return None
    return {
        "ticker": ticker,
        "price": float(msg["price"]),
        "change_pct": float(msg.get("change_pct", 0.0)),
        "timestamp": msg.get("timestamp", _now()),
        "source": "broker:generic",
    }


def _kis(ticker: str, raw: str) -> dict | None:
    """한국투자증권 유사 — 캐럿(^) 구분 텍스트 또는 JSON.

    실시간 체결 예시(텍스트): "0|H0STCNT0|001|005930^123005^73500^..."
    필드: [.., .., .., 종목^체결시각^현재가^...]
    """
    # JSON 형태도 허용
    if raw.lstrip().startswith("{"):
        try:
            msg = json.loads(raw)
            body = msg.get("body", msg)
            price = body.get("stck_prpr") or body.get("price")
            if price is None:
                return None
            return {
                "ticker": ticker,
                "price": float(price),
                "change_pct": float(body.get("prdy_ctrt", 0.0)),
                "timestamp": _now(),
                "source": "broker:kis",
            }
        except (json.JSONDecodeError, ValueError):
            return None
    # 텍스트 파이프/캐럿 포맷
    try:
        payload = raw.split("|")[-1]
        fields = payload.split("^")
        if len(fields) < 3:
            return None
        price = float(fields[2])
        return {
            "ticker": fields[0] or ticker,
            "price": price,
            "change_pct": float(fields[5]) if len(fields) > 5 else 0.0,
            "timestamp": _now(),
            "source": "broker:kis",
        }
    except (ValueError, IndexError):
        return None


_ADAPTERS: dict[str, Adapter] = {
    "generic": _generic,
    "kis": _kis,
}


def register_adapter(name: str, fn: Adapter) -> None:
    _ADAPTERS[name] = fn


def get_adapter(name: str) -> Adapter:
    if name not in _ADAPTERS:
        raise ValueError(f"Unknown broker adapter: {name}. Available: {list(_ADAPTERS)}")
    return _ADAPTERS[name]


def list_adapters() -> list[str]:
    return list(_ADAPTERS)
