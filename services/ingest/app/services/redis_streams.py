"""Redis Streams publisher — F1.3 뉴스·시세 이벤트 발행."""
from typing import Optional

import redis as redis_lib

from app.core.config import settings


class RedisStreamPublisher:
    def __init__(self) -> None:
        self._client: Optional[redis_lib.Redis] = None

    def _get_client(self) -> Optional[redis_lib.Redis]:
        if not settings.redis_url:
            return None
        if self._client is None:
            self._client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        return self._client

    def publish_tick(self, ticker: str, data: dict) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.xadd(f"ticks:{ticker}", {k: str(v) for k, v in data.items()}, maxlen=1000)
            return True
        except Exception:
            return False

    def publish_news(self, source: str, item: dict) -> bool:
        client = self._get_client()
        if client is None:
            return False
        try:
            client.xadd(f"news:{source}", {k: str(v) for k, v in item.items()}, maxlen=500)
            return True
        except Exception:
            return False


publisher = RedisStreamPublisher()
