"""F1.5 KRX OPEN API 전용 수집기.

API 키 미설정 시 빈 결과 반환 → FinanceDataReader 폴백 유지.
실 키: OS Keychain or Vault → KRX_OPEN_API_KEY 환경변수로 주입. 파일 기재 금지.
"""
from __future__ import annotations

import time
from typing import Any

import httpx


class KrxOpenApiService:
    """KRX OPEN API 2단계 호출 클라이언트 (OTP → 데이터).

    Step 1: GET  GenerateOTP.jspx?bld={api_id} → OTP 토큰
    Step 2: POST jsonSvr.do, form data code={OTP} → JSON
    """

    OTP_URL  = "https://openapi.krx.co.kr/contents/COM/GenerateOTP.jspx"
    DATA_URL = "https://openapi.krx.co.kr/contents/USERSVR/jsonSvr.do"

    # API ID 매핑
    API_IDS = {
        "KOSPI":  "stk_bydd_trd",
        "KOSDAQ": "ksq_bydd_trd",
        "KONEX":  "knx_bydd_trd",
    }
    INVESTOR_API_ID   = "stk_invsr_trd_by_isu"
    SHORT_SELL_API_ID = "stk_smls_trd_by_isu"   # 공매도 거래실적 종목별

    def __init__(self, api_key: str = "", rate_limit: float = 0.5) -> None:
        self._api_key   = api_key
        self._configured = bool(api_key)
        self._rate_limit = rate_limit
        self._last_call  = 0.0

    @property
    def configured(self) -> bool:
        return self._configured

    # ──────────────────────────────────────────────────────────
    # 공개 메서드
    # ──────────────────────────────────────────────────────────

    def get_daily_ohlcv(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
        market: str = "KOSPI",
    ) -> list[dict]:
        """일별 OHLCV (KRX OPEN API).

        Args:
            ticker:    6자리 종목코드 (005930)
            from_date: YYYYMMDD 시작일
            to_date:   YYYYMMDD 종료일
            market:    KOSPI | KOSDAQ | KONEX (기본 KOSPI)

        Returns:
            빈 리스트(미설정·오류) 또는 OHLCV dict 리스트.
        """
        if not self._configured:
            return []
        api_id = self.API_IDS.get(market.upper(), self.API_IDS["KOSPI"])
        rows = self._fetch(api_id, {"isuCd": ticker, "strtDd": from_date, "endDd": to_date})
        result: list[dict] = []
        for r in rows:
            try:
                result.append({
                    "date":       _fmt_date(r.get("TRD_DD", "")),
                    "open":       _to_int(r.get("OPNPRC", 0)),
                    "high":       _to_int(r.get("HGPRC", 0)),
                    "low":        _to_int(r.get("LWPRC", 0)),
                    "close":      _to_int(r.get("CLSPRC", 0)),
                    "volume":     _to_int(r.get("ACC_TRDVOL", 0)),
                    "change_pct": _to_float(r.get("FLUC_RT", 0)),
                    "source":     "krx_openapi",
                })
            except Exception:
                continue
        return result

    def get_investor_flow(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
    ) -> list[dict]:
        """투자자별 순매수 (기관/외국인/개인) 일별 데이터.

        Returns:
            빈 리스트(미설정·오류) 또는 flow dict 리스트.
        """
        if not self._configured:
            return []
        rows = self._fetch(
            self.INVESTOR_API_ID,
            {"isuCd": ticker, "strtDd": from_date, "endDd": to_date},
        )
        result: list[dict] = []
        for r in rows:
            try:
                result.append({
                    "date":       _fmt_date(r.get("TRD_DD", "")),
                    "institution": _to_int(r.get("INST_NETBID_TRDVOL", 0)),
                    "foreign":     _to_int(r.get("FRGN_NETBID_TRDVOL", 0)),
                    "individual":  _to_int(r.get("INDV_NETBID_TRDVOL", 0)),
                    "source":      "krx_openapi",
                })
            except Exception:
                continue
        return result

    def get_short_selling(
        self,
        ticker: str,
        from_date: str,
        to_date: str,
    ) -> list[dict]:
        """공매도 거래실적 일별 데이터 (B-3).

        Returns:
            빈 리스트(미설정·오류) 또는 short-selling dict 리스트.
        """
        if not self._configured:
            return []
        rows = self._fetch(
            self.SHORT_SELL_API_ID,
            {"isuCd": ticker, "strtDd": from_date, "endDd": to_date},
        )
        result: list[dict] = []
        for r in rows:
            try:
                result.append({
                    "date":        _fmt_date(r.get("TRD_DD", "")),
                    "short_vol":   _to_int(r.get("SMLS_TRDVOL", 0)),
                    "short_val":   _to_int(r.get("SMLS_TRDVAL", 0)),
                    "short_ratio": _to_float(r.get("SMLS_RT", 0)),
                    "source":      "krx_openapi",
                })
            except Exception:
                continue
        return result

    # ──────────────────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────────────────

    def _wait(self) -> None:
        now = time.monotonic()
        gap = self._rate_limit - (now - self._last_call)
        if gap > 0:
            time.sleep(gap)
        self._last_call = time.monotonic()

    def _get_otp(self, api_id: str) -> str:
        self._wait()
        resp = httpx.get(
            self.OTP_URL,
            params={"bld": api_id, "name": "fileDown"},
            headers={"AUTH_KEY": self._api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.text.strip()

    def _fetch(self, api_id: str, extra: dict[str, Any] | None = None) -> list[dict]:
        try:
            otp = self._get_otp(api_id)
            self._wait()
            form: dict[str, Any] = {"code": otp}
            if extra:
                form.update(extra)
            resp = httpx.post(self.DATA_URL, data=form, timeout=30.0)
            resp.raise_for_status()
            return resp.json().get("OutBlock_1", [])
        except Exception:
            return []


# ──────────────────────────────────────────────────────────────
# 변환 헬퍼
# ──────────────────────────────────────────────────────────────

def _fmt_date(raw: str) -> str:
    """YYYYMMDD → YYYY-MM-DD. 이미 하이픈 형식이면 그대로."""
    s = str(raw).replace(",", "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    return s


def _to_int(raw: Any) -> int:
    try:
        return int(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0


def _to_float(raw: Any) -> float:
    try:
        return float(str(raw).replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0
