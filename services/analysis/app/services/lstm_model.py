"""F2.2 시계열 예측 — PyTorch LSTM / Transformer. 사전학습 체크포인트 + 스케줄 재학습.

arch: "lstm" | "transformer". train_and_save → 체크포인트(.pt, lo/hi·trained_at 보존).
predict_forecast → 체크포인트 로딩(없으면 즉석학습). needs_retrain/scheduled_retrain →
체크포인트 신선도(trained_at) 기반 스케줄 재학습(크론/엔드포인트 트리거).
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import FinanceDataReader as fdr
import numpy as np
import torch
import torch.nn as nn

from app.services.backtest import _ema, _rsi

torch.set_num_threads(1)

WINDOW = 10
HIDDEN = 16
EPOCHS = 60
SEED = 42
ARCHS = ("lstm", "transformer")
# 멀티변량 입력 (close = 타깃, col 0). macro·news 는 provider 미설정 시 중립(0).
FEATURES = ("close", "volume", "rsi", "macd_hist", "macro", "news")

# 외부 채널 provider 훅 — (ticker, length) → np.ndarray. 미설정 시 중립 0 채널.
# 운영: macro = 거시지표(금리·환율·지수), news = 뉴스 센티먼트 점수 시계열 주입.
_macro_provider = None  # Callable[[str, int], np.ndarray] | None
_news_provider = None


def set_channel_providers(macro=None, news=None) -> None:
    """거시·뉴스 채널 데이터 공급자 등록(테스트/운영 주입)."""
    global _macro_provider, _news_provider
    _macro_provider = macro
    _news_provider = news


def _channel(provider, ticker: str, length: int) -> np.ndarray:
    if provider is None:
        return np.zeros(length, dtype=float)
    arr = np.asarray(provider(ticker, length), dtype=float)
    if arr.shape[0] != length:  # 길이 불일치 → 중립 폴백
        return np.zeros(length, dtype=float)
    return arr

MODEL_DIR = Path(__file__).resolve().parents[2] / "models"


class _LSTM(nn.Module):
    def __init__(self, n_features: int = 1, hidden: int = HIDDEN) -> None:
        super().__init__()
        self.lstm = nn.LSTM(input_size=n_features, hidden_size=hidden, num_layers=1, batch_first=True)
        self.fc = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.fc(out[:, -1, :])


class _Transformer(nn.Module):
    """경량 Transformer 인코더 — 멀티변량 시퀀스 → 다음 종가 회귀."""

    def __init__(self, n_features: int = 1, d_model: int = 16, nhead: int = 2, layers: int = 1, window: int = WINDOW) -> None:
        super().__init__()
        self.embed = nn.Linear(n_features, d_model)
        self.pos = nn.Parameter(torch.zeros(1, window, d_model))
        enc_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=d_model * 2,
            batch_first=True, dropout=0.0,
        )
        self.encoder = nn.TransformerEncoder(enc_layer, num_layers=layers)
        self.fc = nn.Linear(d_model, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.embed(x) + self.pos[:, : x.size(1), :]
        h = self.encoder(h)
        return self.fc(h[:, -1, :])


def _build_model(arch: str, n_features: int) -> nn.Module:
    if arch == "transformer":
        return _Transformer(n_features=n_features)
    return _LSTM(n_features=n_features)


def _load_features(ticker: str, days: int = 180) -> np.ndarray:
    """멀티변량 행렬 (T, F): [close, volume, rsi]. RSI warmup 구간 제거."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    df = fdr.DataReader(ticker, start.strftime("%Y-%m-%d"))
    if df.empty:
        raise ValueError(f"No data for ticker: {ticker}")
    close = df["Close"].astype(float).to_numpy()
    volume = (df["Volume"].astype(float).to_numpy() if "Volume" in df.columns
              else np.zeros_like(close))
    rsi = _rsi(close, 14)
    # MACD 히스토그램 (종가 기반)
    macd = _ema(close, 12) - _ema(close, 26)
    macd_hist = macd - _ema(macd, 9)
    n = len(close)
    macro = _channel(_macro_provider, ticker, n)
    news = _channel(_news_provider, ticker, n)
    mat = np.column_stack([close, volume, rsi, macd_hist, macro, news])
    # RSI NaN(초기 14) 제거
    mask = ~np.isnan(mat).any(axis=1)
    return mat[mask]


def _normalize(mat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """열별 min-max. 반환 (norm, lo[F], hi[F])."""
    lo = mat.min(axis=0)
    hi = mat.max(axis=0)
    rng = np.where(hi > lo, hi - lo, 1.0)
    return (mat - lo) / rng, lo, hi


def _make_sequences(norm: np.ndarray, window: int) -> tuple[torch.Tensor, torch.Tensor]:
    """x (N, window, F), y (N,1) = 다음 스텝 종가(col 0, 정규화)."""
    xs, ys = [], []
    for i in range(len(norm) - window):
        xs.append(norm[i : i + window])
        ys.append(norm[i + window, 0])  # close 타깃
    x = torch.tensor(np.array(xs), dtype=torch.float32)
    y = torch.tensor(np.array(ys), dtype=torch.float32).unsqueeze(-1)
    return x, y


def _ckpt_path(ticker: str, arch: str) -> Path:
    return MODEL_DIR / f"{arch}_{ticker}.pt"


def _train(mat: np.ndarray, arch: str, epochs: int) -> tuple[nn.Module, np.ndarray, np.ndarray, float]:
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    norm, lo, hi = _normalize(mat)
    x, y = _make_sequences(norm, WINDOW)

    model = _build_model(arch, n_features=mat.shape[1])
    opt = torch.optim.Adam(model.parameters(), lr=0.01)
    loss_fn = nn.MSELoss()
    model.train()
    last_loss = 0.0
    for _ in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(x), y)
        loss.backward()
        opt.step()
        last_loss = float(loss.item())
    return model, lo, hi, last_loss


def train_and_save(ticker: str, arch: str = "lstm", epochs: int = EPOCHS, days: int = 365) -> dict:
    """사전학습 → 체크포인트 저장. 배치/스케줄 재학습 진입점."""
    if arch not in ARCHS:
        raise ValueError(f"Unknown arch: {arch}. Valid: {list(ARCHS)}")
    mat = _load_features(ticker, days=days)
    if len(mat) < WINDOW + 5:
        raise ValueError(f"Insufficient data: {len(mat)} rows")
    model, lo, hi, last_loss = _train(mat, arch, epochs)

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    path = _ckpt_path(ticker, arch)
    torch.save(
        {
            "arch": arch,
            "state_dict": model.state_dict(),
            "lo": lo.tolist(),
            "hi": hi.tolist(),
            "n_features": mat.shape[1],
            "features": list(FEATURES),
            "window": WINDOW,
            "epochs": epochs,
            "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
        },
        path,
    )
    return {
        "ticker": ticker,
        "arch": arch,
        "checkpoint": str(path),
        "train_loss": round(last_loss, 6),
        "samples": len(mat),
        "epochs": epochs,
    }


def _load_checkpoint(ticker: str, arch: str) -> tuple[nn.Module, np.ndarray, np.ndarray] | None:
    path = _ckpt_path(ticker, arch)
    if not path.exists():
        return None
    ckpt = torch.load(path, weights_only=True)
    n_features = ckpt.get("n_features", 1)
    model = _build_model(ckpt.get("arch", arch), n_features=n_features)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    return model, np.asarray(ckpt["lo"], dtype=float), np.asarray(ckpt["hi"], dtype=float)


def checkpoint_age_hours(ticker: str, arch: str) -> float | None:
    """체크포인트 학습 후 경과 시간(시간). 없으면 None."""
    path = _ckpt_path(ticker, arch)
    if not path.exists():
        return None
    ckpt = torch.load(path, weights_only=True)
    trained = datetime.fromisoformat(ckpt["trained_at"]).replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - trained
    return delta.total_seconds() / 3600.0


def needs_retrain(ticker: str, arch: str, max_age_hours: float = 24.0) -> bool:
    """체크포인트 없거나 max_age_hours 초과 → 재학습 필요."""
    age = checkpoint_age_hours(ticker, arch)
    return age is None or age > max_age_hours


def scheduled_retrain(tickers: list[str], arch: str = "lstm", max_age_hours: float = 24.0) -> list[dict]:
    """스케줄 재학습 — stale 체크포인트만 재학습(크론/엔드포인트 트리거)."""
    results = []
    for t in tickers:
        t = t.upper()
        if needs_retrain(t, arch, max_age_hours):
            try:
                info = train_and_save(t, arch=arch)
                info["retrained"] = True
                results.append(info)
            except ValueError as exc:
                results.append({"ticker": t, "arch": arch, "retrained": False, "error": str(exc)})
        else:
            results.append({"ticker": t, "arch": arch, "retrained": False, "reason": "fresh"})
    return results


def _rollout(model: nn.Module, norm: np.ndarray, lo: np.ndarray, hi: np.ndarray, current: float, last_loss: float) -> list[dict]:
    """멀티변량 롤아웃 — 종가만 예측 갱신, 나머지 피처는 마지막값 고정(근사)."""
    rng0 = hi[0] - lo[0] if hi[0] > lo[0] else 1.0  # close 열 역정규화
    horizons = []
    model.eval()
    with torch.no_grad():
        for label, steps in [("5min", 1), ("30min", 1), ("1day", 1), ("5day", 5)]:
            seq = [row.copy() for row in norm[-WINDOW:]]
            pred_close_norm = seq[-1][0]
            for _ in range(steps):
                inp = torch.tensor(np.array(seq[-WINDOW:]), dtype=torch.float32).reshape(1, WINDOW, -1)
                pred_close_norm = float(model(inp).item())
                nxt = seq[-1].copy()
                nxt[0] = pred_close_norm  # 종가만 갱신, 타 피처 고정
                seq.append(nxt)
            pred_price = pred_close_norm * rng0 + lo[0]
            direction = "UP" if pred_price > current else "DOWN"
            delta = abs(pred_price - current) / current if current else 0.0
            confidence = min(0.95, max(0.50, 0.85 - last_loss * 5 - delta * 3))
            horizons.append({
                "horizon": label,
                "predicted_price": round(pred_price, 2),
                "direction": direction,
                "confidence": round(confidence, 3),
            })
    return horizons


def predict_forecast(ticker: str, arch: str = "lstm") -> dict:
    """arch 모델 예측 — 멀티변량 입력. 체크포인트 있으면 로딩, 없으면 즉석학습(미저장)."""
    if arch not in ARCHS:
        raise ValueError(f"Unknown arch: {arch}. Valid: {list(ARCHS)}")
    mat = _load_features(ticker)
    if len(mat) < WINDOW + 5:
        raise ValueError(f"Insufficient data for {arch}: {len(mat)} rows")
    current = float(mat[-1, 0])

    ckpt = _load_checkpoint(ticker, arch)
    if ckpt is not None:
        model, lo, hi = ckpt
        source = "checkpoint"
        last_loss = 0.0
    else:
        model, lo, hi, last_loss = _train(mat, arch, EPOCHS)
        source = "on-the-fly"

    rng = np.where(hi > lo, hi - lo, 1.0)
    norm = (mat - lo) / rng
    horizons = _rollout(model, norm, lo, hi, current, last_loss)

    return {
        "ticker": ticker,
        "current_price": round(current, 2),
        "model": f"{arch}-v1",
        "weights_source": source,
        "features": list(FEATURES),
        "horizons": horizons,
    }


def predict_lstm(ticker: str) -> dict:
    """하위호환 — LSTM 예측."""
    return predict_forecast(ticker, "lstm")
