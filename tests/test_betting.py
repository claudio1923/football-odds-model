import numpy as np
import pandas as pd
import pytest

from fbmodel.betting import (
    bet_stats,
    clv,
    closing_fair_odds,
    longest_losing_streak,
    max_drawdown,
    select_bets,
    settle_bets,
)

CFG = {"evaluation": {"max_bet_odds": 10}}


def devig(odds):
    inv = 1.0 / np.asarray(odds, dtype=float)
    return inv / inv.sum()


# ---------------------------------------------------------------- helper maths


def test_closing_fair_odds():
    out = closing_fair_odds(np.array([[2.0, 3.4, 4.0]]), np.array([0]))
    assert out[0] == pytest.approx(2.088235, abs=1e-5)
    rows = np.array([[2.0, 3.4, 4.0], [1.5, 4.0, 7.0]])
    out = closing_fair_odds(rows, np.array([2, 1]))
    assert out[0] == pytest.approx(1 / devig(rows[0])[2], abs=1e-9)
    assert out[1] == pytest.approx(1 / devig(rows[1])[1], abs=1e-9)


def test_clv():
    assert float(clv(2.10, 2.00)) == pytest.approx(0.05, abs=1e-12)


def test_longest_losing_streak():
    assert longest_losing_streak([-1, -1, 1, -1, -1, -1, 0.5]) == 3
    assert longest_losing_streak([]) == 0
    assert longest_losing_streak([-1, 0, -1]) == 1


def test_max_drawdown():
    assert max_drawdown([1, 1, -1, -1, -1, 2]) == pytest.approx(3.0)
    assert max_drawdown([1, 2, 3]) == pytest.approx(0.0)
    assert max_drawdown([-1, -1]) == pytest.approx(2.0)


# -------------------------------------------------------------------- bet_stats


def test_bet_stats_hand():
    bets = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"]
            ),
            "match_id": ["m1", "m2", "m3", "m4", "m5", "m6"],
            "profit": [1.0, -1.0, -1.0, 1.5, -1.0, -1.0],
            "clv": [0.05, np.nan, -0.02, 0.1, np.nan, 0.0],
        }
    )
    shuffled = bets.sample(frac=1.0, random_state=3)
    for b in (bets, shuffled):
        s = bet_stats(b, n_boot=200, seed=1, ci_level=0.95)
        assert s["n_bets"] == 6
        assert s["roi"] == pytest.approx(-0.25, abs=1e-12)
        assert s["roi_ci_low"] <= s["roi_ci_high"]
        assert s["mean_clv"] == pytest.approx(0.0325, abs=1e-12)
        assert s["n_clv"] == 4
        assert s["share_beating_close"] == pytest.approx(0.5, abs=1e-12)
        assert s["longest_losing_streak"] == 2
        assert s["max_drawdown"] == pytest.approx(2.5, abs=1e-12)
        assert s["clv_ci_low"] <= s["clv_ci_high"]


def test_bet_stats_empty():
    empty = pd.DataFrame({"date": [], "match_id": [], "profit": [], "clv": []})
    s = bet_stats(empty, n_boot=50, seed=1, ci_level=0.95)
    assert s["n_bets"] == 0
    for k in ("roi", "roi_ci_low", "roi_ci_high", "mean_clv", "clv_ci_low", "clv_ci_high",
              "share_beating_close"):
        assert np.isnan(s[k]), k
    assert s["longest_losing_streak"] == 0
    assert s["max_drawdown"] == 0


# ----------------------------------------------------------------- select_bets

ONE_X_TWO_ODDS = (2.2, 3.5, 5.0)


def _match(mid, **over):
    row = {
        "match_id": mid, "league": "E0", "season": "2425",
        "date": pd.Timestamp("2025-01-10"), "result": "H", "home_goals": 2, "away_goals": 1,
        "ah_line_pre": -0.5, "ah_line_close": -0.5,
        "ref_source_1x2_close": "pin", "ref_source_ou25_close": "pin", "ref_source_ah_close": "pin",
        "odds_1x2_max_pre_h": ONE_X_TWO_ODDS[0], "odds_1x2_max_pre_d": ONE_X_TWO_ODDS[1],
        "odds_1x2_max_pre_a": ONE_X_TWO_ODDS[2],
        "odds_ou25_max_pre_over": 1.9, "odds_ou25_max_pre_under": 2.0,
        "odds_ah_max_pre_home": 2.0, "odds_ah_max_pre_away": 1.8,
        "odds_1x2_pin_close_h": 2.0, "odds_1x2_pin_close_d": 3.4, "odds_1x2_pin_close_a": 4.0,
        "odds_ou25_pin_close_over": 1.9, "odds_ou25_pin_close_under": 2.0,
        "odds_ah_pin_close_home": 1.95, "odds_ah_pin_close_away": 1.95,
    }
    row.update(over)
    return row


def _pred(mid, **over):
    row = {
        "match_id": mid, "p_home": 0.5, "p_draw": 0.3, "p_away": 0.2,
        "p_over25": 0.55, "p_under25": 0.45,
        "ah_line": -0.5, "ah_full_win": 0.6, "ah_half_win": 0.0, "ah_push": 0.0,
        "ah_half_loss": 0.0, "ah_full_loss": 0.4, "ah_fair_odds": 1 + 0.4 / 0.6,
        "bl_home": 0.5, "bl_draw": 0.3, "bl_away": 0.2,
    }
    row.update(over)
    return row


def _frames(match_overs=(), pred_overs=()):
    ms = [_match(f"m{i}", **o) for i, o in enumerate(match_overs)]
    ps = [_pred(f"m{i}", **o) for i, o in enumerate(pred_overs)]
    return pd.DataFrame(ms), pd.DataFrame(ps)


def _bets_for(bets, market):
    return bets[bets["market"] == market]


def test_1x2_threshold_and_best_edge():
    m, p = _frames([{}], [{}])
    bets, _ = select_bets(m, p, CFG, "model", 0.02)
    b = _bets_for(bets, "1x2")
    assert len(b) == 1
    r = b.iloc[0]
    assert r["outcome"] == "H"
    assert r["odds"] == pytest.approx(2.2)
    assert r["p"] == pytest.approx(0.5)
    assert r["edge"] == pytest.approx(0.10, abs=1e-9)
    assert r["signal"] == "model"
    assert r["threshold"] == pytest.approx(0.02)
    assert r["match_id"] == "m0"
    assert r["market"] == "1x2"
    high, _ = select_bets(m, p, CFG, "model", 0.12)
    assert len(_bets_for(high, "1x2")) == 0


def test_1x2_picks_largest_edge_not_first():
    m, p = _frames([{}], [{"p_home": 0.3, "p_draw": 0.5, "p_away": 0.2}])
    bets, _ = select_bets(m, p, CFG, "model", 0.02)
    b = _bets_for(bets, "1x2")
    assert list(b["outcome"]) == ["D"]
    assert b.iloc[0]["edge"] == pytest.approx(0.75, abs=1e-9)


def test_at_most_one_bet_per_match_market():
    rng = np.random.default_rng(0)
    m, p = _random_frames(rng, 40)
    bets, _ = select_bets(m, p, CFG, "model", 0.0)
    assert bets.groupby(["match_id", "market"]).size().max() == 1


def test_odds_above_cap_excluded():
    m, p = _frames(
        [{"odds_1x2_max_pre_h": 12.0, "odds_1x2_max_pre_d": 3.0, "odds_1x2_max_pre_a": 3.0}],
        [{"p_home": 0.3, "p_draw": 0.4, "p_away": 0.3}],
    )
    bets, _ = select_bets(m, p, CFG, "model", 0.02)
    b = _bets_for(bets, "1x2")
    assert list(b["outcome"]) == ["D"]


def test_nan_odds_skipped_and_counted():
    m, p = _frames([{"odds_1x2_max_pre_d": np.nan}, {}], [{}, {}])
    bets, skipped = select_bets(m, p, CFG, "model", 0.02)
    b = _bets_for(bets, "1x2")
    assert "m0" not in set(b["match_id"])
    assert "m1" in set(b["match_id"])
    for c in ("market", "reason", "n"):
        assert c in skipped.columns
    assert skipped[skipped["market"] == "1x2"]["n"].sum() > 0


def test_ref_source_none_gives_no_bet_in_that_market():
    m, p = _frames([{"ref_source_1x2_close": "none"}], [{}])
    bets, _ = select_bets(m, p, CFG, "model", 0.02)
    assert len(_bets_for(bets, "1x2")) == 0
    assert len(_bets_for(bets, "ou25")) == 1
    m, p = _frames([{"ref_source_ou25_close": "none", "ref_source_ah_close": "none"}], [{}])
    bets, _ = select_bets(m, p, CFG, "model", 0.02)
    assert len(_bets_for(bets, "ou25")) == 0
    assert len(_bets_for(bets, "ah")) == 0
    assert len(_bets_for(bets, "1x2")) == 1


def test_ou25_bet():
    m, p = _frames([{}], [{}])
    bets, _ = select_bets(m, p, CFG, "model", 0.02)
    r = _bets_for(bets, "ou25").iloc[0]
    assert r["outcome"] == "over"
    assert r["odds"] == pytest.approx(1.9)
    assert r["edge"] == pytest.approx(0.55 * 1.9 - 1, abs=1e-9)


def test_ah_half_line_home_bet():
    m, p = _frames([{}], [{}])
    bets, _ = select_bets(m, p, CFG, "model", 0.05)
    r = _bets_for(bets, "ah").iloc[0]
    assert r["outcome"] == "home"
    assert r["odds"] == pytest.approx(2.0)
    assert r["edge"] == pytest.approx(0.6 * 1.0 - 0.4, abs=1e-9)


def test_ah_quarter_line_home_edge_formula():
    probs = {
        "ah_line": -0.25, "ah_full_win": 0.4, "ah_half_win": 0.1, "ah_push": 0.1,
        "ah_half_loss": 0.1, "ah_full_loss": 0.3, "ah_fair_odds": 2.0,
    }
    m, p = _frames([{"ah_line_pre": -0.25, "odds_ah_max_pre_home": 2.0, "odds_ah_max_pre_away": 2.2}],
                   [probs])
    bets, _ = select_bets(m, p, CFG, "model", 0.05)
    r = _bets_for(bets, "ah").iloc[0]
    assert r["outcome"] == "home"
    assert r["edge"] == pytest.approx(0.1, abs=1e-9)


def test_ah_away_side_edge_formula():
    probs = {
        "ah_line": -0.25, "ah_full_win": 0.3, "ah_half_win": 0.1, "ah_push": 0.1,
        "ah_half_loss": 0.1, "ah_full_loss": 0.4, "ah_fair_odds": 2.0,
    }
    m, p = _frames([{"ah_line_pre": -0.25, "odds_ah_max_pre_home": 2.0, "odds_ah_max_pre_away": 2.2}],
                   [probs])
    bets, _ = select_bets(m, p, CFG, "model", 0.05)
    r = _bets_for(bets, "ah").iloc[0]
    assert r["outcome"] == "away"
    assert r["odds"] == pytest.approx(2.2)
    assert r["edge"] == pytest.approx(0.19, abs=1e-9)


def test_blend_signal_only_1x2():
    m, p = _frames([{}], [{"bl_home": 0.2, "bl_draw": 0.2, "bl_away": 0.6}])
    bets, _ = select_bets(m, p, CFG, "blend", 0.02)
    assert set(bets["market"]) <= {"1x2"}
    r = bets.iloc[0]
    assert r["outcome"] == "A"
    assert r["signal"] == "blend"
    assert r["p"] == pytest.approx(0.6)
    assert r["edge"] == pytest.approx(0.6 * 5.0 - 1, abs=1e-9)


def test_blend_nan_gives_no_bet():
    m, p = _frames([{}], [{"bl_home": np.nan, "bl_draw": np.nan, "bl_away": np.nan}])
    bets, _ = select_bets(m, p, CFG, "blend", 0.02)
    assert len(bets) == 0


def _random_frames(rng, n):
    ms, ps = [], []
    lines = [-1.0, -0.75, -0.5, -0.25, 0.0, 0.25, 0.5]
    for i in range(n):
        pr = rng.dirichlet([5, 3, 4])
        fair = 1 / pr
        ov = rng.uniform(0.45, 0.6)
        ao = rng.dirichlet(np.ones(5) * 2)
        line = lines[i % len(lines)]
        ms.append(
            _match(
                f"r{i}",
                date=pd.Timestamp("2025-01-01") + pd.Timedelta(days=i),
                ah_line_pre=line, ah_line_close=line,
                odds_1x2_max_pre_h=float(fair[0] * rng.uniform(0.85, 1.2)),
                odds_1x2_max_pre_d=float(fair[1] * rng.uniform(0.85, 1.2)),
                odds_1x2_max_pre_a=float(fair[2] * rng.uniform(0.85, 1.2)),
                odds_ou25_max_pre_over=float(rng.uniform(1.7, 2.2)),
                odds_ou25_max_pre_under=float(rng.uniform(1.7, 2.2)),
                odds_ah_max_pre_home=float(rng.uniform(1.7, 2.2)),
                odds_ah_max_pre_away=float(rng.uniform(1.7, 2.2)),
                odds_1x2_pin_close_h=float(fair[0]), odds_1x2_pin_close_d=float(fair[1]),
                odds_1x2_pin_close_a=float(fair[2]),
                result=str(rng.choice(["H", "D", "A"])),
                home_goals=int(rng.integers(0, 5)), away_goals=int(rng.integers(0, 5)),
            )
        )
        ps.append(
            _pred(
                f"r{i}", p_home=float(pr[0]), p_draw=float(pr[1]), p_away=float(pr[2]),
                p_over25=float(ov), p_under25=float(1 - ov), ah_line=line,
                ah_full_win=float(ao[0]), ah_half_win=float(ao[1]), ah_push=float(ao[2]),
                ah_half_loss=float(ao[3]), ah_full_loss=float(ao[4]),
                ah_fair_odds=2.0,
                bl_home=float(pr[1]), bl_draw=float(pr[0]), bl_away=float(pr[2]),
            )
        )
    return pd.DataFrame(ms), pd.DataFrame(ps)


def _key_set(bets):
    return set(zip(bets["match_id"], bets["market"], bets["outcome"]))


@pytest.mark.parametrize("signal", ["model", "blend"])
def test_thresholds_nested(signal):
    rng = np.random.default_rng(5)
    m, p = _random_frames(rng, 60)
    b02, _ = select_bets(m, p, CFG, signal, 0.02)
    b05, _ = select_bets(m, p, CFG, signal, 0.05)
    b10, _ = select_bets(m, p, CFG, signal, 0.10)
    assert len(b02) > 0
    assert _key_set(b10) <= _key_set(b05) <= _key_set(b02)


@pytest.mark.parametrize("signal", ["model", "blend"])
@pytest.mark.parametrize("threshold", [0.02, 0.05, 0.10])
def test_invariance_to_closing_and_results(signal, threshold):
    rng = np.random.default_rng(8)
    m, p = _random_frames(rng, 50)
    base, _ = select_bets(m, p, CFG, signal, threshold)
    m2 = m.copy()
    scr = np.random.default_rng(123)
    for c in [c for c in m2.columns if "_pin_close_" in c] + ["ah_line_close"]:
        m2[c] = scr.permutation(m2[c].to_numpy())
    perm = scr.permutation(len(m2))
    for c in ("result", "home_goals", "away_goals"):
        m2[c] = m2[c].to_numpy()[perm]
    assert (m2["ref_source_1x2_close"] == m["ref_source_1x2_close"]).all()
    new, _ = select_bets(m2, p, CFG, signal, threshold)
    pd.testing.assert_frame_equal(base, new)


# ----------------------------------------------------------------- settle_bets


def _bet(mid, market, outcome, odds, **over):
    row = {
        "match_id": mid, "league": "E0", "season": "2425", "date": pd.Timestamp("2025-01-10"),
        "market": market, "signal": "model", "outcome": outcome, "odds": odds,
        "p": 0.5, "edge": 0.1, "threshold": 0.02,
    }
    row.update(over)
    return row


def test_settle_1x2_win_loss_and_clv():
    m = pd.DataFrame([_match("a", result="H"), _match("b", result="A")])
    bets = pd.DataFrame([_bet("a", "1x2", "H", 2.2), _bet("b", "1x2", "D", 3.5)])
    out = settle_bets(bets, m)
    for c in ("profit", "fair_close_odds", "clv"):
        assert c in out.columns
    assert list(out["match_id"]) == ["a", "b"]
    assert out.loc[0, "profit"] == pytest.approx(1.2, abs=1e-12)
    assert out.loc[1, "profit"] == pytest.approx(-1.0, abs=1e-12)
    fair_h = 1 / devig([2.0, 3.4, 4.0])[0]
    fair_d = 1 / devig([2.0, 3.4, 4.0])[1]
    assert out.loc[0, "fair_close_odds"] == pytest.approx(fair_h, abs=1e-9)
    assert out.loc[0, "clv"] == pytest.approx(2.2 / fair_h - 1, abs=1e-9)
    assert out.loc[1, "fair_close_odds"] == pytest.approx(fair_d, abs=1e-9)


def test_settle_ou25():
    m = pd.DataFrame(
        [_match("a", home_goals=2, away_goals=1), _match("b", home_goals=1, away_goals=1)]
    )
    bets = pd.DataFrame(
        [_bet("a", "ou25", "over", 1.9), _bet("b", "ou25", "over", 1.9),
         _bet("b", "ou25", "under", 2.0)]
    )
    out = settle_bets(bets, m)
    assert out.loc[0, "profit"] == pytest.approx(0.9, abs=1e-12)
    assert out.loc[1, "profit"] == pytest.approx(-1.0, abs=1e-12)
    assert out.loc[2, "profit"] == pytest.approx(1.0, abs=1e-12)
    fair_over = 1 / devig([1.9, 2.0])[0]
    assert out.loc[0, "fair_close_odds"] == pytest.approx(fair_over, abs=1e-9)
    assert out.loc[0, "clv"] == pytest.approx(1.9 / fair_over - 1, abs=1e-9)


def test_settle_ah_quarter_lines():
    m = pd.DataFrame(
        [_match("a", home_goals=1, away_goals=1, ah_line_pre=-0.25, ah_line_close=-0.25)]
    )
    bets = pd.DataFrame(
        [_bet("a", "ah", "home", 2.0), _bet("a", "ah", "away", 1.9)]
    )
    out = settle_bets(bets, m)
    assert out.loc[0, "profit"] == pytest.approx(-0.5, abs=1e-12)
    assert out.loc[1, "profit"] == pytest.approx(0.5 * 0.9, abs=1e-12)
    fair_home = 1 / devig([1.95, 1.95])[0]
    assert out.loc[0, "fair_close_odds"] == pytest.approx(fair_home, abs=1e-9)
    assert out.loc[0, "clv"] == pytest.approx(2.0 / fair_home - 1, abs=1e-9)


@pytest.mark.parametrize("close_line", [-0.5, np.nan])
def test_settle_ah_line_moved_gives_nan_clv(close_line):
    m = pd.DataFrame(
        [_match("a", home_goals=2, away_goals=0, ah_line_pre=-0.25, ah_line_close=close_line)]
    )
    out = settle_bets(pd.DataFrame([_bet("a", "ah", "home", 2.0)]), m)
    assert out.loc[0, "profit"] == pytest.approx(1.0, abs=1e-12)
    assert np.isnan(out.loc[0, "fair_close_odds"])
    assert np.isnan(out.loc[0, "clv"])
