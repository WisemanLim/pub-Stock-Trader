"""F3.1 멀티에이전트 오케스트레이터 — 4 에이전트 순차 협업.

  Scraper  → ingest 뉴스/시세 수집
  Analyst  → analysis 기술지표·예측 해석
  Portfolio→ 페르소나별 변동성·비중 산정
  Decision → 최종 시그널 (Claude 있으면 강화, 없으면 룰베이스)

각 외부 서비스 장애는 부분 degrade — 해당 에이전트 노트에 기록하고 진행.
"""
import httpx

from app.core.config import settings

# 페르소나별 포지션 한도 (F4.3 연계) + 손절 성향
# "scalp"/"safe" = 웹 UI 표준명. "scalper"/"day" = 하위호환 유지.
PERSONA_MAX_WEIGHT = {
    "scalp": 0.10,
    "scalper": 0.10,
    "day": 0.20,
    "swing": 0.30,
    "position": 0.40,
    "safe": 0.12,
}


def _get(url: str, timeout: float = 5.0) -> dict | None:
    try:
        r = httpx.get(url, timeout=timeout)
        if r.status_code == 200:
            return r.json()
    except Exception:
        return None
    return None


def _scraper(ticker: str) -> dict:
    price = _get(f"{settings.ingest_url}/market/price/{ticker}")
    return {"price": price}


def _analyst(ticker: str) -> dict:
    indicators = _get(f"{settings.analysis_url}/indicators/{ticker}")
    prediction = _get(f"{settings.analysis_url}/predict/{ticker}")
    return {"indicators": indicators, "prediction": prediction}


def _portfolio(persona: str, analyst_data: dict) -> dict:
    max_w = PERSONA_MAX_WEIGHT.get(persona, 0.20)
    ind = analyst_data.get("indicators") or {}
    atr = ind.get("atr")
    close = ind.get("close") or 0.0
    # ATR 변동성 클수록 비중 축소
    vol_factor = 1.0
    if atr and close:
        vol_ratio = atr / close
        vol_factor = max(0.3, 1.0 - vol_ratio * 5)
    return {"max_weight": max_w, "suggested_weight": round(max_w * vol_factor, 3)}


def _flow_agent(ticker: str) -> dict:
    """C-3: 수급 분석 에이전트 — 기관/외인 매수 방향성 해석."""
    from datetime import date, timedelta
    today = date.today()
    from_date = (today - timedelta(days=5)).strftime("%Y%m%d")
    to_date = today.strftime("%Y%m%d")
    flow = _get(f"{settings.ingest_url}/krx/investor-flow/{ticker}?from_date={from_date}&to_date={to_date}")
    if not flow:
        return {"available": False, "institutional_net": None, "foreign_net": None, "signal": "HOLD"}

    rows = flow.get("rows", [])
    if not rows:
        return {"available": False, "institutional_net": None, "foreign_net": None, "signal": "HOLD"}

    # 최근 3일 기관·외국인 순매수 합계
    inst_net = sum(r.get("institutional_net_vol", 0) or 0 for r in rows[:3])
    foreign_net = sum(r.get("foreign_net_vol", 0) or 0 for r in rows[:3])
    sig = "HOLD"
    if inst_net > 0 and foreign_net > 0:
        sig = "BUY"
    elif inst_net < 0 and foreign_net < 0:
        sig = "SELL"
    return {
        "available": True,
        "institutional_net": inst_net,
        "foreign_net": foreign_net,
        "signal": sig,
    }


def _alert_agent(ticker: str) -> dict:
    """C-4: 시장경보 에이전트 — 위험 경보 시 신호 하향 조정."""
    alerts = _get(f"{settings.ingest_url}/krx/market-alerts?ticker={ticker}")
    if not alerts:
        return {"alert_level": 0, "alert_name": None, "override": None}

    rows = alerts.get("alerts", [])
    if not rows:
        return {"alert_level": 0, "alert_name": None, "override": None}

    # 가장 높은 경보 레벨 선택
    level_map = {"투자주의": 1, "투자경고": 2, "투자위험": 3, "위험예고": 3, "정리매매": 4}
    max_level = 0
    max_name = None
    for row in rows:
        lvl = level_map.get(row.get("level", ""), 0)
        if lvl > max_level:
            max_level = lvl
            max_name = row.get("level")

    override: str | None = None
    if max_level >= 3:
        override = "SELL"  # 위험 → 강제 매도 신호
    elif max_level == 2:
        override = "HOLD"  # 경고 → 중립 강제
    return {"alert_level": max_level, "alert_name": max_name, "override": override}


def _decision(ticker: str, analyst: dict, portfolio: dict,
              flow: dict | None = None, alert: dict | None = None) -> dict:
    ind = analyst.get("indicators") or {}
    pred = analyst.get("prediction") or {}
    signal = ind.get("signal", "HOLD")

    # C-4: 시장경보 override 우선 적용
    if alert and alert.get("override"):
        signal = alert["override"]

    # C-3: 수급 신호 반영 (지표와 일치 시 신뢰도 상승, 불일치 시 하락)
    flow_signal = (flow or {}).get("signal", "HOLD")

    # 예측 방향과 지표 시그널 정합성 체크
    pred_up = False
    if pred.get("horizons"):
        ups = sum(1 for h in pred["horizons"] if h.get("direction") == "UP")
        pred_up = ups > len(pred["horizons"]) / 2

    confidence = 0.5
    if signal == "BUY" and pred_up:
        confidence = 0.8
    elif signal == "SELL" and not pred_up:
        confidence = 0.8
    elif signal == "HOLD":
        confidence = 0.5
    else:
        confidence = 0.4

    # C-3: 수급 동일 방향 → 신뢰도 +0.05
    if flow_signal == signal and signal != "HOLD":
        confidence = min(1.0, confidence + 0.05)
    elif flow_signal != "HOLD" and flow_signal != signal:
        confidence = max(0.0, confidence - 0.05)

    # C-4: 경보 레벨 존재 → 신뢰도 하향
    if alert and alert.get("alert_level", 0) >= 2:
        confidence = max(0.0, confidence - 0.10)

    weight = portfolio["suggested_weight"] if signal == "BUY" else 0.0
    alert_note = f", 경보={alert.get('alert_name','없음')}" if alert and alert.get("alert_level", 0) else ""
    flow_note = f", 수급={'BUY' if (flow or {}).get('institutional_net', 0) > 0 else 'SELL/중립'}" if flow and flow.get("available") else ""
    rationale = (
        f"지표 시그널={signal}, 예측방향={'UP' if pred_up else 'DOWN/혼조'}, "
        f"RSI={ind.get('rsi')}, 비중상한={portfolio['max_weight']}{flow_note}{alert_note}"
    )

    if settings.anthropic_api_key:
        rationale = _claude_rationale(ticker, ind, pred, signal) or rationale

    return {
        "signal": signal,
        "weight": round(weight, 3),
        "confidence": confidence,
        "rationale": rationale,
    }


def _claude_rationale(ticker: str, ind: dict, pred: dict, signal: str) -> str | None:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            system="너는 트레이딩 의사결정 에이전트다. 지표·예측만 근거로 간결한 매매 논리를 한국어 2문장으로.",
            messages=[{
                "role": "user",
                "content": f"{ticker} 지표={ind} 예측={pred} 시그널={signal}. 매매 논리?",
            }],
        )
        return msg.content[0].text
    except Exception:
        return None


def run_pipeline(ticker: str, persona: str) -> dict:
    scraper_data = _scraper(ticker)
    analyst_data = _analyst(ticker)
    portfolio_data = _portfolio(persona, analyst_data)
    # C-3: 수급 분석 에이전트, C-4: 시장경보 에이전트
    flow_data = _flow_agent(ticker)
    alert_data = _alert_agent(ticker)
    decision = _decision(ticker, analyst_data, portfolio_data, flow_data, alert_data)

    notes = [
        {
            "agent": "Scraper",
            "summary": "시세 수집 완료" if scraper_data.get("price") else "시세 수집 실패(degrade)",
            "data": scraper_data.get("price") or {},
        },
        {
            "agent": "Analyst",
            "summary": "기술지표·예측 해석" if analyst_data.get("indicators") else "분석 데이터 없음(degrade)",
            "data": {
                "signal": (analyst_data.get("indicators") or {}).get("signal"),
                "rsi": (analyst_data.get("indicators") or {}).get("rsi"),
                "vwap_20": (analyst_data.get("indicators") or {}).get("vwap_20"),
            },
        },
        {
            "agent": "Portfolio",
            "summary": f"페르소나 {persona} 비중 산정",
            "data": portfolio_data,
        },
        {
            "agent": "FlowAgent",
            "summary": f"수급 분석: 기관{'매수' if flow_data.get('institutional_net', 0) > 0 else '매도/중립'}" if flow_data.get("available") else "수급 데이터 없음(degrade)",
            "data": flow_data,
        },
        {
            "agent": "AlertAgent",
            "summary": f"시장경보 레벨{alert_data.get('alert_level', 0)}: {alert_data.get('alert_name') or '정상'}" + (f" → 시그널 {alert_data['override']}" if alert_data.get("override") else ""),
            "data": alert_data,
        },
        {
            "agent": "Decision",
            "summary": f"최종 시그널 {decision['signal']} (신뢰도 {decision['confidence']:.0%})",
            "data": {"confidence": decision["confidence"]},
        },
    ]
    return {"ticker": ticker, "persona": persona, "notes": notes, "decision": decision}
