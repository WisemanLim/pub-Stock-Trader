"""F2.2 실 거시·뉴스 채널 provider 시험."""
from unittest.mock import patch

import numpy as np
import pandas as pd

from app.services import channels


def test_score_text_positive():
    assert channels._score_text("KOSPI surge rally gain") > 0


def test_score_text_negative():
    assert channels._score_text("market plunge drop loss") < 0


def test_score_text_neutral():
    assert channels._score_text("the company released a report") == 0.0


def test_macro_provider_composite_zscore():
    idx = pd.DataFrame({"Close": np.linspace(2400, 2600, 100)})
    with patch("app.services.channels.fdr.DataReader", return_value=idx):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30
    # z-score 합성 → 평균 ~0, 표준편차 ~1 (단조증가)
    assert abs(arr.mean()) < 1e-6
    assert arr[-1] > arr[0]


def test_macro_provider_pads_when_short():
    idx = pd.DataFrame({"Close": np.array([2500.0, 2510.0, 2520.0])})
    with patch("app.services.channels.fdr.DataReader", return_value=idx):
        arr = channels.macro_provider("ANY", 10)
    assert arr.shape[0] == 10  # 앞쪽 패딩


def test_macro_provider_fallback_on_error():
    with patch("app.services.channels.fdr.DataReader", side_effect=Exception("net")):
        arr = channels.macro_provider("ANY", 5)
    assert arr.shape[0] == 5
    assert np.all(arr == 0.0)  # 전 심볼 실패 → 중립 폴백


def test_macro_weighted_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),
        pd.DataFrame({"Close": np.linspace(1300, 1350, 40)}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "weighted"), \
         patch("app.services.channels.settings.macro_weights", "0.7,0.3"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30
    assert np.isfinite(arr).all()


def test_macro_pca_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 50)}),
        pd.DataFrame({"Close": np.linspace(1300, 1350, 50)}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "pca"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30
    assert abs(arr.mean()) < 1e-6  # z-score 정규화된 주성분


def test_macro_dynamic_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),       # 저변동
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(40)) * 50}),  # 고변동
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "dynamic"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30
    assert np.isfinite(arr).all()


def test_macro_incremental_pca():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 50)}),
        pd.DataFrame({"Close": np.linspace(1300, 1380, 50)}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "ipca"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30
    assert abs(arr.mean()) < 1e-6  # z-score 정규화


def test_dynamic_weights_favors_stable():
    import numpy as np
    stable = np.linspace(0, 1, 50)               # 저변동
    volatile = np.sin(np.arange(50)) * np.arange(50)  # 고변동
    w = channels._dynamic_weights([stable, volatile])
    assert w[0] > w[1]   # 안정 지표 비중↑
    assert abs(w.sum() - 1.0) < 1e-9


def test_macro_riskparity_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(40)) * 30}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "riskparity"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30 and np.isfinite(arr).all()


def test_macro_ccipca_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 50)}),
        pd.DataFrame({"Close": np.linspace(1300, 1380, 50)}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "ccipca"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30
    assert abs(arr.mean()) < 1e-6  # z-score


def test_macro_erc_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 50)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(50)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30 and np.isfinite(arr).all()


def test_erc_weights_sum_one():
    import numpy as np
    a = np.cumsum(np.sin(np.arange(60)) * 0.1)
    b = np.cumsum(np.cos(np.arange(60)) * 0.3)
    w = channels._erc_weights([a, b])
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w > 0).all()


def test_ledoit_wolf_shrink_psd():
    import numpy as np
    rng = np.random.default_rng(1)
    rets = rng.normal(0, 0.02, (3, 30))
    sample = np.cov(rets)
    shrunk = channels._ledoit_wolf_shrink(rets, sample)
    assert shrunk.shape == (3, 3)
    # 양정치(고유값 ≥ 0)
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)


def test_const_corr_target():
    import numpy as np
    sample = np.array([[4.0, 1.0], [1.0, 9.0]])
    f = channels._const_corr_target(sample)
    assert f[0, 0] == 4.0 and f[1, 1] == 9.0   # 대각 보존
    assert abs(f[0, 1] - f[1, 0]) < 1e-9        # 대칭


def test_oas_shrink_psd():
    import numpy as np
    rng = np.random.default_rng(2)
    rets = rng.normal(0, 0.02, (3, 25))
    s = np.cov(rets)
    shrunk = channels._ledoit_wolf_shrink(rets, s, target="oas")
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)


def test_nlw_shrink_psd():
    import numpy as np
    rng = np.random.default_rng(3)
    rets = rng.normal(0, 0.02, (3, 20))
    s = np.cov(rets)
    shrunk = channels._ledoit_wolf_shrink(rets, s, target="nlw")
    assert shrunk.shape == (3, 3)
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)  # PSD 유지
    # 고유값 분산 축소(평균쪽 수축)
    v_orig = np.linalg.eigvalsh(s)
    v_new = np.linalg.eigvalsh(shrunk)
    assert v_new.std() <= v_orig.std() + 1e-9


def test_quest_shrink_psd():
    import numpy as np
    rng = np.random.default_rng(4)
    rets = rng.normal(0, 0.02, (4, 40))  # n>p
    s = np.cov(rets)
    shrunk = channels._quest_shrink(s, 40)
    assert shrunk.shape == (4, 4)
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)  # PSD
    assert np.allclose(shrunk, shrunk.T, atol=1e-9)     # 대칭


def test_quest_grid_shrink_psd():
    import numpy as np
    rng = np.random.default_rng(7)
    rets = rng.normal(0, 0.02, (4, 50))
    s = np.cov(rets)
    shrunk = channels._quest_grid_shrink(s, 50)
    assert shrunk.shape == (4, 4)
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)  # PSD
    assert np.allclose(shrunk, shrunk.T, atol=1e-9)


# ── 차수22: F2.2 적응 격자 QuEST · MP 적합도검정 · 팩터모델 타깃 ──

def test_quest_adaptive_shrink_psd():
    rng = np.random.default_rng(11)
    rets = rng.normal(0, 0.02, (4, 50))
    s = np.cov(rets)
    shrunk = channels._quest_adaptive_shrink(s, 50)
    assert shrunk.shape == (4, 4)
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)   # PSD
    assert np.allclose(shrunk, shrunk.T, atol=1e-9)       # 대칭


def test_quest_adaptive_small_sample_fallback():
    rng = np.random.default_rng(12)
    rets = rng.normal(0, 0.02, (5, 4))   # p>n → 원본
    s = np.cov(rets)
    assert np.allclose(channels._quest_adaptive_shrink(s, 4), s)


def test_quest_adaptive_valid_oracle():
    """적응 격자 QuEST 출력 — PSD·대칭·양 고유값·유한(유효 oracle 공분산)."""
    rng = np.random.default_rng(13)
    rets = rng.normal(0, 0.02, (5, 60))
    s = np.cov(rets)
    ad = channels._quest_adaptive_shrink(s, 60)
    assert ad.shape == (5, 5)
    assert np.isfinite(ad).all()
    assert np.allclose(ad, ad.T, atol=1e-9)              # 대칭
    eig = np.linalg.eigvalsh(ad)
    assert np.all(eig >= -1e-9) and np.all(eig > 0)      # 양정치 oracle


def test_mp_gof_lower_for_pure_noise_than_spiked():
    rng = np.random.default_rng(21)
    k, n = 6, 300
    noise = rng.normal(0, 1, (k, n))
    eig_noise = np.linalg.eigvalsh(np.cov(noise))
    # 스파이크 — 한 변수에 강한 공통 팩터 주입(큰 고유값)
    spiked = noise.copy()
    factor = rng.normal(0, 1, n)
    spiked += 3.0 * factor                       # 전 변수 공통 팩터 → 1 거대 고유값
    eig_spiked = np.linalg.eigvalsh(np.cov(spiked))
    c = k / n
    gof_noise = channels.marchenko_pastur_gof(eig_noise, c)
    gof_spiked = channels.marchenko_pastur_gof(eig_spiked, c)
    assert 0.0 <= gof_noise <= 1.0
    assert gof_spiked > gof_noise                # 신호(팩터) 있으면 MP 불일치↑


def test_mp_gof_invalid_inputs():
    assert channels.marchenko_pastur_gof(np.array([1.0]), 0.5) == 1.0   # 표본 부족
    assert channels.marchenko_pastur_gof(np.array([1.0, 2.0]), 1.5) == 1.0  # c 범위 밖


def test_factor_model_shrink_preserves_signal_flattens_bulk():
    rng = np.random.default_rng(31)
    k, n = 6, 200
    factor = rng.normal(0, 1, n)
    data = rng.normal(0, 0.3, (k, n)) + 2.0 * factor   # 강한 공통 팩터 → 1 신호 고유값
    s = np.cov(data)
    shrunk = channels._factor_model_shrink(s, n)
    assert shrunk.shape == (k, k)
    assert np.all(np.linalg.eigvalsh(shrunk) >= -1e-9)  # PSD
    eig_s = np.linalg.eigvalsh(s)
    eig_sh = np.linalg.eigvalsh(shrunk)
    assert np.isclose(eig_sh[-1], eig_s[-1], rtol=1e-6)  # 최대(신호) 고유값 보존
    # bulk(노이즈) 고유값은 평탄화 → 거의 동일값
    assert eig_sh[:-1].std() < eig_s[:-1].std() + 1e-9
    assert eig_sh[:-1].std() < 1e-9


def test_factor_model_no_signal_returns_original():
    rng = np.random.default_rng(32)
    rets = rng.normal(0, 0.02, (5, 4))   # p>n → 원본
    s = np.cov(rets)
    assert np.allclose(channels._factor_model_shrink(s, 4), s)


def test_macro_erc_quest_adaptive_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(40)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc_quest_adaptive"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30 and np.isfinite(arr).all()


def test_macro_erc_factor_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(40)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc_factor"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30 and np.isfinite(arr).all()


def test_macro_erc_quest_grid_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(40)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc_quest_grid"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30 and np.isfinite(arr).all()


def test_quest_small_sample_fallback():
    import numpy as np
    rng = np.random.default_rng(5)
    rets = rng.normal(0, 0.02, (5, 4))  # p>n → 원본 반환
    s = np.cov(rets)
    assert np.allclose(channels._quest_shrink(s, 4), s)


def test_macro_erc_quest_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 40)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(40)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc_quest"):
        arr = channels.macro_provider("ANY", 30)
    assert arr.shape[0] == 30 and np.isfinite(arr).all()


def test_macro_erc_nlw_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 30)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(30)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc_nlw"):
        arr = channels.macro_provider("ANY", 25)
    assert arr.shape[0] == 25 and np.isfinite(arr).all()


def test_macro_erc_cc_oas_combine():
    for combine in ("erc_cc", "erc_oas"):
        seq = iter([
            pd.DataFrame({"Close": np.linspace(2400, 2600, 30)}),
            pd.DataFrame({"Close": 1300 + np.sin(np.arange(30)) * 40}),
        ])
        with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
             patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
             patch("app.services.channels.settings.macro_combine", combine):
            arr = channels.macro_provider("ANY", 25)
        assert arr.shape[0] == 25 and np.isfinite(arr).all()


def test_macro_erc_lw_combine():
    seq = iter([
        pd.DataFrame({"Close": np.linspace(2400, 2600, 30)}),
        pd.DataFrame({"Close": 1300 + np.sin(np.arange(30)) * 40}),
    ])
    with patch("app.services.channels.fdr.DataReader", side_effect=lambda *a, **k: next(seq)), \
         patch("app.services.channels.settings.macro_indices", "KS11,USD/KRW"), \
         patch("app.services.channels.settings.macro_combine", "erc_lw"):
        arr = channels.macro_provider("ANY", 25)
    assert arr.shape[0] == 25 and np.isfinite(arr).all()


def test_erc_newton_equal_risk_contribution():
    import numpy as np
    rng = np.random.default_rng(0)
    # 독립 자산 → ERC 가중은 역변동성 비례
    a = np.cumsum(rng.normal(0, 0.01, 200))
    b = np.cumsum(rng.normal(0, 0.03, 200))
    w = channels._erc_newton([a, b])
    assert abs(w.sum() - 1.0) < 1e-6
    assert (w > 0).all()
    # 위험기여 RC_i = w_i·(Σw)_i 가 균등(독립 → 거의 동일)
    cov = channels._cov_from_zs([a, b])
    rc = w * (cov @ w)
    assert abs(rc[0] - rc[1]) / (abs(rc[0]) + 1e-12) < 0.2


def test_risk_parity_weights_sum_one():
    stable = np.linspace(0, 1, 50)
    volatile = np.sin(np.arange(50)) * np.arange(50)
    w = channels._risk_parity_weights([stable, volatile])
    assert abs(w.sum() - 1.0) < 1e-9
    assert w[0] > w[1]  # 안정 지표 비중↑


def test_finbert_korean_label():
    class FakePipe:
        def __call__(self, texts):
            return [{"label": "긍정", "score": 0.8} for _ in texts]
    with patch("app.services.channels._get_finbert", return_value=FakePipe()):
        s = channels._finbert_score(["삼성전자 급등 호재"])
    assert s > 0.5  # 한글 긍정 라벨 인식


def test_finbert_used_when_enabled():
    class FakePipe:
        def __call__(self, texts):
            return [{"label": "positive", "score": 0.9} for _ in texts]

    class R:
        status_code = 200
        def json(self):
            return {"items": [{"title": "x", "summary": "y"}]}

    with patch("app.services.channels.settings.finbert_enabled", True), \
         patch("app.services.channels._get_finbert", return_value=FakePipe()), \
         patch("app.services.channels.httpx.get", return_value=R()):
        s = channels.news_sentiment()
    assert s > 0.5  # FinBERT positive


def test_finbert_falls_back_to_keyword_when_unavailable():
    class R:
        status_code = 200
        def json(self):
            return {"items": [{"title": "surge rally", "summary": "gain"}]}

    with patch("app.services.channels.settings.finbert_enabled", True), \
         patch("app.services.channels._get_finbert", return_value=None), \
         patch("app.services.channels.httpx.get", return_value=R()):
        s = channels.news_sentiment()
    assert s > 0  # 키워드 폴백


def test_news_sentiment_aggregates():
    class R:
        status_code = 200

        def json(self):
            return {"items": [
                {"title": "stocks surge", "summary": "rally gain"},
                {"title": "market plunge", "summary": "loss"},
            ]}

    with patch("app.services.channels.httpx.get", return_value=R()):
        s = channels.news_sentiment()
    assert -1.0 <= s <= 1.0


def test_news_sentiment_fallback():
    with patch("app.services.channels.httpx.get", side_effect=Exception("down")):
        assert channels.news_sentiment() == 0.0


def test_news_provider_broadcasts():
    with patch("app.services.channels.news_sentiment", return_value=0.5):
        arr = channels.news_provider("ANY", 8)
    assert arr.shape[0] == 8
    assert np.all(arr == 0.5)


def _transformers_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except Exception:
        return False


import pytest


@pytest.mark.skipif(not _transformers_available(), reason="transformers 미설치")
def test_finbert_real_model_inference():
    """실 FinBERT 모델 로드·추론 — 긍/부정 부호 검증."""
    pipe = channels._get_finbert()
    if pipe is None:
        pytest.skip("FinBERT 모델 로드 실패(오프라인)")
    pos = channels._finbert_score(["Company profits surge to record high on strong demand"])
    neg = channels._finbert_score(["Company faces massive losses amid bankruptcy fears"])
    assert pos is not None and neg is not None
    assert pos > neg  # 긍정 > 부정


def test_register_sets_providers():
    import app.services.lstm_model as lm
    channels.register()
    try:
        assert lm._macro_provider is channels.macro_provider
        assert lm._news_provider is channels.news_provider
    finally:
        lm.set_channel_providers(macro=None, news=None)
