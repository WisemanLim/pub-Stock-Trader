"""F2.2 시계열 예측 스키마."""
from pydantic import BaseModel


class PredictionHorizon(BaseModel):
    horizon: str
    predicted_price: float
    direction: str
    confidence: float


class PredictionResponse(BaseModel):
    ticker: str
    current_price: float
    model: str
    horizons: list[PredictionHorizon]
    weights_source: str | None = None  # lstm: "checkpoint" | "on-the-fly"
    features: list[str] | None = None  # 멀티변량 입력 피처(close·volume·rsi)


class TrainResponse(BaseModel):
    ticker: str
    arch: str
    checkpoint: str
    train_loss: float
    samples: int
    epochs: int
