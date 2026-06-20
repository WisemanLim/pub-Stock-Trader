"""F2.2 실 거시·뉴스 채널 provider — lstm_model 훅에 연결.

macro: FDR 거시 지수(KOSPI KS11 등) 종가 시계열, 길이 정렬.
news: ingest 서비스 뉴스 → 간이 센티먼트 점수(키워드 기반) 시계열(상수 확장).
둘 다 실패 시 lstm_model 의 _channel 이 중립 폴백 → 부분 장애 격리.
"""
from datetime import datetime, timedelta, timezone

import FinanceDataReader as fdr
import httpx
import numpy as np

from app.core.config import settings

# 간이 사전 — 운영: FinBERT/Anthropic 등 모델 기반 점수로 교체.
_POS = {"surge", "rally", "gain", "beat", "growth", "up", "상승", "급등", "호재"}
_NEG = {"plunge", "drop", "loss", "miss", "fall", "down", "하락", "급락", "악재"}


def _fetch_series(symbol: str, length: int) -> np.ndarray | None:
    """단일 거시 심볼 종가 → length 정렬(앞쪽 패딩). 실패 시 None."""
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=length * 2 + 40)
        df = fdr.DataReader(symbol, start.strftime("%Y-%m-%d"))
        series = df["Close"].astype(float).to_numpy()
        if len(series) == 0:
            return None
        if len(series) >= length:
            return series[-length:]
        pad = np.full(length - len(series), series[0])
        return np.concatenate([pad, series])
    except Exception:
        return None


def _zscore(arr: np.ndarray) -> np.ndarray:
    sd = arr.std()
    return (arr - arr.mean()) / sd if sd > 0 else np.zeros_like(arr)


def _pca_first_component(mat: np.ndarray) -> np.ndarray:
    """행=지표, 열=시점 z-score 행렬 → 제1주성분 점수(시점별). numpy SVD."""
    # mat shape (k, T). 시점 축으로 투영 → 길이 T 시계열.
    x = mat - mat.mean(axis=1, keepdims=True)
    # 공분산(지표간) 고유벡터 → 첫 주성분 로딩
    u, s, vt = np.linalg.svd(x, full_matrices=False)
    pc1 = vt[0]  # 길이 T, 제1주성분 점수
    return _zscore(pc1)


def _incremental_pca(mat: np.ndarray, window: int = 20) -> np.ndarray:
    """증분(롤링) PCA — 각 시점에서 직전 window 구간 SVD 제1주성분의 마지막값.

    배치 PCA 대비 시변 구조 추적. 초기 구간은 배치 PCA 폴백.
    """
    k, T = mat.shape
    out = np.zeros(T)
    for t in range(T):
        lo = max(0, t - window + 1)
        seg = mat[:, lo : t + 1]
        if seg.shape[1] < 2:
            out[t] = 0.0
            continue
        x = seg - seg.mean(axis=1, keepdims=True)
        _, _, vt = np.linalg.svd(x, full_matrices=False)
        out[t] = vt[0][-1]  # 윈도우 마지막 시점의 주성분 점수
    return _zscore(out)


def _ccipca(mat: np.ndarray, ell: float = 2.0) -> np.ndarray:
    """CCIPCA(Candid Covariance-free Incremental PCA) — 진성 증분 제1주성분.

    Weng et al. 2003. 시점마다 v 갱신: v ← (1-w)v + w·(u·(uᵀv̂))·v̂.
    각 시점 점수 = uₜ·v̂. 배치 SVD 재계산 없이 O(k) 업데이트.
    """
    k, T = mat.shape
    x = mat - mat.mean(axis=1, keepdims=True)
    v = x[:, 0].copy()
    if np.linalg.norm(v) == 0:
        v = np.ones(k)
    out = np.zeros(T)
    for t in range(T):
        u = x[:, t]
        n = t + 1
        w1 = (n - 1 - ell) / n if n > ell else 0.0
        w2 = (1 + ell) / n
        vh = v / (np.linalg.norm(v) + 1e-12)
        v = w1 * v + w2 * (u @ vh) * u
        out[t] = u @ (v / (np.linalg.norm(v) + 1e-12))
    return _zscore(out)


def _risk_parity_weights(zs: list[np.ndarray]) -> np.ndarray:
    """리스크 패리티 — 역변동성 정규화(동일 위험기여 근사). Σw=1."""
    vols = np.array([np.std(np.diff(z)) if len(z) > 1 else 1.0 for z in zs])
    vols = np.where(vols > 0, vols, 1e-9)
    inv = 1.0 / vols
    return inv / inv.sum()


def _const_corr_target(sample: np.ndarray) -> np.ndarray:
    """상수상관 타깃 — 평균상관 r̄, F_ij = r̄·√(s_ii·s_jj), F_ii=s_ii."""
    d = np.sqrt(np.clip(np.diag(sample), 1e-12, None))
    corr = sample / np.outer(d, d)
    k = sample.shape[0]
    off = corr[~np.eye(k, dtype=bool)]
    rbar = off.mean() if off.size else 0.0
    f = rbar * np.outer(d, d)
    np.fill_diagonal(f, np.diag(sample))
    return f


def _quest_shrink(sample: np.ndarray, n: int) -> np.ndarray:
    """QuEST-계열 해석적 비선형 축소(Ledoit-Wolf 2020).

    표본 고유값 λ + 커널밀도 추정으로 oracle 고유값 d̃_i 산출:
      d̃_i = λ_i / ((π·c·λ_i·f̃)² + (1 − c − π·c·λ_i·Hf̃)²)
    f̃=밀도, Hf̃=Hilbert 변환(Epanechnikov 커널). 고유벡터 보존.
    """
    k = sample.shape[0]
    vals, vecs = np.linalg.eigh(sample)
    vals = np.clip(vals, 0.0, None)
    if k < 2 or n <= k:
        return sample  # p≥n 영역은 별도 처리 필요 → 보수적으로 원본
    c = k / n
    lam = vals.copy()
    h = n ** (-1.0 / 3.0)            # 대역폭
    L = lam.reshape(-1, 1)           # (k,1)
    Lj = lam.reshape(1, -1)          # (1,k)
    denom = (h * Lj) ** 2
    diff = L - Lj
    # Epanechnikov 밀도 f̃(λ_i)
    inside = 1.0 - (diff ** 2) / (5.0 * denom + 1e-12)
    kern = np.where(inside > 0, np.sqrt(np.clip(inside, 0, None)) * 3.0 / (4.0 * np.sqrt(5.0) * np.sqrt(denom) + 1e-12), 0.0)
    f = kern.mean(axis=1)
    # Hilbert 변환 Hf̃(λ_i)
    with np.errstate(divide="ignore", invalid="ignore"):
        hf_kern = np.where(
            np.abs(diff) > 1e-12,
            (3.0 / (10.0 * np.pi)) / denom * diff
            - (3.0 / (4.0 * np.sqrt(5.0) * np.pi)) / np.sqrt(denom)
            * (1.0 - (diff ** 2) / (5.0 * denom)) * np.log(np.abs((np.sqrt(5.0 * denom) - diff) / (np.sqrt(5.0 * denom) + diff + 1e-12)) + 1e-12),
            0.0,
        )
    hf = hf_kern.mean(axis=1)
    d_tilde = lam / ((np.pi * c * lam * f) ** 2 + (1.0 - c - np.pi * c * lam * hf) ** 2 + 1e-12)
    d_tilde = np.where(np.isfinite(d_tilde) & (d_tilde > 0), d_tilde, lam)
    return (vecs * d_tilde) @ vecs.T


def _quest_grid_shrink(sample: np.ndarray, n: int, grid: int = 200) -> np.ndarray:
    """격자 QuEST — 표본 고유값 지지구간을 격자로 이산화, 밀도·Hilbert 변환을
    격자에서 수치적분(역변환). 격자에서 oracle 고유값 산출 후 표본 λ_i 에 보간.
    해석적 커널(per-sample) 대비 안정적 수치역전.
    """
    k = sample.shape[0]
    vals, vecs = np.linalg.eigh(sample)
    vals = np.clip(vals, 0.0, None)
    if k < 2 or n <= k:
        return sample
    c = k / n
    lam = vals.copy()
    lo, hi = lam.min(), lam.max()
    span = max(hi - lo, 1e-9)
    xg = np.linspace(lo - 0.05 * span, hi + 0.05 * span, grid)  # 격자
    h = max(span * n ** (-1.0 / 3.0), 1e-6)                     # 대역폭
    # 격자점별 밀도 f(x), Hilbert Hf(x) — Epanechnikov 커널 합(표본 λ 기준)
    diff = xg.reshape(-1, 1) - lam.reshape(1, -1)               # (grid,k)
    u = diff / h
    inside = 1.0 - u * u / 5.0
    kern = np.where(inside > 0, np.sqrt(np.clip(inside, 0, None)) * 3.0 / (4.0 * np.sqrt(5.0)), 0.0)
    f_grid = kern.mean(axis=1) / h
    # Hilbert (수치 주값적분, 격자 간 제외)
    hf_grid = np.zeros(grid)
    dx = xg[1] - xg[0]
    for gi in range(grid):
        d = xg[gi] - lam
        mask = np.abs(d) > 1e-9
        hf_grid[gi] = np.mean(np.where(mask, 1.0 / (np.pi * d), 0.0)) if mask.any() else 0.0
    _ = dx
    # 격자 oracle 고유값
    d_grid = xg / ((np.pi * c * xg * f_grid) ** 2 + (1.0 - c - np.pi * c * xg * hf_grid) ** 2 + 1e-12)
    d_grid = np.where(np.isfinite(d_grid) & (d_grid > 0), d_grid, xg)
    # 표본 λ_i 에 보간
    d_tilde = np.interp(lam, xg, d_grid)
    d_tilde = np.where(d_tilde > 0, d_tilde, lam)
    return (vecs * d_tilde) @ vecs.T


def _quest_adaptive_shrink(sample: np.ndarray, n: int, grid: int = 200) -> np.ndarray:
    """적응 격자 QuEST — 균일 격자(_quest_grid_shrink) 대신 표본 고유값 분포의
    분위수로 격자를 배치(고유값 밀집 구간에 노드 집중 → 밀도 추정·수치역전 정밀도↑).

    노드: [lo-pad] + quantile(λ, ·) + [hi-pad]. 비균일 격자(분위수 단조증가, 보간 안전).
    밀도 f·Hilbert Hf 는 per-node 평균(격자 간격 무관)이라 비균일에도 유효. 결정적.
    """
    k = sample.shape[0]
    vals, vecs = np.linalg.eigh(sample)
    vals = np.clip(vals, 0.0, None)
    if k < 2 or n <= k:
        return sample
    c = k / n
    lam = vals.copy()
    lo, hi = lam.min(), lam.max()
    span = max(hi - lo, 1e-9)
    pad = 0.05 * span
    # 적응 격자 — 분위수 기반(밀집 구간 노드 집중) + 양끝 패딩. 중복 제거·정렬.
    inner = max(grid - 2, 2)
    qs = np.quantile(lam, np.linspace(0.0, 1.0, inner))
    xg = np.unique(np.concatenate(([lo - pad], qs, [hi + pad])))
    h = max(span * n ** (-1.0 / 3.0), 1e-6)
    diff = xg.reshape(-1, 1) - lam.reshape(1, -1)
    u = diff / h
    inside = 1.0 - u * u / 5.0
    kern = np.where(inside > 0, np.sqrt(np.clip(inside, 0, None)) * 3.0 / (4.0 * np.sqrt(5.0)), 0.0)
    f_grid = kern.mean(axis=1) / h
    g = xg.shape[0]
    hf_grid = np.zeros(g)
    for gi in range(g):
        d = xg[gi] - lam
        mask = np.abs(d) > 1e-9
        hf_grid[gi] = np.mean(np.where(mask, 1.0 / (np.pi * d), 0.0)) if mask.any() else 0.0
    d_grid = xg / ((np.pi * c * xg * f_grid) ** 2 + (1.0 - c - np.pi * c * xg * hf_grid) ** 2 + 1e-12)
    d_grid = np.where(np.isfinite(d_grid) & (d_grid > 0), d_grid, xg)
    d_tilde = np.interp(lam, xg, d_grid)
    d_tilde = np.where(d_tilde > 0, d_tilde, lam)
    return (vecs * d_tilde) @ vecs.T


def marchenko_pastur_gof(eigs: np.ndarray, c: float, bins: int = 50) -> float:
    """Marchenko-Pastur 적합도검정 — 표본 고유값 분포 vs MP 법칙의 KS 거리.

    c=k/n (관측당 차원비, 0<c<1 가정). MP 지지 [(1-√c)², (1+√c)²]·σ², σ²=mean(eigs).
    경험 CDF 와 MP 누적분포의 최대 차(KS 통계, 0~1). 낮을수록 노이즈(MP) 적합 = 신호 적음.
    소표본·비정상 입력 시 1.0(불일치).
    """
    e = np.asarray(eigs, dtype=float)
    e = e[np.isfinite(e)]
    if e.size < 2 or not (0.0 < c < 1.0):
        return 1.0
    sigma2 = float(e.mean())
    if sigma2 <= 0:
        return 1.0
    a = sigma2 * (1.0 - np.sqrt(c)) ** 2     # MP 하한
    b = sigma2 * (1.0 + np.sqrt(c)) ** 2     # MP 상한
    if b <= a:
        return 1.0
    # MP 밀도 → 수치 CDF (격자 적분)
    xs = np.linspace(a, b, bins)
    with np.errstate(invalid="ignore"):
        dens = np.sqrt(np.clip((b - xs) * (xs - a), 0.0, None)) / (2.0 * np.pi * c * sigma2 * xs)
    dens = np.where(np.isfinite(dens), dens, 0.0)
    cdf = np.cumsum(dens)
    cdf = cdf / cdf[-1] if cdf[-1] > 0 else cdf
    # 경험 CDF 를 동일 격자에서 평가 후 KS
    es = np.sort(e)
    emp = np.searchsorted(es, xs, side="right") / es.size
    return float(np.max(np.abs(emp - cdf)))


def _factor_model_shrink(sample: np.ndarray, n: int) -> np.ndarray:
    """팩터모델 타깃 축소 — MP 상한(λ⁺) 초과 고유값=신호(팩터) 보존,
    나머지 bulk(노이즈)는 평균으로 평탄화(랜덤행렬이론 디노이징, Bouchaud/LdP).

    λ⁺=σ²(1+√c)², σ²=bulk 평균 분산. 신호 고유값 < 1개면 원본 반환(보수적).
    """
    k = sample.shape[0]
    vals, vecs = np.linalg.eigh(sample)
    vals = np.clip(vals, 0.0, None)
    if k < 2 or n <= k:
        return sample
    c = k / n
    sigma2 = float(vals.mean())
    lam_plus = sigma2 * (1.0 + np.sqrt(c)) ** 2
    signal = vals > lam_plus
    if signal.sum() < 1 or signal.all():
        return sample  # 분리 불가 → 원본
    bulk_mean = float(vals[~signal].mean())
    d = np.where(signal, vals, bulk_mean)   # 신호 보존, 노이즈 평탄화
    return (vecs * d) @ vecs.T


def _ledoit_wolf_shrink(rets: np.ndarray, sample: np.ndarray, target: str = "identity") -> np.ndarray:
    """공분산 축소 — target: identity | const_corr | oas | nlw | quest | quest_grid | quest_adaptive | factor_model.

    Σ_shrunk = δ·F + (1-δ)·S. δ=최적 축소강도. 소표본 안정화.
    """
    k, n = rets.shape
    if n < 2:
        return sample
    if target == "quest":
        return _quest_shrink(sample, n)
    if target == "quest_grid":
        return _quest_grid_shrink(sample, n)
    if target == "quest_adaptive":
        return _quest_adaptive_shrink(sample, n)
    if target == "factor_model":
        return _factor_model_shrink(sample, n)
    if target == "nlw":
        # 비선형 축소(Ledoit-Wolf 2017 근사) — 고유값별 수축. 극단 고유값일수록 평균쪽 강수축.
        vals, vecs = np.linalg.eigh(sample)
        mu = vals.mean()
        c = k / n  # 집중도 p/n
        shrunk = np.empty_like(vals)
        for i, lam in enumerate(vals):
            dist = abs(lam - mu) / (mu + 1e-12)
            delta = c / (c + dist + 1e-12)
            shrunk[i] = lam * (1 - delta) + mu * delta
        return (vecs * shrunk) @ vecs.T

    if target == "const_corr":
        f = _const_corr_target(sample)
    else:
        f = (np.trace(sample) / k) * np.eye(k)  # μI

    x = rets - rets.mean(axis=1, keepdims=True)
    if target == "oas":
        # OAS(Chen 2010) — 폐형 δ. F = μI.
        mu = np.trace(sample) / k
        f = mu * np.eye(k)
        tr_s2 = np.sum(sample * sample)
        tr_s_2 = np.trace(sample) ** 2
        num = (1.0 - 2.0 / k) * tr_s2 + tr_s_2
        den = (n + 1.0 - 2.0 / k) * (tr_s2 - tr_s_2 / k)
        delta = 1.0 if den <= 0 else float(np.clip(num / den, 0.0, 1.0))
        return delta * f + (1.0 - delta) * sample

    # Ledoit-Wolf δ
    pi = 0.0
    for t in range(n):
        xt = x[:, t : t + 1]
        diff = xt @ xt.T - sample
        pi += np.sum(diff * diff)
    pi /= n
    gamma = np.sum((sample - f) ** 2)
    delta = 0.0 if gamma <= 0 else float(np.clip(pi / (gamma * n), 0.0, 1.0))
    return delta * f + (1.0 - delta) * sample


def _cov_from_zs(zs: list[np.ndarray], shrink: bool = False, target: str = "identity") -> np.ndarray:
    k = len(zs)
    rets = np.vstack([np.diff(z) for z in zs])  # (k, T-1)
    cov = np.cov(rets) if rets.shape[1] > 1 else np.eye(k)
    cov = np.atleast_2d(cov)
    if shrink and cov.shape == (k, k) and rets.shape[1] > 1:
        cov = _ledoit_wolf_shrink(rets, cov, target=target)
    if cov.shape != (k, k):
        cov = np.eye(k)
    return cov


def _erc_newton(zs: list[np.ndarray], iters: int = 100, tol: float = 1e-10,
                shrink: bool = False, target: str = "identity") -> np.ndarray:
    """ERC 정밀해 — Spinu(2013) 볼록 공식 Newton 해.

    min ½xᵀΣx − (1/k)Σln(xᵢ) s.t. x>0. 해 x* → w=x*/Σx*. 위험기여 균등.
    그래디언트 g=Σx−(1/k)/x, 헤시안 H=Σ+diag((1/k)/x²) → Newton step.
    shrink=True 시 Ledoit-Wolf 축소 공분산 사용(소표본 안정).
    """
    k = len(zs)
    if k == 1:
        return np.array([1.0])
    cov = _cov_from_zs(zs, shrink=shrink, target=target)
    diag = np.diag(cov).copy()
    diag[diag <= 0] = 1e-9
    x = 1.0 / np.sqrt(diag)  # 초기값
    c = 1.0 / k
    for _ in range(iters):
        sx = cov @ x
        grad = sx - c / x
        hess = cov + np.diag(c / (x * x))
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        # 양수 유지 백트래킹
        alpha = 1.0
        while alpha > 1e-6 and np.any(x - alpha * step <= 0):
            alpha *= 0.5
        x_new = x - alpha * step
        if np.max(np.abs(x_new - x)) < tol:
            x = x_new
            break
        x = x_new
    return x / x.sum()


def _risk_parity_weights(zs: list[np.ndarray]) -> np.ndarray:
    """리스크 패리티 — 역변동성 정규화(동일 위험기여 근사). Σw=1."""
    vols = np.array([np.std(np.diff(z)) if len(z) > 1 else 1.0 for z in zs])
    vols = np.where(vols > 0, vols, 1e-9)
    inv = 1.0 / vols
    return inv / inv.sum()


def _erc_weights(zs: list[np.ndarray], iters: int = 50) -> np.ndarray:
    """공분산 기반 ERC — marginal risk 역가중 반복(휴리스틱)."""
    k = len(zs)
    if k == 1:
        return np.array([1.0])
    cov = _cov_from_zs(zs)
    diag = np.diag(cov).copy()
    diag[diag <= 0] = 1e-9
    w = 1.0 / np.sqrt(diag)
    w = w / w.sum()
    for _ in range(iters):
        mrc = cov @ w                      # marginal risk contribution
        mrc = np.where(np.abs(mrc) < 1e-12, 1e-12, mrc)
        w = w / mrc                        # 위험기여 역가중
        w = np.clip(w, 1e-9, None)
        w = w / w.sum()
    return w


def _dynamic_weights(zs: list[np.ndarray]) -> np.ndarray:
    """변동성 역가중 — 최근 변동성 큰 지표 비중 축소(안정 지표 우선)."""
    vols = np.array([np.std(np.diff(z)) if len(z) > 1 else 1.0 for z in zs])
    vols = np.where(vols > 0, vols, 1.0)
    inv = 1.0 / vols
    return inv / inv.sum()


def macro_provider(ticker: str, length: int) -> np.ndarray:
    """다지표 합성 거시 채널. MACRO_COMBINE: mean|weighted|pca.

    각 심볼 z-score 후 합성. 일부 실패 시 가능한 것만. 전부 실패 → 중립 0.
    """
    symbols = [s.strip() for s in settings.macro_indices.split(",") if s.strip()]
    if not symbols:
        symbols = [settings.macro_index]
    zs = []
    for sym in symbols:
        s = _fetch_series(sym, length)
        if s is not None:
            zs.append(_zscore(s))
    if not zs:
        return np.zeros(length, dtype=float)

    mode = settings.macro_combine
    if mode == "pca" and len(zs) >= 2:
        return _pca_first_component(np.vstack(zs))
    if mode == "ipca" and len(zs) >= 2:
        return _incremental_pca(np.vstack(zs))  # 증분(롤링) PCA
    if mode == "ccipca" and len(zs) >= 2:
        return _ccipca(np.vstack(zs))           # 진성 증분 PCA(Oja류)
    if mode == "riskparity":
        w = _risk_parity_weights(zs)            # 리스크 패리티(역변동성)
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc" and len(zs) >= 2:
        w = _erc_weights(zs)                    # 공분산 ERC(휴리스틱)
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_newton" and len(zs) >= 2:
        w = _erc_newton(zs)                     # ERC 정밀해(Newton)
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_lw" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True)        # ERC + Ledoit-Wolf(μI 타깃)
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_cc" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="const_corr")  # 상수상관 타깃
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_oas" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="oas")         # OAS 축소
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_nlw" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="nlw")         # 비선형 축소(휴리스틱)
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_quest" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="quest")       # QuEST 해석적 비선형
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_quest_grid" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="quest_grid")  # 격자 QuEST 수치역전
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_quest_adaptive" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="quest_adaptive")  # 적응 격자 QuEST
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "erc_factor" and len(zs) >= 2:
        w = _erc_newton(zs, shrink=True, target="factor_model")    # MP 팩터/노이즈 분리 디노이징
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "dynamic":
        w = _dynamic_weights(zs)                # 변동성 역가중(시변)
        return np.average(np.vstack(zs), axis=0, weights=w)
    if mode == "weighted":
        raw = [float(w) for w in settings.macro_weights.split(",") if w.strip()]
        if len(raw) == len(zs) and sum(abs(w) for w in raw) > 0:
            w = np.asarray(raw)
            w = w / np.abs(w).sum()
            return np.average(np.vstack(zs), axis=0, weights=w)
    return np.mean(zs, axis=0)  # 기본 mean


def _score_text(text: str) -> float:
    """키워드 기반 센티먼트 [-1,1] (설명가능 폴백)."""
    toks = set(text.lower().split())
    pos = len(toks & _POS)
    neg = len(toks & _NEG)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


_finbert_pipe = None  # 지연 로드 캐시


def _get_finbert():
    """FinBERT 파이프라인 지연 로드. 실패 시 None(키워드 폴백)."""
    global _finbert_pipe
    if _finbert_pipe is not None:
        return _finbert_pipe
    try:
        from transformers import pipeline
        _finbert_pipe = pipeline("sentiment-analysis", model=settings.finbert_model)
        return _finbert_pipe
    except Exception:
        return None


def _finbert_score(texts: list[str]) -> float | None:
    """FinBERT 평균 센티먼트 [-1,1]. positive=+, negative=-, neutral=0."""
    pipe = _get_finbert()
    if pipe is None:
        return None
    try:
        results = pipe([t[:512] for t in texts])
        vals = []
        for r in results:
            label = r["label"].lower()
            score = float(r.get("score", 0.0))
            # 영문(positive/negative) + KR-FinBERT(긍정/부정/label_2 등) 대응
            is_pos = "pos" in label or "긍정" in label or label in ("label_2", "2")
            is_neg = "neg" in label or "부정" in label or label in ("label_0", "0")
            vals.append(score if is_pos else -score if is_neg else 0.0)
        return float(np.mean(vals)) if vals else 0.0
    except Exception:
        return None


def news_sentiment(source: str = "reuters-business", limit: int = 20) -> float:
    """ingest 뉴스 → 평균 센티먼트 [-1,1]. FinBERT(설정 시) 우선, 키워드 폴백, 실패 0."""
    try:
        r = httpx.get(f"{settings.ingest_url}/news/{source}", params={"limit": limit}, timeout=5.0)
        if r.status_code != 200:
            return 0.0
        items = r.json().get("items", [])
        if not items:
            return 0.0
        texts = [f"{it.get('title','')} {it.get('summary','')}" for it in items]
        if settings.finbert_enabled:
            fb = _finbert_score(texts)
            if fb is not None:
                return fb
        return float(np.mean([_score_text(t) for t in texts]))
    except Exception:
        return 0.0


def news_provider(ticker: str, length: int) -> np.ndarray:
    """현재 센티먼트를 상수 채널로 확장(시계열 히스토리 없음 → 최신값 broadcast)."""
    return np.full(length, news_sentiment(), dtype=float)


def register() -> None:
    """lstm_model 에 실 provider 등록."""
    from app.services.lstm_model import set_channel_providers
    set_channel_providers(macro=macro_provider, news=news_provider)
