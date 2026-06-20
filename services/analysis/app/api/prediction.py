"""F2.2 시계열 예측 API — 선형회귀 / LSTM / Transformer + 사전학습·스케줄 재학습."""
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

from app.schemas.prediction import PredictionResponse, TrainResponse
from app.services.predictor import predict

router = APIRouter(prefix="/predict", tags=["prediction"])


class RetrainRequest(BaseModel):
    tickers: list[str]
    arch: str = "lstm"          # lstm | transformer
    max_age_hours: float = 24.0


@router.post("/{ticker}/train", response_model=TrainResponse)
async def train_model_endpoint(ticker: str, arch: str = "lstm", epochs: int = 60, days: int = 365) -> TrainResponse:
    """사전학습 → 체크포인트 저장. 별도 프로세스 오프로드(이벤트 루프 비블로킹)."""
    from app.core.offload import run_training

    try:
        info = await run_training(
            "app.services.lstm_model", "train_and_save",
            ticker=ticker.upper(), arch=arch, epochs=epochs, days=days,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TrainResponse(**info)


@router.post("/retrain")
async def scheduled_retrain_endpoint(req: RetrainRequest) -> dict:
    """스케줄 재학습 — stale 체크포인트만 재학습. 크론에서 주기 호출 가정. 별도 프로세스 오프로드."""
    from app.core.offload import run_training

    try:
        results = await run_training(
            "app.services.lstm_model", "scheduled_retrain",
            tickers=req.tickers, arch=req.arch, max_age_hours=req.max_age_hours,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"arch": req.arch, "results": results}


@router.get("/{ticker}", response_model=PredictionResponse)
async def get_prediction(ticker: str, model: str = "linear") -> PredictionResponse:
    """방향성 예측. model=linear(기본,빠름) | lstm | transformer.

    lstm/transformer(torch)는 별도 프로세스 오프로드(이벤트 루프 비블로킹). linear 는 경량 인프로세스.
    """
    try:
        if model in ("lstm", "transformer"):
            from app.core.offload import run_training
            data = await run_training(
                "app.services.lstm_model", "predict_forecast",
                ticker=ticker.upper(), arch=model,
            )
        else:
            data = predict(ticker.upper())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return PredictionResponse(**data)
