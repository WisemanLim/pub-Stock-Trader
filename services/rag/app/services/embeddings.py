"""로컬 결정적 임베딩 — 토큰 해시 BoW (외부 API 불요, 테스트 가능).

운영 시 교체 지점: 이 함수를 sentence-transformers / Anthropic embeddings 로 대체.
차원·정규화 인터페이스만 유지하면 vector_store 변경 불필요.
"""
import math
import re

DIM = 256
_TOKEN = re.compile(r"[A-Za-z가-힣0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def embed(text: str) -> list[float]:
    vec = [0.0] * DIM
    for tok in _tokens(text):
        idx = hash(tok) % DIM
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))
