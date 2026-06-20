"""F1.2 브로커 인증·재연결 — 순수 헬퍼 (테스트 가능).

인증 메시지 빌드 + 지수 백오프 지연 계산. 실 키는 호출부에서 env/Keychain
으로 주입받아 전달(이 모듈은 보관 안 함). 브로커별 핸드셰이크는 build_auth_message
의 protocol 분기로 확장.
"""


def build_auth_message(protocol: str, api_key: str, api_secret: str, ticker: str) -> dict:
    """프로토콜별 인증 + 구독 핸드셰이크 메시지."""
    if protocol == "kis":
        # 한국투자증권 유사 — approval_key 헤더 + 체결 구독(H0STCNT0)
        return {
            "header": {"approval_key": api_key, "custtype": "P", "tr_type": "1"},
            "body": {"input": {"tr_id": "H0STCNT0", "tr_key": ticker}},
        }
    # generic — 토큰 인증 후 구독
    return {
        "action": "auth",
        "api_key": api_key,
        "signature": api_secret,
        "subscribe": ticker,
    }


def backoff_delay(attempt: int, base: float = 0.5, cap: float = 30.0) -> float:
    """지수 백오프 지연(초). attempt 0부터. 상한 cap.

    base * 2^attempt, 최대 cap. (지터는 호출부에서 선택 적용)
    """
    if attempt < 0:
        attempt = 0
    delay = base * (2 ** attempt)
    return min(delay, cap)


def should_retry(attempt: int, max_retries: int) -> bool:
    """max_retries < 0 → 무한 재시도. 그 외 attempt < max_retries."""
    if max_retries < 0:
        return True
    return attempt < max_retries
