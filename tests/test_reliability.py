import numpy as np
import pandas as pd
import pytest

from fbmodel.data.reliability import first_suspect_month, implied_probs, monthly_diagnostics

CFG = {
    "pinnacle_checks": {
        "min_coverage": 0.95,
        "stale_share_min": 0.10,
        "stale_share_multiple": 3,
        "overround_range": [1.00, 1.08],
        "divergence_p95_max": 0.05,
        "min_valid_odds": 1.0,
        "quantile_low": 0.05,
        "quantile_high": 0.95,
    }
}

PRE = {"PS": ["PSH", "PSD", "PSA"], "Avg": ["AvgH", "AvgD", "AvgA"], "Max": ["MaxH", "MaxD", "MaxA"]}
CLOSE = {
    "PS": ["PSCH", "PSCD", "PSCA"],
    "Avg": ["AvgCH", "AvgCD", "AvgCA"],
    "Max": ["MaxCH", "MaxCD", "MaxCA"],
}


def _odds_for(i):
    # probabilities summing to 1, odds carry an overround of 1.04
    base = np.array([0.45, 0.28, 0.27])
    shift = 0.001 * (i % 5)
    p = base + np.array([shift, -shift, 0.0])
    return 1.0 / (p * 1.04)


def _make(n, stale_idx=(), date="2023-03-{:02d}", league="L1", close_scale=1.01):
    rows = []
    for i in range(n):
        o = _odds_for(i)
        c = o if i in stale_idx else o * close_scale
        row = {"league": league, "date": pd.Timestamp(date.format(i + 1))}
        for k, cols in PRE.items():
            mult = 1.02 if k == "Max" else 1.0
            for col, v in zip(cols, o):
                row[col] = v * mult
        for k, cols in CLOSE.items():
            mult = 1.02 if k == "Max" else 1.0
            for col, v in zip(cols, c):
                row[col] = v * mult
        rows.append(row)
    return pd.DataFrame(rows)


def _row(diag, market="1x2"):
    sub = diag[diag["market"] == market]
    assert len(sub) == 1
    return sub.iloc[0]


def test_implied_probs_example():
    df = pd.DataFrame({"H": [2.0], "D": [3.4], "A": [4.0]})
    out = implied_probs(df)
    assert list(out.columns) == ["H", "D", "A"]
    total = 0.5 + 1 / 3.4 + 0.25
    np.testing.assert_allclose(
        out.iloc[0].to_numpy(), [0.5 / total, (1 / 3.4) / total, 0.25 / total], atol=1e-9
    )
    assert out.iloc[0].sum() == pytest.approx(1.0)
    assert out.iloc[0, 0] == pytest.approx(0.5 / 1.0441176, abs=1e-6)


def test_implied_probs_nan_and_nonpositive_rows():
    df = pd.DataFrame(
        {"H": [2.0, np.nan, 2.0, 2.0], "D": [3.4, 3.0, 3.4, 3.4], "A": [4.0, 4.0, 0.0, 4.0]},
        index=[10, 11, 12, 13],
    )
    out = implied_probs(df)
    assert list(out.index) == [10, 11, 12, 13]
    assert out.loc[10].sum() == pytest.approx(1.0)
    assert out.loc[11].isna().all()
    assert out.loc[12].isna().all()
    assert out.loc[13].sum() == pytest.approx(1.0)


def test_stale_share():
    df = _make(10, stale_idx={0, 1, 2})
    diag = monthly_diagnostics(df, CFG)
    r = _row(diag)
    assert r["league"] == "L1"
    assert r["month"] == "2023-03"
    assert r["n_matches"] == 10
    assert r["stale_share"] == pytest.approx(0.3)


def test_coverage_nine_of_ten_suspect():
    df = _make(10)
    df.loc[0, "PSH"] = np.nan
    diag = monthly_diagnostics(df, CFG)
    r = _row(diag)
    assert r["pin_pre_coverage"] == pytest.approx(0.9)
    assert r["pin_close_coverage"] == pytest.approx(1.0)
    assert bool(r["suspect"]) is True


def test_single_match_overround():
    df = pd.DataFrame(
        [{
            "league": "L1", "date": pd.Timestamp("2023-03-05"),
            "PSH": 2.0, "PSD": 3.4, "PSA": 4.0,
            "PSCH": 2.0, "PSCD": 3.4, "PSCA": 4.0,
            "AvgH": 2.0, "AvgD": 3.4, "AvgA": 4.0,
            "AvgCH": 2.0, "AvgCD": 3.4, "AvgCA": 4.0,
            "MaxH": 2.0, "MaxD": 3.4, "MaxA": 4.0,
            "MaxCH": 2.0, "MaxCD": 3.4, "MaxCA": 4.0,
        }]
    )
    diag = monthly_diagnostics(df, CFG)
    r = _row(diag)
    assert r["overround_pre_median"] == pytest.approx(1.0441176, abs=1e-6)
    assert r["overround_close_median"] == pytest.approx(1.0441176, abs=1e-6)


def test_clean_month_not_suspect_and_columns():
    df = _make(20)
    diag = monthly_diagnostics(df, CFG)
    expected = [
        "league", "month", "market", "n_matches", "pin_pre_coverage", "pin_close_coverage",
        "stale_share", "overround_pre_median", "overround_pre_p5", "overround_pre_p95",
        "overround_close_median", "overround_close_p5", "overround_close_p95",
        "divergence_pre_median", "divergence_pre_p95", "divergence_close_median",
        "divergence_close_p95", "max_below_pin_pre", "max_below_pin_close", "suspect",
        "suspect_reasons",
    ]
    for c in expected:
        assert c in diag.columns
    r = _row(diag)
    assert r["pin_pre_coverage"] == pytest.approx(1.0)
    assert r["pin_close_coverage"] == pytest.approx(1.0)
    assert r["stale_share"] == pytest.approx(0.0)
    assert bool(r["suspect"]) is False


def test_only_1x2_rows_when_only_1x2_columns():
    diag = monthly_diagnostics(_make(5), CFG)
    assert set(diag["market"]) == {"1x2"}


def test_two_leagues_two_months_rows():
    a = _make(5, league="A", date="2023-03-{:02d}")
    b = _make(5, league="B", date="2023-04-{:02d}")
    diag = monthly_diagnostics(pd.concat([a, b], ignore_index=True), CFG)
    got = {(r.league, r.month) for r in diag.itertuples()}
    assert got == {("A", "2023-03"), ("B", "2023-04")}


def test_first_suspect_month():
    diag = pd.DataFrame(
        {
            "league": ["A", "A", "A", "B", "B", "C", "C"],
            "month": ["2023-07", "2023-03", "2023-01", "2023-02", "2023-05", "2023-01", "2023-02"],
            "market": ["1x2", "1x2", "ou25", "1x2", "1x2", "ou25", "1x2"],
            "suspect": [True, True, True, False, False, True, False],
        }
    )
    out = first_suspect_month(diag)
    assert out["A"] == "2023-03"
    assert out["B"] is None
    assert out["C"] is None


def _set_avg(df, pre, close):
    for col, v in zip(PRE["Avg"], pre):
        df[col] = v
    for col, v in zip(CLOSE["Avg"], close):
        df[col] = v
    return df


def test_divergence_zero_when_avg_equals_pinnacle():
    df = _make(10)
    for a, b in zip(PRE["Avg"] + CLOSE["Avg"], PRE["PS"] + CLOSE["PS"]):
        df[a] = df[b]
    r = _row(monthly_diagnostics(df, CFG))
    for c in ("divergence_pre_median", "divergence_pre_p95",
              "divergence_close_median", "divergence_close_p95"):
        assert not pd.isna(r[c])
        assert r[c] == pytest.approx(0.0, abs=1e-12)


def test_divergence_single_match_value():
    pin = np.array([2.0, 3.4, 4.0])
    avg = np.array([2.2, 3.2, 3.8])
    df = _make(1)
    for cols, v in ((PRE["PS"], pin), (CLOSE["PS"], pin), (PRE["Avg"], avg), (CLOSE["Avg"], avg)):
        for c, x in zip(cols, v):
            df[c] = x
    p_pin = (1 / pin) / (1 / pin).sum()
    p_avg = (1 / avg) / (1 / avg).sum()
    expected = np.max(np.abs(p_pin - p_avg))
    r = _row(monthly_diagnostics(df, CFG))
    for c in ("divergence_pre_median", "divergence_pre_p95",
              "divergence_close_median", "divergence_close_p95"):
        assert r[c] == pytest.approx(expected, abs=1e-9)


def test_divergence_nan_when_avg_columns_absent():
    df = _make(5).drop(columns=PRE["Avg"] + CLOSE["Avg"])
    r = _row(monthly_diagnostics(df, CFG))
    assert pd.isna(r["divergence_pre_median"])
    assert pd.isna(r["divergence_close_p95"])


def test_large_divergence_is_suspect_with_reason():
    df = _set_avg(_make(10), [3.0, 3.0, 3.0], [3.0, 3.0, 3.0])
    r = _row(monthly_diagnostics(df, CFG))
    assert r["divergence_pre_p95"] > 0.05
    assert bool(r["suspect"]) is True
    assert "divergence" in str(r["suspect_reasons"]).lower()


def test_max_below_pin_share():
    df = _make(10)
    for a, b in zip(PRE["Max"] + CLOSE["Max"], PRE["PS"] + CLOSE["PS"]):
        df[a] = df[b] * 1.02
    r = _row(monthly_diagnostics(df, CFG))
    assert r["max_below_pin_pre"] == pytest.approx(0.0)
    assert r["max_below_pin_close"] == pytest.approx(0.0)
    df["MaxH"] = df["PSH"] * 0.98
    df["MaxCH"] = df["PSCH"] * 0.98
    r = _row(monthly_diagnostics(df, CFG))
    assert r["max_below_pin_pre"] == pytest.approx(1.0)
    assert r["max_below_pin_close"] == pytest.approx(1.0)
