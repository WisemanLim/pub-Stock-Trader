"""검색 컨텍스트 기반 답변 생성 — 환각 차단 (F3.2).

ANTHROPIC_API_KEY 있으면 Claude 호출, 없으면 추출형 fallback.
어느 경로든 '검색된 컨텍스트 밖 주장 금지' 원칙 유지.
"""
from app.core.config import settings


def _grounded(answer: str, sources: list[dict]) -> bool:
    """답변 토큰이 컨텍스트에 실제 등장하는지로 grounded 판정."""
    if not sources:
        return False
    ctx = " ".join(s["content"].lower() for s in sources)
    ans_tokens = [t for t in answer.lower().split() if len(t) > 2]
    if not ans_tokens:
        return False
    hits = sum(1 for t in ans_tokens if t in ctx)
    return hits / len(ans_tokens) >= 0.5


def answer(query: str, sources: list[dict]) -> tuple[str, bool]:
    if not sources:
        return ("검색된 근거 문서가 없어 답변할 수 없습니다. (환각 차단)", False)

    if settings.anthropic_api_key:
        try:
            return _claude_answer(query, sources)
        except Exception:
            pass  # API 실패 시 추출형 fallback

    # 추출형 fallback — 최상위 근거 발췌 (컨텍스트 밖 주장 없음)
    top = sources[0]["content"]
    text = f"근거 기반 요약: {top[:300]}"
    return (text, _grounded(text, sources))


def _claude_answer(query: str, sources: list[dict]) -> tuple[str, bool]:
    import anthropic

    ctx = "\n\n".join(f"[{s['id']}] {s['content']}" for s in sources)
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        system=(
            "너는 금융 분석 어시스턴트다. 반드시 제공된 컨텍스트만 근거로 답하라. "
            "컨텍스트에 없는 정보는 '근거 없음'이라고 말하라."
        ),
        messages=[{
            "role": "user",
            "content": f"컨텍스트:\n{ctx}\n\n질문: {query}",
        }],
    )
    text = msg.content[0].text
    return (text, _grounded(text, sources))
