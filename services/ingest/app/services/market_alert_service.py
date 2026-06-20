"""B-1: KRX KIND 시장경보 종목 수집기.

KIND(한국거래소 공시시스템)에서 투자주의/경고/위험/정리매매 종목 목록을 수집.
API 키 불필요 — 공개 HTTP 엔드포인트.
네트워크 오류 / 파싱 실패 시 빈 리스트 반환 (graceful).
"""
from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

KIND_URL = "https://kind.krx.co.kr/listinvstinfo/investwarnlist.do"

# KIND 응답 필드 → 정규 level 이름 매핑
_LEVEL_MAP: dict[str, str] = {
    "투자주의": "투자주의",
    "투자경고": "투자경고",
    "투자위험": "투자위험",
    "정리매매": "정리매매",
    "단기과열": "단기과열",
}


class KrxMarketAlertService:
    """KRX KIND 시장경보 종목 조회."""

    def __init__(self, timeout: float = 15.0) -> None:
        self._timeout = timeout

    def get_alert_stocks(self) -> list[dict[str, Any]]:
        """현재 시장경보 지정 종목 목록 반환.

        Returns:
            list of {"ticker", "name", "level", "date"}
            네트워크 오류 시 빈 리스트.
        """
        try:
            return self._fetch_all()
        except Exception as exc:
            logger.warning(f"market_alert_service: KIND 조회 실패 — {exc}")
            return []

    # ──────────────────────────────────────────────
    # 내부
    # ──────────────────────────────────────────────

    def _fetch_page(self, page: int = 1, page_size: int = 100) -> dict[str, Any]:
        resp = httpx.post(
            KIND_URL,
            data={
                "method": "searchInvstWarnList",
                "forward": "investwarnlist_main",
                "currentPageSize": str(page_size),
                "pageIndex": str(page),
                "orderMode": "1",
                "orderStat": "D",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://kind.krx.co.kr/",
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _fetch_all(self) -> list[dict[str, Any]]:
        data = self._fetch_page(1, 100)
        items: list[dict[str, Any]] = data.get("list", [])
        total: int = int(data.get("totalCount", len(items)))

        # 2페이지 이상 있으면 추가 수집
        fetched = len(items)
        page = 2
        while fetched < total:
            more = self._fetch_page(page, 100).get("list", [])
            if not more:
                break
            items.extend(more)
            fetched += len(more)
            page += 1

        return [self._normalize(r) for r in items if r]

    @staticmethod
    def _normalize(r: dict[str, Any]) -> dict[str, Any]:
        raw_level = str(r.get("invstWarnTpNm") or r.get("warningType") or "")
        level = _LEVEL_MAP.get(raw_level, raw_level or "unknown")
        raw_date = str(r.get("invstWarnDd") or r.get("designDd") or "")
        # YYYYMMDD → YYYY-MM-DD
        if len(raw_date) == 8 and raw_date.isdigit():
            raw_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
        return {
            "ticker": str(r.get("isuSrtCd") or r.get("ticker") or "").strip(),
            "name":   str(r.get("isuNm") or r.get("name") or "").strip(),
            "level":  level,
            "date":   raw_date,
        }
