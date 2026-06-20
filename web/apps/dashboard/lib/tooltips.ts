/**
 * 대시보드 전체 툴팁 콘텐츠.
 * \n = 줄바꿈, 빈 줄(\n\n) = 단락 간격.
 */

export const TOOLTIPS = {
  // ── PERSONA ─────────────────────────────────────────────────────
  persona: {
    scalper: `(전략) 초단타 매매로 보유 기간은 수 초~수 분. 하루에도 수십~수백 번 거래하며 아주 작은 가격 변동(틱)을 이용해 수익을 쌓아가는 방식.
\n(특징) 거래 수수료와 슬리피지를 반드시 감안해야 하며, 고도의 집중력과 빠른 판단력이 필요. 자동화 매매에 가장 적합한 페르소나.
\n(파라미터) 비중 한도 5% · 손절폭 최소(0.5~1%) · 회전율 최대 · 일일한도 3%`,

    day: `(전략) 당일 장중에만 거래하고 오버나이트(장 마감 후 포지션 보유) 없이 모든 포지션을 당일 청산하는 방식.
\n(특징) 다음날 갭 상승·하락 리스크를 원천 차단. 당일 손익 한도 내에서 집중 운영. 뉴스·이벤트 드리븐 매매에 유리.
\n(파라미터) 비중 한도 8% · 당일 손익 한도 우선 적용 · 오버나이트 포지션 없음`,

    swing: `(전략) 수일에서 수주 동안 포지션을 보유하며 기술적 추세를 추종하는 방식. 본 시스템의 기본(default) 페르소나.
\n(특징) 단기·중기 이동평균 교차, RSI 과매수·과매도 구간을 핵심 신호로 활용. 표준 손절·트레일링 스탑 적용. 잦은 매매 없이 추세를 충분히 활용.
\n(파라미터) 비중 한도 10% · 트레일링 스탑 기본 활성 · 손절폭 2~3% · 일일한도 5%`,

    position: `(전략) 수주에서 수개월 이상 장기 보유하는 방식. 거시 지표와 펀더멘털 분석 비중이 가장 높음.
\n(특징) 단기 변동성을 넓은 손절폭으로 견뎌내며 중장기 추세를 추구. ESG·AI 기업보고서·거시 채널 17종을 종합 반영. 거래 빈도 최소.
\n(파라미터) 비중 한도 15% · 손절폭 최대 5~7% · 일일한도 7% · 거시 채널 17종 합성`,
  },

  // ── MENU ────────────────────────────────────────────────────────
  menu: {
    dashboard: `실시간 시세·기술지표·에이전트 결정을 통합한 메인 화면.
캔들 차트, RSI/MACD/Bollinger, 투자자 수급 동향, 리스크 상태를 한눈에 확인.`,

    portfolio: `현재 보유 종목별 수익·손익·비중을 확인하는 화면.
가상 체결(Paper Trading) 기반 포트폴리오 현황, 수익곡선(Equity Curve), 벤치마크 대비 알파 분석 제공.`,

    strategy: `자동매매 전략 설정 및 관리 화면.
SMA 교차·RSI 임계값·MACD 등 규칙 기반 전략과 DQN·PPO·A2C 강화학습 전략을 구성하고 백테스트로 검증.`,

    risk: `손절·한도·리스크 지표 모니터링 화면.
Stop-Loss · Trailing Stop · 일일 손실 한도 · 포지션 한도 설정과 Rust 기반 Fail-Safe 엔진 상태 확인.`,

    backtest: `과거 데이터로 전략 성과를 검증하는 화면.
SMA·RSI·MACD 규칙 전략 + DQN·C51·QR-DQN·PPO·A2C RL 전략 백테스트.
Sharpe Ratio · MDD · 최대 연속 손실 · Fama-French 팩터회귀 등 성과 지표 제공.`,

    agents: `AI 멀티에이전트 상태 및 결정 현황 화면.
Scraper(뉴스 수집) · Analyst(지표 분석) · Portfolio(비중 결정) · Decision(최종 신호) 에이전트의 실시간 상태와 자가교정 루프 모니터링.`,
  },

  // ── SERVICE STATUS ───────────────────────────────────────────────
  service: {
    ingest: `ingest 서비스 (포트 8003)
실시간 시세·OHLCV·호가창·뉴스 수집 담당. Python/FastAPI.
FinanceDataReader(KRX·US 종목), KRX OPEN API(F1.5), 브로커 WebSocket 연동.
Redis Streams로 tick 데이터 발행 → 하위 서비스 구독.`,

    analysis: `analysis 서비스 (포트 8001)
기술지표·시계열 예측·스크리너·백테스팅 담당. Python/FastAPI.
RSI·MACD·Bollinger·ATR·EMA·SMA 계산.
멀티변량 거시 채널 17종 + FinBERT 감성 분석.
강화학습 백테스팅(DQN·C51·QR-DQN·PPO·A2C).`,

    agents: `agents 서비스 (포트 8004)
AI 멀티에이전트·RAG·알림·양방향 제어 담당. Python/FastAPI.
Scraper → Analyst → Portfolio → Decision 파이프라인.
자가교정 루프: 전략 드리프트 감지 시 HOLD 강등.
Telegram/Discord 웹훅 알림 + 봇 중지·긴급청산 원격 제어.`,

    risk: `risk-engine 서비스 (포트 3001)
Stop-Loss·Trailing Stop·일일한도·Fail-Safe 리스크 엔진. Rust/Axum.
가상 체결(Paper Trading) 원장 관리 — 다종목·계정 다중화.
Fama-French 5요인·Newey-West HAC 팩터회귀 + 동반행렬 안정성 사영.`,
  },

  // ── INDICATORS ──────────────────────────────────────────────────
  indicator: {
    rsi: `RSI (Relative Strength Index, 상대강도지수)
\n(계산) 14일 기준: 상승폭 평균 / (상승폭 + 하락폭) 평균 × 100
\n(해석)
· 30 이하 → 과매도. 반등 가능성 (매수 신호 고려)
· 70 이상 → 과매수. 조정 가능성 (매도 신호 고려)
· 50 근방 → 중립 추세
· 50 상향 돌파 → 상승 추세 전환 시그널`,

    macd: `MACD (Moving Average Convergence/Divergence)
\n(계산) 12일 EMA − 26일 EMA
\n(해석)
· 양수 → 단기 추세가 장기보다 강. 상승 국면
· 음수 → 단기 추세가 장기보다 약. 하락 국면
· Signal선 상향 돌파 → 매수 신호 (골든 크로스)
· Signal선 하향 돌파 → 매도 신호 (데드 크로스)`,

    macdSignal: `MACD Signal선 (9일 EMA)
\nMACD 값의 9일 지수이동평균.
\n(해석)
· MACD가 Signal을 상향 돌파 → 매수 신호
· MACD가 Signal을 하향 돌파 → 매도 신호
· MACD − Signal = Histogram (추세 강도)
· Histogram 양전환 → 상승 모멘텀 강화`,

    atr: `ATR (Average True Range, 평균 실제 범위)
\n(계산) 14일 기준. True Range = max(고가-저가, |고가-전종가|, |저가-전종가|)
\n(해석)
· 높을수록 → 변동성 크고 리스크 높음
· 낮을수록 → 가격 안정적
\n(활용) 손절 간격 설정에 사용 (예: 2×ATR 손절).
변동성 급등 시 포지션 비중 축소 신호.`,

    ema20: `EMA (Exponential Moving Average, 지수이동평균) — 20일
\n최근 가격에 더 높은 가중치를 부여한 이동평균. SMA보다 빠르게 반응.
\n(해석)
· 주가 > EMA → 단기 상승 추세
· 주가 < EMA → 단기 하락 추세
· EMA 자체 기울기 → 추세 방향 확인`,

    sma20: `SMA (Simple Moving Average, 단순이동평균) — 20일
\n최근 20일 종가의 산술평균. 추세 방향과 지지·저항선 확인에 가장 널리 사용.
\n(구분)
· 단기 5·10일 — 초단기 추세
· 중기 20·60일 — 주력 추세 (이 값)
· 장기 120·200일 — 대세 방향
\n(활용) 단기 SMA가 장기 SMA 상향 돌파 → 황금 교차 (골든 크로스)`,

    bollinger: `볼린저 밴드 (Bollinger Bands)
\n(계산) 20일 SMA ± 2 표준편차로 상·중·하단 밴드 구성
\n(해석)
· 상단 돌파 → 과매수 구간. 강한 상승 또는 조정 신호
· 하단 이탈 → 과매도 구간. 반등 또는 추가 하락 신호
· 밴드 수축(Squeeze) → 큰 방향성 돌파 예고
· 밴드 확장 → 현재 고변동성 상태`,

    signal: `지표 시그널 (Technical Signal)
\nRSI · MACD · Bollinger Band 등 기술지표를 종합 분석한 시스템 신호.
\n(신호 종류)
· BUY → 매수 조건 충족 (과매도·상향 교차·하단 반등 등)
· SELL → 매도 조건 충족 (과매수·하향 교차·상단 돌파 등)
· HOLD → 명확한 방향성 신호 없음. 관망 권장
\n⚠ 복합 지표 종합치. 최종 결정은 에이전트 시그널과 함께 확인 권장.`,

    agentDecision: `에이전트 최종 결정 (AI Multi-Agent Decision)
\nScraper · Analyst · Portfolio · Decision 4개 에이전트가 협력해 산출한 최종 매매 신호.
\n(에이전트 역할)
· Scraper: 최신 뉴스·공시 수집 + 감성 분석
· Analyst: 기술지표 + 거시 채널 17종 분석
· Portfolio: 현재 비중 고려 + 목표 비중 산출
· Decision: 위 3개 결과를 종합한 최종 신호
\n(비중) 포트폴리오 대비 권장 진입 비율 (0~100%)
(신뢰도) 에이전트 간 합의 수준 (0~100%)
\n자가교정: 과도한 반전·저신뢰·비중 위반 감지 시 자동 HOLD 교정`,

    currentPrice: `현재가 (Latest Price)
\ningest 서비스가 FinanceDataReader를 통해 수집한 최신 종가.
\n⚠ 현재 EOD(End of Day) 기준 데이터.
KRX 장중 실시간 데이터는 Phase A (KIS 브로커 WebSocket 연동) 예정.
\nBFF(:3002)를 통해 5초마다 폴링 갱신. 서비스 미기동 시 '—' 표시.`,
  },

  // ── RISK ────────────────────────────────────────────────────────
  risk: {
    stopLoss: `Stop-Loss (손절매)
\n설정 손실률 이하로 가격이 하락하면 자동 매도하여 손실 확대를 방지.
\n(예시) 매수가 70,000원 × (-2%) = 68,600원 이하 도달 시 자동 청산
\n(주의)
· 갭 하락 시 설정가보다 낮은 가격에 체결 가능 (슬리피지)
· Rust 기반 리스크 엔진이 실시간 모니터링
· Trailing Stop과 함께 사용 시 이익 보호 효과 극대화`,

    dailyLimit: `일일 손실 한도 (Daily Loss Limit)
\n하루 총 실현 손실이 포트폴리오의 지정 비율(기본 -5%)을 초과하면 당일 신규 진입 전면 차단.
\n(주의)
· 기존 보유 포지션은 유지 (강제 청산과 다름)
· 리셋: 다음 영업일 장 시작 시 자동 초기화
· 연속 손실 방지를 위한 쿨다운 메커니즘
\n(페르소나별 기본값)
스캘퍼/데이 3% · 스윙 5% · 포지션 7%`,

    positionLimit: `최대 포지션 한도 (Max Position Size)
\n단일 종목에 포트폴리오 전체 대비 최대 비율까지만 진입 허용.
\n(페르소나별 기본값)
· 스캘퍼: 5% — 극소 비중, 리스크 분산
· 데이: 8% — 당일 청산 전제의 중간 비중
· 스윙: 10% — 표준 비중 (기본값)
· 포지션: 15% — 장기 확신 포지션 허용
\n⚠ 한도 초과 주문은 리스크 엔진이 즉시 거부 (Fail-Safe).`,
  },

  // ── PANELS ──────────────────────────────────────────────────────
  panel: {
    candleChart: `캔들 차트 (OHLCV Candlestick Chart)
\nOpen(시가)·High(고가)·Low(저가)·Close(종가)·Volume(거래량) 일봉 차트.
\n(색상)
· 초록 캔들 → 양봉 (종가 > 시가, 상승)
· 빨간 캔들 → 음봉 (종가 < 시가, 하락)
\n(구성)
· 몸통(Body): 시가~종가 구간
· 위꼬리(Upper Wick): 고가까지의 범위
· 아래꼬리(Lower Wick): 저가까지의 범위
\n마우스 오버 → 해당 봉의 OHLCV + 등락률 툴팁 표시.`,

    indicators: `기술지표 패널 (Technical Indicators)
\nRSI · MACD · Signal · ATR · EMA · SMA 등 가격·거래량 기반 분석 지표.
\n지표들을 종합 분석하여 '지표 시그널'(BUY/SELL/HOLD)을 산출.
analysis 서비스(포트 8001)에서 계산 후 BFF를 통해 전달.
\n(지표별 역할)
· RSI/Bollinger: 과매수·과매도 판단
· MACD/Signal: 추세 방향 및 모멘텀
· ATR: 변동성 (손절 간격 계산에 활용)
· EMA/SMA: 추세 방향 확인`,

    flow: `수급 동향 (Investor Flow)
\n기관·외국인·개인 투자자의 일별 순매수/순매도 흐름.
\n(해석)
· 기관 순매수 지속 → 상승 모멘텀 지지
· 외국인 순매수 전환 → 중장기 상승 신호
· 개인만 순매수(기관·외인 매도) → 고점 주의
\n⚠ KRX OPEN API (stk_invsr_trd_by_isu) Phase A 연동 예정.
현재 표시값은 예시 데이터.`,

    riskStatus: `리스크 상태 (Risk Engine Status)
\nStop-Loss · 일일한도 · 포지션 한도의 현재 설정값과 활성화 여부.
\nRust/Axum 기반 리스크 엔진(포트 3001)이 실시간 모니터링.
한도 초과 시 Fail-Safe 작동 → 신규 주문 자동 차단.
\n(상태 표시)
· 초록 점 → 활성 (정상 모니터링 중)
· 회색 점 → 비활성 (수동 설정 필요)`,

    marketAlert: `시장경보 (KRX Market Surveillance)
\nKRX 이상 거래 감시 시스템이 지정한 투자 경보 종목 현황.
\n(단계별 의미)
· 투자주의 → 단기 급등락, 이상 거래량 감지
· 투자경고 → 투자주의 지속 또는 반복 이상 거래
· 투자위험 → 상장폐지 가능성, 중대 부실 우려
\n⚠ 경보 지정 종목 자동 진입 차단 기능 Phase B 예정.`,

    shortSelling: `공매도 현황 (Short Selling Statistics)
\n당일 공매도 비율 및 대차잔고(빌린 주식) 추이.
\n(해석)
· 공매도 비율 급등 → 시장의 하락 베팅 증가
· 대차잔고 급증 → 향후 공매도 물량 출회 가능성
· 잔고 급감(숏 커버링) → 단기 상승 압력
\n⚠ KRX OPEN API 연동 Phase B 예정. 현재 미구현.`,

    position: `포지션 요약 (Position Summary)
\n현재 보유 종목, 평균 매수가, 평가 손익 현황.
\n(현재 모드) 가상 체결(Paper Trading) — 실제 자금 거래 없음.
매매 내역은 risk-engine(포트 3001)의 가상 원장(Ledger)에 기록.
\n(실거래 연동) KIS Open API 실주문 연동 Phase D 예정.
SIMULATION 모드에서도 수수료·슬리피지 시뮬레이션 포함.`,
  },

  // ── INVESTOR FLOW ROWS ──────────────────────────────────────────
  flow: {
    institution: `기관 투자자 순매수 (Institutional Net Buy)
\n자산운용사·투자신탁·보험·연기금·은행 등 기관 투자자의 일별 순매수 금액.
\n(해석)
· 기관 연속 순매수 → 중장기 상승 모멘텀 지지
· 기관 대규모 매도 전환 → 추세 약화 신호
· 기관과 외국인 동시 매도 → 강한 하락 압력
\n출처: KRX OPEN API stk_invsr_trd_by_isu (Phase A 연동 예정)`,

    foreign: `외국인 투자자 순매수 (Foreign Investor Net Buy)
\n국내 증시에 투자하는 외국인(개인·기관 포함) 투자자의 일별 순매수 금액.
\n(해석)
· 외국인 연속 순매수 → KOSPI 중장기 상승 신호
· 외국인 대규모 이탈 → 원화 약세·증시 하락 동반 가능
· 외국인 보유 비중 높은 종목일수록 환율 영향 민감
\n출처: KRX OPEN API stk_invsr_trd_by_isu (Phase A 연동 예정)`,

    individual: `개인 투자자 순매수 (Individual/Retail Net Buy)
\n개인(소매) 투자자의 일별 순매수 금액.
\n(해석)
· 개인만 순매수(기관·외인 쌍매도) → 주가 상단 부근 경고 신호
· 개인 순매도(기관·외인 매수) → 저점 형성 가능성
· '개인 역발상 지표'로도 활용
\n출처: KRX OPEN API stk_invsr_trd_by_isu (Phase A 연동 예정)`,
  },

  // ── MISC ────────────────────────────────────────────────────────
  misc: {
    kospi: `KOSPI (Korea Composite Stock Price Index)
\n한국거래소(KRX) 유가증권시장에 상장된 전체 종목을 포함하는 대한민국 대표 주가지수.
기준 시가총액 대비 현재 시가총액의 비율로 산출.
\n삼성전자·SK하이닉스·POSCO 등 대형주 위주. 1980년 1월 4일 기준 100pt.`,

    persona: `페르소나 (Trading Persona)
\n트레이딩 스타일을 나타내는 분류. 보유 기간·리스크 허용 범위·매매 빈도에 따라 구분.
\n스캘퍼(수 초~분) · 데이(당일 청산) · 스윙(수일~수주, 기본값) · 포지션(수주~수개월)
\n선택한 페르소나에 따라 손절폭·비중 한도·에이전트 결정 임계값이 자동으로 조정됨.`,
  },
} as const;
