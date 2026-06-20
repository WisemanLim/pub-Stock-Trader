"""F1.2 다종목 멀티플렉싱 시험."""
from unittest.mock import patch

from app.services.adaptive_flow import AIMDRateController
from app.services.broker_multiplex import (
    MultiplexRouter,
    SubscriptionManager,
    build_sub_message,
    build_subscribe_messages,
    build_unsub_message,
)


def test_subscribe_messages_generic():
    msgs = build_subscribe_messages("generic", "K", "S", ["005930", "000660", "035720"])
    assert len(msgs) == 3
    assert msgs[0]["action"] == "auth"          # 첫 메시지 인증
    assert msgs[1]["action"] == "subscribe"
    assert msgs[1]["subscribe"] == "000660"


def test_subscribe_messages_kis():
    msgs = build_subscribe_messages("kis", "APPR", "S", ["005930", "000660"])
    assert msgs[0]["header"]["approval_key"] == "APPR"
    assert msgs[1]["body"]["input"]["tr_key"] == "000660"


def test_subscribe_messages_empty():
    assert build_subscribe_messages("generic", "K", "S", []) == []


def test_router_dispatch_and_drain():
    r = MultiplexRouter()
    r.subscribe("005930")
    r.subscribe("000660")
    assert r.dispatch({"ticker": "005930", "price": 70000}) is True
    assert r.dispatch({"ticker": "000660", "price": 120000}) is True
    assert r.dispatch({"ticker": "035720", "price": 50000}) is False  # 미구독
    assert len(r.drain("005930")) == 1
    assert len(r.drain("005930")) == 0  # 비워짐


def test_router_case_insensitive():
    r = MultiplexRouter()
    r.subscribe("aapl")
    assert r.dispatch({"ticker": "AAPL", "price": 200}) is True


def test_dynamic_subscribe_unsubscribe():
    r = MultiplexRouter()
    assert r.subscribe("005930") is True
    assert r.subscribe("005930") is False     # 중복 추가
    assert r.is_subscribed("005930") is True
    assert r.unsubscribe("005930") is True
    assert r.is_subscribed("005930") is False
    assert r.unsubscribe("005930") is False   # 없는 것 해지
    assert r.dispatch({"ticker": "005930", "price": 1}) is False  # 해지 후 미라우팅


def test_sub_unsub_messages_generic():
    assert build_sub_message("generic", "005930")["action"] == "subscribe"
    assert build_unsub_message("generic", "005930")["action"] == "unsubscribe"


def test_sub_unsub_messages_kis():
    assert build_sub_message("kis", "005930")["header"]["tr_type"] == "1"
    assert build_unsub_message("kis", "005930")["header"]["tr_type"] == "2"


def test_subscription_manager_runtime():
    sm = SubscriptionManager("generic")
    assert sm.add("005930") is True
    assert sm.add("005930") is False        # 중복
    assert sm.add("000660") is True
    cmds = sm.drain_commands()
    assert len(cmds) == 2                    # 구독 2건 송신 대기
    assert all(c["action"] == "subscribe" for c in cmds)
    assert sm.drain_commands() == []         # 비워짐

    assert sm.remove("005930") is True
    cmds2 = sm.drain_commands()
    assert len(cmds2) == 1
    assert cmds2[0]["action"] == "unsubscribe"
    assert sm.router.is_subscribed("005930") is False
    assert sm.router.is_subscribed("000660") is True


def test_subscription_manager_kis_messages():
    sm = SubscriptionManager("kis")
    sm.add("005930")
    cmds = sm.drain_commands()
    assert cmds[0]["header"]["tr_type"] == "1"


def test_subscription_ack_generic():
    sm = SubscriptionManager("generic")
    sm.add("005930")
    sm.add("000660")
    assert set(sm.pending_acks()) == {"005930", "000660"}  # ack 대기
    # 브로커 ack 수신
    acked = sm.parse_ack({"type": "ack", "subscribed": "005930"})
    assert acked == "005930"
    assert sm.ack_state["005930"] == "acked"
    assert sm.pending_acks() == ["000660"]


def test_subscription_ack_kis():
    sm = SubscriptionManager("kis")
    sm.add("005930")
    acked = sm.parse_ack({"body": {"output": {"tr_key": "005930"}}})
    assert acked == "005930"
    assert sm.pending_acks() == []


def test_subscription_ack_unknown_ignored():
    sm = SubscriptionManager("generic")
    sm.add("005930")
    assert sm.parse_ack({"type": "ack", "subscribed": "999999"}) is None
    assert sm.pending_acks() == ["005930"]  # 변동 없음


class _Clock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t


def test_ack_timeout_resend():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=3, now_fn=clk)
    sm.add("005930")
    sm.drain_commands()
    # 타임아웃 전 → 재송신 없음
    clk.t = 3.0
    assert sm.check_timeouts() == []
    # 타임아웃 경과 → 재송신
    clk.t = 6.0
    rs = sm.check_timeouts()
    assert len(rs) == 1
    assert rs[0]["action"] == "subscribe"


def test_ack_resend_gives_up_after_max():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=2, now_fn=clk)
    sm.add("005930")
    # 지수 백오프 간격 초과하도록 큰 점프 반복
    for k in range(1, 6):
        clk.t += 10_000.0
        sm.check_timeouts()
    assert "005930" in sm.failed_subscriptions()  # max 초과 → 실패
    assert sm.pending_acks() == []


def test_exponential_backoff_interval():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=5, now_fn=clk)
    sm.add("005930")
    # attempts=0 → interval 5
    clk.t = 5.0
    assert len(sm.check_timeouts()) == 1
    # attempts=1 → interval 10, 6초 경과로는 부족
    clk.t = 11.0
    assert sm.check_timeouts() == []
    # 추가 경과 → interval 10 초과
    clk.t = 16.0
    assert len(sm.check_timeouts()) == 1


def test_circuit_breaker_opens_and_blocks():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=2, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA")
    sm.add("BBB")
    # 두 종목 모두 ack 없이 실패 → cb_failures 2 → open (cooldown 초과 전 즉시 확인)
    clk.t += 10_000.0
    sm.check_timeouts()   # 재송신(attempts=1)
    clk.t += 10_000.0
    sm.check_timeouts()   # 실패 → open
    assert sm.circuit_open() is True
    assert sm.add("CCC") is False  # 오픈 → 신규 구독 차단


def test_per_ticker_circuit_breaker():
    clk = _Clock(0.0)
    # 전역 threshold 높게(전역 오픈 회피), 종목별만 확인
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=99, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA")
    # AAA 실패시킴 → 종목별 서킷 오픈
    clk.t += 10_000.0
    sm.check_timeouts()  # resend
    clk.t += 10_000.0
    sm.check_timeouts()  # 실패 → ticker cb open
    assert sm.ticker_circuit_open("AAA") is True
    assert sm.add("AAA") is False         # 해당 종목 차단
    assert sm.add("BBB") is True          # 다른 종목은 정상
    assert sm.circuit_open() is False     # 전역은 닫힘


def test_per_ticker_cb_cooldown_release():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=99, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA")
    clk.t += 10_000.0
    sm.check_timeouts()
    clk.t += 10_000.0
    sm.check_timeouts()
    assert sm.ticker_circuit_open("AAA") is True
    clk.t += 31.0  # cooldown 경과
    assert sm.ticker_circuit_open("AAA") is False  # 자동 해제
    assert sm.add("AAA") is True


def test_half_open_probe_success_closes():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=1, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA")
    clk.t += 10_000.0
    sm.check_timeouts()
    clk.t += 10_000.0
    sm.check_timeouts()          # 전역 open
    assert sm.cb_state == "open"
    assert sm.probe() is None    # open 중 탐침 없음
    clk.t += 31.0
    sm.circuit_open()            # cooldown → half_open
    msg = sm.probe()
    assert msg is not None and msg["action"] == "subscribe"
    assert sm.probe() is None    # 탐침 진행중 → 중복 없음
    sm.probe_ack()               # 탐침 성공
    assert sm.cb_state == "closed"


def test_half_open_probe_fail_reopens():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=1, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA")
    clk.t += 10_000.0
    sm.check_timeouts()
    clk.t += 10_000.0
    sm.check_timeouts()
    clk.t += 31.0
    sm.circuit_open()            # half_open
    sm.probe()
    sm.probe_fail()              # 탐침 실패 → 재오픈
    assert sm.cb_state == "open"


def test_token_bucket_rate_limit():
    clk = _Clock(0.0)
    # rate 1/s, capacity 2 → 버스트 2건 후 차단
    sm = SubscriptionManager("generic", rate_limit=1.0, bucket_capacity=2.0, now_fn=clk)
    assert sm.add("AAA") is True
    assert sm.add("BBB") is True
    assert sm.add("CCC") is False   # 버킷 소진
    clk.t += 1.0                    # 1초 → 토큰 1 충전
    assert sm.add("CCC") is True
    assert sm.add("DDD") is False


def test_token_bucket_unlimited_default():
    sm = SubscriptionManager("generic")  # rate_limit=0 → 무제한
    for i in range(10):
        assert sm.add(f"T{i}") is True


def test_token_bucket_duplicate_no_consume():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", rate_limit=1.0, bucket_capacity=1.0, now_fn=clk)
    assert sm.add("AAA") is True
    assert sm.add("AAA") is False   # 중복(이미 구독) — 토큰 소비 X, subscribe False
    # 토큰은 1개 소비됨 → 신규는 차단
    assert sm.add("BBB") is False


def test_channel_token_buckets():
    clk = _Clock(0.0)
    # news 채널 1/s cap2, price 채널 무지정(전역 무제한)
    sm = SubscriptionManager("generic", channel_rates={"news": (1.0, 2.0)}, now_fn=clk)
    assert sm.add("A1", channel="news") is True
    assert sm.add("A2", channel="news") is True
    assert sm.add("A3", channel="news") is False   # news 버킷 소진
    # price 채널은 전역(무제한) → 허용
    assert sm.add("P1", channel="price") is True
    assert sm.add("P2", channel="price") is True
    clk.t += 1.0
    assert sm.add("A3", channel="news") is True     # news 토큰 충전


def test_channel_bucket_independent():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic",
                             channel_rates={"news": (1.0, 1.0), "macro": (1.0, 1.0)}, now_fn=clk)
    assert sm.add("N1", channel="news") is True
    assert sm.add("N2", channel="news") is False    # news 소진
    assert sm.add("M1", channel="macro") is True     # macro 독립 → 허용


def test_rate_ramp_gradual_admit():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=1, cb_cooldown=30.0, now_fn=clk)
    sm._ramp_step = 2
    sm._ramp_interval = 5.0
    sm.add("AAA")
    clk.t += 10_000.0
    sm.check_timeouts()
    clk.t += 10_000.0
    sm.check_timeouts()   # 전역 open
    clk.t += 31.0
    sm.circuit_open()     # half_open
    sm.probe()
    sm.probe_ack()        # 복구 → ramp 시작(한도 2)
    # 한도 2 → 2건 허용, 3번째 차단
    assert sm.add("T1") is True
    assert sm.add("T2") is True
    assert sm.add("T3") is False   # ramp 한도 초과
    # interval 경과 → 한도 증가
    clk.t += 6.0
    sm.ramp_tick()
    assert sm.add("T3") is True     # 한도 상향 후 허용


def test_ramp_inactive_allows_all():
    sm = SubscriptionManager("generic")
    assert sm.ramp_allows() is True   # ramp 비활성 → 항상 허용


def test_channel_circuit_breaker():
    clk = _Clock(0.0)
    # 채널 threshold=2, 전역 threshold 높게(전역 오픈 회피)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=99, channel_threshold=2, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA", channel="news")
    sm.add("BBB", channel="news")
    sm.add("CCC", channel="price")
    # news 채널 두 종목 실패 → 채널 서킷 오픈
    clk.t += 10_000.0
    sm.check_timeouts()  # resend
    clk.t += 10_000.0
    sm.check_timeouts()  # 실패 → news 채널 실패 2
    assert sm.channel_circuit_open("news") is True
    assert sm.add("DDD", channel="news") is False   # news 채널 차단
    assert sm.add("EEE", channel="price") is True    # price 채널 정상


def test_channel_cb_cooldown_release():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=99, channel_threshold=1, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA", channel="news")
    clk.t += 10_000.0
    sm.check_timeouts()
    clk.t += 10_000.0
    sm.check_timeouts()
    assert sm.channel_circuit_open("news") is True
    clk.t += 31.0
    assert sm.channel_circuit_open("news") is False  # cooldown 해제


def test_circuit_breaker_half_open_after_cooldown():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=1, cb_cooldown=30.0, now_fn=clk)
    sm.add("AAA")
    for _ in range(3):
        clk.t += 10_000.0
        sm.check_timeouts()
    assert sm.cb_state == "open"
    clk.t += 31.0  # cooldown 경과
    assert sm.circuit_open() is False  # half_open → 차단 해제
    assert sm.cb_state == "half_open"


def test_ack_received_stops_resend():
    clk = _Clock(0.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, now_fn=clk)
    sm.add("005930")
    sm.parse_ack({"type": "ack", "subscribed": "005930"})
    clk.t = 100.0
    assert sm.check_timeouts() == []  # acked → 재송신 없음


# ── 차수21: AIMD·우선순위큐·백프레셔 → SubscriptionManager 통합 ──

def test_aimd_drives_rate_up_on_ack():
    clk = _Clock(0.0)
    aimd = AIMDRateController(base_rate=5.0, ai_step=2.0, max_rate=100.0)
    sm = SubscriptionManager("generic", now_fn=clk, aimd=aimd)
    assert sm.current_rate() == 5.0
    sm.add("AAA")
    sm.parse_ack({"type": "ack", "subscribed": "AAA"})  # 성공 → 가산증가
    assert sm.current_rate() == 7.0


def test_aimd_drops_rate_on_subscription_failure():
    clk = _Clock(0.0)
    aimd = AIMDRateController(base_rate=10.0, md_factor=0.5, min_rate=1.0)
    sm = SubscriptionManager("generic", ack_timeout=5.0, max_resend=1,
                             cb_threshold=99, now_fn=clk, aimd=aimd)
    sm.add("AAA")
    assert sm.current_rate() == 10.0
    clk.t += 10_000.0
    sm.check_timeouts()   # resend (attempts=1)
    clk.t += 10_000.0
    sm.check_timeouts()   # give up → on_loss (승법감소)
    assert sm.current_rate() == 5.0


def test_aimd_rate_feeds_token_bucket():
    clk = _Clock(0.0)
    # rate 1/s 고정(ai_step 0), capacity 2 → 버스트 2건 후 차단(AIMD rate 가 버킷 구동)
    aimd = AIMDRateController(base_rate=1.0, ai_step=0.0, md_factor=0.5, min_rate=1.0, max_rate=1.0)
    sm = SubscriptionManager("generic", bucket_capacity=2.0, now_fn=clk, aimd=aimd)
    assert sm.add("A") is True
    assert sm.add("B") is True
    assert sm.add("C") is False    # AIMD rate 기반 버킷 소진
    clk.t += 1.0
    assert sm.add("C") is True     # 1초 → 토큰 1 충전


def test_priority_queue_orders_commands():
    sm = SubscriptionManager("generic", command_capacity=10)
    sm.add("LOW", priority=1)
    sm.add("HIGH", priority=9)
    sm.add("MID", priority=5)
    cmds = sm.drain_commands()
    assert [c["subscribe"] for c in cmds] == ["HIGH", "MID", "LOW"]


def test_unsubscribe_prioritized_over_subscribe():
    sm = SubscriptionManager("generic", command_capacity=10)
    sm.add("AAA", priority=0)        # 먼저 적재
    sm.add("BBB", priority=0)
    sm.drain_commands()             # 비움
    sm.add("CCC", priority=0)        # 신규 구독(우선순위 0)
    sm.remove("AAA")                 # 해지(우선순위 5) → 앞당김
    cmds = sm.drain_commands()
    assert cmds[0]["action"] == "unsubscribe"


def test_command_backpressure_watermark():
    sm = SubscriptionManager("generic", command_watermark=2)
    assert sm.command_backpressured() is False
    sm.add("A")
    assert sm.command_backpressured() is False
    sm.add("B")
    assert sm.command_backpressured() is True   # 워터마크 도달


def test_command_capacity_drops_lowest_priority():
    sm = SubscriptionManager("generic", command_capacity=2)
    sm.add("HI", priority=9)
    sm.add("MID", priority=5)
    sm.add("LO", priority=1)         # 용량 초과 → 최저 우선순위(LO) 명령 드롭
    assert sm.commands_dropped() == 1
    keys = {c["subscribe"] for c in sm.drain_commands()}
    assert keys == {"HI", "MID"}


def test_default_mode_unchanged_fifo():
    """aimd/pq 미지정(기본) → 기존 FIFO·무제한 동작 보존(하위호환)."""
    sm = SubscriptionManager("generic")
    sm.add("A")
    sm.add("B")
    assert [c["subscribe"] for c in sm.drain_commands()] == ["A", "B"]  # FIFO
    assert sm.command_backpressured() is False
    assert sm.commands_dropped() == 0
    assert sm.current_rate() == 0.0


def test_ws_feed_multi_simulated(client):
    with patch("app.services.broker_feed._fdr.get_price", return_value={"price": 70000.0}):
        with client.websocket_connect("/market/feed_multi/005930,000660") as ws:
            t1 = ws.receive_json()
            t2 = ws.receive_json()
            got = {t1["ticker"], t2["ticker"]}
            assert got == {"005930", "000660"}
            assert t1["source"] == "simulated"
