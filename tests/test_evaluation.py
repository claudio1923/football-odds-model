import numpy as np
import pandas as pd
import pytest

from fbmodel.evaluation import (
    bootstrap_mean_ci,
    brier_binary_rows,
    brier_rows,
    calibration_table,
    estimate_blend_weight,
    expected_calibration_error,
    log_loss_rows,
    paired_bootstrap_diff,
    rps_rows,
    season_blend_weights,
)


# ------------------------------------------------------------------ row losses


def test_log_loss_rows():
    p = np.array([[0.5, 0.3, 0.2], [0.1, 0.1, 0.8]])
    y = np.array([0, 2])
    out = log_loss_rows(p, y)
    np.testing.assert_allclose(out, [-np.log(0.5), -np.log(0.8)], atol=1e-12)


def test_brier_rows():
    p = np.array([[0.5, 0.3, 0.2], [0.1, 0.1, 0.8]])
    y = np.array([0, 1])
    out = brier_rows(p, y)
    np.testing.assert_allclose(
        out, [0.25 + 0.09 + 0.04, 0.01 + 0.81 + 0.64], atol=1e-12
    )


def test_brier_binary_rows():
    out = brier_binary_rows(np.array([0.7, 0.2]), np.array([1, 0]))
    np.testing.assert_allclose(out, [0.09, 0.04], atol=1e-12)


def test_rps_hand_examples():
    p = np.array([[0.5, 0.3, 0.2]])
    assert rps_rows(p, np.array([0]))[0] == pytest.approx(0.145, abs=1e-12)
    # outcome away: cumsum p = 0.5, 0.8 ; cumsum onehot = 0, 0
    assert rps_rows(p, np.array([2]))[0] == pytest.approx(0.5 * (0.25 + 0.64), abs=1e-12)
    perfect = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    np.testing.assert_allclose(rps_rows(perfect, np.array([0, 2])), [0.0, 0.0], atol=1e-12)


# ----------------------------------------------------------------- calibration


def test_calibration_table():
    p = np.array([0.05, 0.07, 0.95, 1.0])
    o = np.array([0, 1, 1, 1])
    t = calibration_table(p, o, 10)
    assert list(t.columns) == ["bin", "lower", "upper", "n", "mean_p", "mean_o"]
    assert list(t["bin"]) == [0, 9]
    assert list(t["n"]) == [2, 2]
    np.testing.assert_allclose(t["lower"], [0.0, 0.9], atol=1e-12)
    np.testing.assert_allclose(t["upper"], [0.1, 1.0], atol=1e-12)
    np.testing.assert_allclose(t["mean_p"], [0.06, 0.975], atol=1e-12)
    np.testing.assert_allclose(t["mean_o"], [0.5, 1.0], atol=1e-12)


def test_ece_perfect_and_miscalibrated():
    p = np.array([0.5] * 10 + [0.2] * 5)
    o = np.array([1] * 5 + [0] * 5 + [1] + [0] * 4)
    assert expected_calibration_error(p, o, 10) == pytest.approx(0.0, abs=1e-12)
    p2 = np.full(10, 0.8)
    o2 = np.array([1] * 5 + [0] * 5)
    assert expected_calibration_error(p2, o2, 10) == pytest.approx(0.3, abs=1e-12)


# ------------------------------------------------------------------- bootstrap


def test_paired_bootstrap_basic():
    rng = np.random.default_rng(0)
    a = rng.normal(1.0, 0.3, 200)
    b = rng.normal(1.02, 0.3, 200)
    r1 = paired_bootstrap_diff(a, b, n_boot=500, seed=5, ci_level=0.95)
    r2 = paired_bootstrap_diff(a, b, n_boot=500, seed=5, ci_level=0.95)
    assert r1 == r2
    assert r1["n"] == 200
    assert r1["mean_diff"] == pytest.approx(a.mean() - b.mean(), abs=1e-12)
    assert r1["ci_low"] <= r1["mean_diff"] <= r1["ci_high"]


def test_paired_bootstrap_degenerate():
    rng = np.random.default_rng(1)
    a = rng.normal(size=50)
    same = paired_bootstrap_diff(a, a.copy(), n_boot=200, seed=1, ci_level=0.95)
    assert same["mean_diff"] == 0 and same["ci_low"] == 0 and same["ci_high"] == 0
    shifted = paired_bootstrap_diff(a + 0.1, a, n_boot=200, seed=1, ci_level=0.95)
    assert shifted["ci_low"] == pytest.approx(0.1, abs=1e-12)
    assert shifted["ci_high"] == pytest.approx(0.1, abs=1e-12)


def test_paired_bootstrap_larger_sample_narrower():
    rng = np.random.default_rng(2)
    widths = []
    for n in (50, 5000):
        a = rng.normal(1.0, 0.5, n)
        b = rng.normal(1.0, 0.5, n)
        r = paired_bootstrap_diff(a, b, n_boot=400, seed=3, ci_level=0.95)
        widths.append(r["ci_high"] - r["ci_low"])
    assert widths[1] < widths[0]


def test_bootstrap_mean_ci():
    rng = np.random.default_rng(4)
    x = rng.normal(2.0, 1.0, 300)
    r = bootstrap_mean_ci(x, n_boot=500, seed=9, ci_level=0.95)
    assert r["n"] == 300
    assert r["mean"] == pytest.approx(x.mean(), abs=1e-12)
    assert r["ci_low"] <= r["mean"] <= r["ci_high"]
    assert r == bootstrap_mean_ci(x, n_boot=500, seed=9, ci_level=0.95)
    const = bootstrap_mean_ci(np.full(20, 0.3), n_boot=100, seed=1, ci_level=0.9)
    assert const["ci_low"] == pytest.approx(0.3, abs=1e-12)
    assert const["ci_high"] == pytest.approx(0.3, abs=1e-12)


# ------------------------------------------------------------------ blend weight

GRID = np.linspace(0.0, 1.0, 11)


def _onehot_like(y, hi):
    n = len(y)
    p = np.full((n, 3), (1 - hi) / 2)
    p[np.arange(n), y] = hi
    return p


def test_blend_weight_bench_better():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 300)
    p_model = np.full((300, 3), 1 / 3)
    p_bench = _onehot_like(y, 0.8)
    assert estimate_blend_weight(p_model, p_bench, y, GRID) < 0.5


def test_blend_weight_model_better():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 300)
    p_model = _onehot_like(y, 0.8)
    p_bench = np.full((300, 3), 1 / 3)
    assert estimate_blend_weight(p_model, p_bench, y, GRID) > 0.5


def test_blend_weight_perfect_model_gives_max_grid():
    rng = np.random.default_rng(0)
    y = rng.integers(0, 3, 200)
    p_model = _onehot_like(y, 0.98)
    p_bench = np.full((200, 3), 1 / 3)
    assert estimate_blend_weight(p_model, p_bench, y, GRID) == GRID.max()


# --------------------------------------------------------- season blend weights


def _dirichlet_probs(rng, n):
    return rng.dirichlet([4, 3, 3], size=n)


def _season_frame(seed=0, leagues=("A", "B"), seasons=("s1", "s2", "s3"), n=30):
    rng = np.random.default_rng(seed)
    parts = []
    for li, league in enumerate(leagues):
        for si, season in enumerate(seasons):
            m = _dirichlet_probs(rng, n)
            b = _dirichlet_probs(rng, n)
            d = pd.DataFrame(
                {
                    "league": league,
                    "season": season,
                    "date": pd.Timestamp("2020-01-01") + pd.to_timedelta(si * 400 + np.arange(n), "D"),
                    "y": rng.integers(0, 3, n),
                    "m_h": m[:, 0], "m_d": m[:, 1], "m_a": m[:, 2],
                    "b_h": b[:, 0], "b_d": b[:, 1], "b_a": b[:, 2],
                }
            )
            parts.append(d)
    return pd.concat(parts, ignore_index=True)


def test_season_blend_weights_shape_and_first_season():
    df = _season_frame()
    out = season_blend_weights(df, GRID)
    for c in ("league", "season", "w", "n_fit"):
        assert c in out.columns
    assert len(out) == 6
    for league in ("A", "B"):
        sub = out[out["league"] == league].set_index("season")
        assert np.isnan(sub.loc["s1", "w"])
        assert sub.loc["s1", "n_fit"] == 0
        assert sub.loc["s2", "n_fit"] == 30
        assert sub.loc["s3", "n_fit"] == 60
        assert sub.loc["s2", "w"] in set(GRID) or np.isclose(GRID, sub.loc["s2", "w"]).any()
        assert not np.isnan(sub.loc["s3", "w"])


def test_season_order_by_earliest_date_not_label():
    df = _season_frame(seasons=("s1", "s2", "s3"))
    df["season"] = df["season"].map({"s1": "z", "s2": "a", "s3": "m"})
    out = season_blend_weights(df, GRID)
    sub = out[out["league"] == "A"].set_index("season")
    assert np.isnan(sub.loc["z", "w"]) and sub.loc["z", "n_fit"] == 0
    assert sub.loc["a", "n_fit"] == 30
    assert sub.loc["m", "n_fit"] == 60


def test_season_weights_no_leakage_from_current_or_future():
    df = _season_frame()
    base = season_blend_weights(df, GRID).set_index(["league", "season"])
    df2 = df.copy()
    rng = np.random.default_rng(99)
    mask = (df2["league"] == "A") & df2["season"].isin(["s2", "s3"])
    n = int(mask.sum())
    df2.loc[mask, "y"] = rng.integers(0, 3, n)
    m = _dirichlet_probs(rng, n)
    b = _dirichlet_probs(rng, n)
    df2.loc[mask, ["m_h", "m_d", "m_a"]] = m
    df2.loc[mask, ["b_h", "b_d", "b_a"]] = b
    new = season_blend_weights(df2, GRID).set_index(["league", "season"])
    for key in [("A", "s1"), ("A", "s2")]:
        a, b_ = base.loc[key, "w"], new.loc[key, "w"]
        assert (np.isnan(a) and np.isnan(b_)) or a == b_
    # league B untouched entirely (leagues independent)
    for season in ("s1", "s2", "s3"):
        a, b_ = base.loc[("B", season), "w"], new.loc[("B", season), "w"]
        assert (np.isnan(a) and np.isnan(b_)) or a == b_
    assert (base.loc[("B", "s3"), "n_fit"]) == (new.loc[("B", "s3"), "n_fit"])
