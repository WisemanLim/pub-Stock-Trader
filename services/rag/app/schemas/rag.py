"""F3.2 Quant RAG 스키마."""
from pydantic import BaseModel


class Document(BaseModel):
    id: str
    content: str
    meta: dict = {}


class IngestRequest(BaseModel):
    documents: list[Document]


class IngestResponse(BaseModel):
    ingested: int
    total: int


class QueryRequest(BaseModel):
    query: str
    k: int = 3


class RetrievedDoc(BaseModel):
    id: str
    content: str
    meta: dict
    score: float


class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: list[RetrievedDoc]
    grounded: bool


class EvalRequest(BaseModel):
    query: str
    answer: str
    k: int = 3


class EvalResponse(BaseModel):
    query: str
    groundedness: float
    context_recall: float
    sources_used: int
