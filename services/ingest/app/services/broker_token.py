"""F1.2 브로커 액세스 토큰 — 발급·만료·재발급 (KIS 등 OAuth 유사).

issuer 콜백이 (token, ttl_seconds) 반환. 만료 skew 초 전에 자동 재발급.
실 키는 issuer 클로저가 보관(env/Keychain), 이 매니저는 토큰 값·만료시각만 캐시.
now_fn 주입으로 시계 테스트 가능.
"""
import time
from typing import Callable


class TokenManager:
    def __init__(
        self,
        issuer: Callable[[], tuple[str, float]],
        skew_seconds: float = 60.0,
        now_fn: Callable[[], float] = time.time,
    ) -> None:
        self._issuer = issuer
        self._skew = skew_seconds
        self._now = now_fn
        self._token: str | None = None
        self._expires_at: float = 0.0
        self.issue_count = 0

    def is_expired(self) -> bool:
        """만료 skew 이내면 만료로 간주(선제 재발급)."""
        if self._token is None:
            return True
        return self._now() >= (self._expires_at - self._skew)

    def get_token(self) -> str:
        """유효 토큰 반환 — 만료 임박 시 재발급."""
        if self.is_expired():
            token, ttl = self._issuer()
            self._token = token
            self._expires_at = self._now() + ttl
            self.issue_count += 1
        return self._token  # type: ignore[return-value]

    def invalidate(self) -> None:
        """강제 무효화 — 다음 get_token 시 재발급(401 응답 등)."""
        self._token = None
        self._expires_at = 0.0
