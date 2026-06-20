"""F1.2 다종목 멀티플렉싱 — 단일 WS로 다종목 구독 + 틱 라우팅.

build_subscribe_messages: 인증 1회 + 종목별 구독 메시지 생성.
MultiplexRouter: 수신 틱을 ticker 별 버퍼로 디멀티플렉싱(fan-out).
순수 로직 → 테스트 가능. 실 WS 연동은 broker_feed 에서 사용.
"""
from app.services.adaptive_flow import AIMDRateController, PriorityCommandQueue
from app.services.broker_auth import build_auth_message


def build_subscribe_messages(
    protocol: str, api_key: str, api_secret: str, tickers: list[str]
) -> list[dict]:
    """첫 메시지=인증+첫종목 구독, 이후=구독만. KIS=종목별 body 반복."""
    if not tickers:
        return []
    msgs = [build_auth_message(protocol, api_key, api_secret, tickers[0])]
    for tk in tickers[1:]:
        msgs.append(build_sub_message(protocol, tk))
    return msgs


def build_sub_message(protocol: str, ticker: str) -> dict:
    """단일 종목 구독 메시지(동적 추가용)."""
    if protocol == "kis":
        return {"header": {"tr_type": "1"}, "body": {"input": {"tr_id": "H0STCNT0", "tr_key": ticker}}}
    return {"action": "subscribe", "subscribe": ticker}


def build_unsub_message(protocol: str, ticker: str) -> dict:
    """단일 종목 구독 해지 메시지(동적 제거용)."""
    if protocol == "kis":
        return {"header": {"tr_type": "2"}, "body": {"input": {"tr_id": "H0STCNT0", "tr_key": ticker}}}
    return {"action": "unsubscribe", "unsubscribe": ticker}


class MultiplexRouter:
    """ticker → 버퍼 디멀티플렉서."""

    def __init__(self) -> None:
        self.buffers: dict[str, list[dict]] = {}

    def subscribe(self, ticker: str) -> bool:
        """동적 구독 추가. 신규면 True, 이미 있으면 False."""
        t = ticker.upper()
        if t in self.buffers:
            return False
        self.buffers[t] = []
        return True

    def unsubscribe(self, ticker: str) -> bool:
        """동적 구독 해지. 존재하면 True."""
        return self.buffers.pop(ticker.upper(), None) is not None

    def is_subscribed(self, ticker: str) -> bool:
        return ticker.upper() in self.buffers

    def dispatch(self, tick: dict) -> bool:
        """틱을 해당 ticker 버퍼로 라우팅. 미구독 종목은 False."""
        t = (tick.get("ticker") or "").upper()
        if t in self.buffers:
            self.buffers[t].append(tick)
            return True
        return False

    def drain(self, ticker: str) -> list[dict]:
        """버퍼 비우고 반환."""
        t = ticker.upper()
        out = self.buffers.get(t, [])
        self.buffers[t] = []
        return out

    def tickers(self) -> list[str]:
        return list(self.buffers)


class SubscriptionManager:
    """실행 중 WS 런타임 구독/해지 — 명령을 큐에 적재, 스트림 루프가 송신.

    라우터 상태 + 대기 명령(메시지). 송신은 broker_feed 스트림이 drain_commands 로 수행.
    """

    def __init__(self, protocol: str, ack_timeout: float = 5.0, max_resend: int = 3,
                 cb_threshold: int = 3, cb_cooldown: float = 30.0,
                 channel_threshold: int | None = None,
                 rate_limit: float = 0.0, bucket_capacity: float = 0.0,
                 channel_rates: dict | None = None, now_fn=None,
                 aimd: AIMDRateController | None = None,
                 command_capacity: int = 0, command_watermark: int = 0) -> None:
        import time
        self.protocol = protocol
        self.router = MultiplexRouter()
        # 송신 대기 메시지 — 기본 FIFO 리스트. command_capacity/watermark>0 시 우선순위 큐(백프레셔).
        self._pending: list[dict] = []
        self._pq: PriorityCommandQueue | None = (
            PriorityCommandQueue(capacity=command_capacity, high_watermark=command_watermark)
            if (command_capacity or command_watermark) else None
        )
        self.ack_state: dict[str, str] = {}   # ticker → pending|acked|failed
        self._sent_at: dict[str, float] = {}  # ticker → 마지막 송신 시각
        self._resend: dict[str, int] = {}     # ticker → 재송신 횟수
        self._ack_timeout = ack_timeout
        self._max_resend = max_resend
        self._now = now_fn or time.time
        # 전역 서킷브레이커 — 연속 구독실패 cb_threshold 회 → open(전체 신규 구독 차단)
        self._cb_threshold = cb_threshold
        self._channel_threshold = channel_threshold if channel_threshold is not None else cb_threshold
        self._cb_cooldown = cb_cooldown
        self._cb_failures = 0
        self._cb_opened_at = 0.0
        self.cb_state = "closed"  # closed | open | half_open
        self._probe_inflight = False  # half_open 탐침 진행중
        # 점진 트래픽 증대(rate ramp) — 복구 후 한도 점진 상향
        self._ramp_active = False
        self._ramp_limit = 0      # 현재 허용 수
        self._ramp_admitted = 0   # ramp 중 허용된 구독 수
        self._ramp_step = 2       # tick 당 한도 증가
        self._ramp_at = 0.0
        self._ramp_interval = 5.0
        # 종목별 서킷브레이커 — ticker → opened_at(해당 종목만 cooldown 차단)
        self._ticker_cb_open: dict[str, float] = {}
        # 채널별 서킷브레이커 — channel(소스/프로토콜) → 실패수·opened_at
        self._ticker_channel: dict[str, str] = {}
        self._channel_failures: dict[str, int] = {}
        self._channel_open: dict[str, float] = {}
        # AIMD 적응형 처리율 — 주입 시 전역 토큰버킷 rate 를 동적 구동(ack 성공=증가, 구독실패=감소).
        # 전역 버킷에만 적용(채널별 버킷은 고정 rate). aimd 미지정 시 rate_limit 고정.
        self._aimd = aimd
        # 토큰버킷 처리율 제한 — rate(토큰/초), capacity(버스트). 0=무제한.
        # 전역 버킷 + 채널별 버킷(channel_rates={"news":(rate,cap),...}).
        self._tb_rate = aimd.current_rate() if aimd else rate_limit
        self._tb_cap = bucket_capacity if bucket_capacity > 0 else max(1.0, self._tb_rate)
        self._tb_tokens = self._tb_cap
        self._tb_at = self._now()
        # 채널별: ch → [rate, cap, tokens, at]
        self._tb_ch: dict[str, list[float]] = {}
        for ch, spec in (channel_rates or {}).items():
            rate, cap = (spec if isinstance(spec, (tuple, list)) else (spec, spec))
            cap = cap if cap > 0 else max(1.0, rate)
            self._tb_ch[ch] = [rate, cap, cap, self._now()]

    def _bucket_refill(self, st: list[float]) -> None:
        rate, cap = st[0], st[1]
        if rate <= 0:
            return
        now = self._now()
        st[2] = min(cap, st[2] + (now - st[3]) * rate)
        st[3] = now

    def _tb_refill(self) -> None:
        if self._aimd is not None:
            self._tb_rate = self._aimd.current_rate()  # AIMD 적응 rate 동기화
        if self._tb_rate <= 0:
            return
        now = self._now()
        elapsed = now - self._tb_at
        self._tb_tokens = min(self._tb_cap, self._tb_tokens + elapsed * self._tb_rate)
        self._tb_at = now

    def _tb_consume(self, channel: str = "default") -> bool:
        """토큰 1개 소비 — 채널별 버킷 우선, 없으면 전역. rate 0 이면 항상 허용."""
        st = self._tb_ch.get(channel)
        if st is not None:
            if st[0] <= 0:
                return True
            self._bucket_refill(st)
            if st[2] >= 1.0:
                st[2] -= 1.0
                return True
            return False
        if self._tb_rate <= 0:
            return True
        self._tb_refill()
        if self._tb_tokens >= 1.0:
            self._tb_tokens -= 1.0
            return True
        return False

    def tokens_available(self, channel: str = "default") -> float:
        st = self._tb_ch.get(channel)
        if st is not None:
            self._bucket_refill(st)
            return st[2]
        self._tb_refill()
        return self._tb_tokens

    # ── 송신 대기 큐 추상화 — 기본 FIFO 리스트 / 우선순위 큐(백프레셔) 양쪽 지원 ──

    def _enqueue(self, msg: dict, priority: int) -> None:
        if self._pq is not None:
            self._pq.push(msg, priority)
        else:
            self._pending.append(msg)

    def _dequeue_all(self) -> list[dict]:
        if self._pq is not None:
            return self._pq.drain()        # 우선순위 순서
        out = self._pending
        self._pending = []
        return out

    def command_backpressured(self) -> bool:
        """우선순위 큐 백프레셔 활성 여부(미사용 시 항상 False) — 피드 루프 생산속도 조절 신호."""
        return self._pq.is_backpressured() if self._pq is not None else False

    def commands_dropped(self) -> int:
        """용량 초과로 드롭된 저우선 명령 수(우선순위 큐 전용)."""
        return self._pq.dropped if self._pq is not None else 0

    def current_rate(self) -> float:
        """현재 전역 토큰버킷 rate(AIMD 적응 시 변동)."""
        if self._aimd is not None:
            self._tb_rate = self._aimd.current_rate()
        return self._tb_rate

    def _cb_check(self) -> None:
        """전역 open 상태에서 cooldown 경과 시 half_open 전환."""
        if self.cb_state == "open" and (self._now() - self._cb_opened_at) >= self._cb_cooldown:
            self.cb_state = "half_open"

    def circuit_open(self) -> bool:
        self._cb_check()
        return self.cb_state == "open"

    def probe(self, ticker: str = "__PROBE__") -> dict | None:
        """half_open 탐침 — 단일 탐침 구독 메시지 송신(상태 확인용).

        half_open 일 때만 1건 반환. probe_ack/probe_fail 로 결과 반영.
        """
        self._cb_check()
        if self.cb_state != "half_open" or self._probe_inflight:
            return None
        self._probe_inflight = True
        return build_sub_message(self.protocol, ticker.upper())

    def probe_ack(self) -> None:
        """탐침 성공 → 전역 서킷 닫힘 + 점진 트래픽 증대 시작."""
        if self.cb_state == "half_open":
            self.cb_state = "closed"
            self._cb_failures = 0
            # rate ramp 시작 — 즉시 전체 재개 대신 점진 허용
            self._ramp_active = True
            self._ramp_limit = self._ramp_step
            self._ramp_admitted = 0
            self._ramp_at = self._now()
        self._probe_inflight = False

    def ramp_tick(self) -> None:
        """ramp 한도 점진 상향 — interval 경과마다 step 증가."""
        if not self._ramp_active:
            return
        if (self._now() - self._ramp_at) >= self._ramp_interval:
            self._ramp_limit += self._ramp_step
            self._ramp_at = self._now()

    def ramp_allows(self) -> bool:
        """ramp 비활성이면 항상 허용, 활성이면 한도 내."""
        if not self._ramp_active:
            return True
        return self._ramp_admitted < self._ramp_limit

    def probe_fail(self) -> None:
        """탐침 실패 → 전역 서킷 재오픈(cooldown 재시작)."""
        if self.cb_state == "half_open":
            self.cb_state = "open"
            self._cb_opened_at = self._now()
        self._probe_inflight = False

    def ticker_circuit_open(self, ticker: str) -> bool:
        """종목별 서킷 오픈 여부 — cooldown 경과 시 자동 해제."""
        t = ticker.upper()
        opened = self._ticker_cb_open.get(t)
        if opened is None:
            return False
        if (self._now() - opened) >= self._cb_cooldown:
            del self._ticker_cb_open[t]  # cooldown 경과 → 해제
            return False
        return True

    def channel_circuit_open(self, channel: str) -> bool:
        """채널별 서킷 오픈 여부 — cooldown 경과 시 자동 해제."""
        opened = self._channel_open.get(channel)
        if opened is None:
            return False
        if (self._now() - opened) >= self._cb_cooldown:
            del self._channel_open[channel]
            self._channel_failures[channel] = 0
            return False
        return True

    def add(self, ticker: str, channel: str = "default", priority: int = 0) -> bool:
        self._cb_check()
        if self.cb_state == "open":
            return False  # 전역 서킷 오픈 → 신규 구독 차단
        if self.channel_circuit_open(channel):
            return False  # 채널 서킷 오픈 → 해당 채널 차단
        if self.ticker_circuit_open(ticker):
            return False  # 종목별 서킷 오픈 → 해당 종목 차단
        if not self.ramp_allows():
            return False  # rate ramp 한도 초과 → 점진 허용 대기
        t = ticker.upper()
        # 토큰버킷 — 신규 구독만 토큰 소비(중복은 미소비)
        if not self.router.is_subscribed(t) and not self._tb_consume(channel):
            return False  # 처리율 초과 → 차단
        self._ticker_channel[t] = channel
        if self.router.subscribe(t):
            if self._ramp_active:
                self._ramp_admitted += 1
            self._enqueue(build_sub_message(self.protocol, t), priority)
            self.ack_state[t] = "pending"  # 구독 확인(ack) 대기
            self._sent_at[t] = self._now()
            self._resend[t] = 0
            return True
        return False

    def remove(self, ticker: str) -> bool:
        t = ticker.upper()
        if self.router.unsubscribe(t):
            # 구독 해지는 우선 처리(우선순위 큐 모드에서 신규 구독보다 앞당김).
            self._enqueue(build_unsub_message(self.protocol, t), priority=5)
            self.ack_state.pop(t, None)
            self._sent_at.pop(t, None)
            self._resend.pop(t, None)
            return True
        return False

    def drain_commands(self) -> list[dict]:
        """대기 중 sub/unsub 메시지 반환 후 비움(스트림이 WS 송신). PQ 모드는 우선순위 순서."""
        return self._dequeue_all()

    def parse_ack(self, msg: dict) -> str | None:
        """브로커 ack 메시지 → 해당 ticker acked 표시. 반환 ticker 또는 None."""
        if self.protocol == "kis":
            t = msg.get("body", {}).get("output", {}).get("tr_key") or msg.get("tr_key")
        else:
            t = msg.get("ack") or (msg.get("subscribed") if msg.get("type") == "ack" else None)
        if t and t.upper() in self.ack_state:
            self.ack_state[t.upper()] = "acked"
            self._cb_failures = 0        # 성공 → 서킷브레이커 리셋
            if self.cb_state == "half_open":
                self.cb_state = "closed"
            if self._aimd is not None:
                self._aimd.on_success()  # AIMD 가산증가 — 안정 시 처리율 상향
            return t.upper()
        return None

    def pending_acks(self) -> list[str]:
        """ack 미수신 종목 목록."""
        return [t for t, s in self.ack_state.items() if s == "pending"]

    def check_timeouts(self) -> list[dict]:
        """ack 타임아웃 재송신 — 지수 백오프 간격. max_resend 초과 시 failed + 서킷브레이커."""
        now = self._now()
        resends = []
        for t in self.pending_acks():
            attempts = self._resend.get(t, 0)
            # 지수 백오프: ack_timeout · 2^attempts
            interval = self._ack_timeout * (2 ** attempts)
            if now - self._sent_at.get(t, now) < interval:
                continue
            if attempts >= self._max_resend:
                self.ack_state[t] = "failed"
                if self._aimd is not None:
                    self._aimd.on_loss()          # AIMD 승법감소 — 손실(구독실패) 시 처리율 급감
                self.router.unsubscribe(t)        # 실패 종목 라우터 제거(재구독 가능)
                self._ticker_cb_open[t] = now     # 종목별 서킷 오픈
                # 채널별 실패 카운트 → 임계 초과 시 채널 서킷 오픈
                ch = self._ticker_channel.get(t, "default")
                self._channel_failures[ch] = self._channel_failures.get(ch, 0) + 1
                if self._channel_failures[ch] >= self._channel_threshold:
                    self._channel_open[ch] = now
                self._cb_failures += 1
                if self._cb_failures >= self._cb_threshold:
                    self.cb_state = "open"        # 전역 서킷 오픈
                    self._cb_opened_at = now
                continue
            self._resend[t] = attempts + 1
            self._sent_at[t] = now
            resends.append(build_sub_message(self.protocol, t))
        return resends

    def failed_subscriptions(self) -> list[str]:
        return [t for t, s in self.ack_state.items() if s == "failed"]
