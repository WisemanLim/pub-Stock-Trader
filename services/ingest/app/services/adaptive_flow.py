"""F1.2 적응형 흐름제어 — AIMD 처리율 + 우선순위 큐 + 백프레셔.

채널별 토큰버킷(broker_multiplex) 위 고도화 단계. 순수 로직 → 결정적·시험 가능.

- AIMDRateController: 성공 시 additive-increase, 손실(타임아웃/드롭) 시 multiplicative-decrease.
  TCP 혼잡제어와 동형. 하한·상한 클램프. 토큰버킷 rate 를 동적 조정하는 데 사용.
- PriorityCommandQueue: 우선순위(높을수록 먼저) + 동일 우선순위 FIFO. 백프레셔 워터마크 초과 시
  저우선 항목부터 드롭(과부하 시 중요 구독 보호).
- now_fn 주입으로 시간 결정적(테스트).
"""
import heapq


class AIMDRateController:
    """AIMD 적응형 처리율 — 성공=+ai_step, 손실=×md_factor. [min_rate, max_rate] 클램프."""

    def __init__(
        self,
        base_rate: float,
        ai_step: float = 1.0,
        md_factor: float = 0.5,
        min_rate: float = 1.0,
        max_rate: float = 100.0,
    ) -> None:
        if not (0.0 < md_factor < 1.0):
            raise ValueError("md_factor must be in (0,1)")
        self._ai_step = ai_step
        self._md_factor = md_factor
        self._min = min_rate
        self._max = max_rate
        self._rate = self._clamp(base_rate)

    def _clamp(self, r: float) -> float:
        return max(self._min, min(self._max, r))

    def on_success(self) -> float:
        """선형 증가 — 안정 구간에서 점진 상향."""
        self._rate = self._clamp(self._rate + self._ai_step)
        return self._rate

    def on_loss(self) -> float:
        """승법 감소 — 혼잡/손실 감지 시 급감(보수적)."""
        self._rate = self._clamp(self._rate * self._md_factor)
        return self._rate

    def current_rate(self) -> float:
        return self._rate


class PriorityCommandQueue:
    """우선순위 명령 큐 — 높은 priority 먼저, 동일 priority 는 삽입순(FIFO).

    백프레셔: len ≥ high_watermark 면 backpressured. 용량(capacity) 초과 push 시
    최저 우선순위(가장 늦게 처리될) 항목을 드롭하고 그 항목 반환(드롭 회계).
    """

    def __init__(self, capacity: int = 0, high_watermark: int = 0) -> None:
        # capacity 0 = 무제한. high_watermark 0 = capacity 기준(없으면 백프레셔 비활성).
        self._cap = capacity
        self._hw = high_watermark
        self._heap: list[tuple] = []
        self._seq = 0  # FIFO tie-breaker(삽입순)
        self.dropped = 0

    def __len__(self) -> int:
        return len(self._heap)

    def push(self, item, priority: int = 0):
        """항목 적재. 용량 초과 시 최저 우선순위 항목 드롭 후 반환(없으면 None)."""
        # heapq 는 최소힙 → (-priority) 로 높은 우선순위를 먼저 pop.
        heapq.heappush(self._heap, (-priority, self._seq, item))
        self._seq += 1
        if self._cap and len(self._heap) > self._cap:
            return self._drop_lowest()
        return None

    def _drop_lowest(self):
        """최저 우선순위(동일 시 가장 늦게 삽입) 1건 제거 후 반환."""
        if not self._heap:
            return None
        # 최저 = max (-priority, seq) → 우선순위 낮고 seq 큰 것.
        victim = max(self._heap)
        self._heap.remove(victim)
        heapq.heapify(self._heap)
        self.dropped += 1
        return victim[2]

    def pop(self):
        """최고 우선순위 항목 반환. 비었으면 None."""
        if not self._heap:
            return None
        return heapq.heappop(self._heap)[2]

    def is_backpressured(self) -> bool:
        """백프레셔 활성 여부 — 큐 적체가 워터마크 도달."""
        wm = self._hw or self._cap
        if not wm:
            return False
        return len(self._heap) >= wm

    def drain(self) -> list:
        """우선순위 순서대로 전량 반환 후 비움."""
        out = []
        while self._heap:
            out.append(self.pop())
        return out
