import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from fbmodel.model.dixon_coles import (
    fit_dc,
    markets_from_matrix,
    score_matrix,
    tau,
    walk_forward,
)


def make_cfg(xi=0.0019, l2=1.0, refit_days=7):
    return {
        "model": {
            "xi": xi,
            "l2_penalty": l2,
            "refit_days": refit_days,
            "max_goals": 10,
            "min_team_matches": 5,
            "rho_bounds": [-0.3, 0.3],
            "tau_floor": 1e-6,
            "maxiter": 500,
            "ou_line": 2.5,
        }
    }


# ------------------------------------------------------------------------ tau


def test_tau_special_cells():
    lam, mu, rho = 1.5, 1.2, -0.1
    assert float(tau(0, 0, lam, mu, rho)) == pytest.approx(1 - lam * mu * rho, abs=1e-12)
    assert float(tau(0, 1, lam, mu, rho)) == pytest.approx(1 + lam * rho, abs=1e-12)
    assert float(tau(1, 0, lam, mu, rho)) == pytest.approx(1 + mu * rho, abs=1e-12)
    assert float(tau(1, 1, lam, mu, rho)) == pytest.approx(1 - rho, abs=1e-12)
    assert float(tau(0, 0, lam, mu, rho)) == pytest.approx(1.18, abs=1e-12)
    assert float(tau(0, 1, lam, mu, rho)) == pytest.approx(0.85, abs=1e-12)
    assert float(tau(1, 0, lam, mu, rho)) == pytest.approx(0.88, abs=1e-12)
    assert float(tau(1, 1, lam, mu, rho)) == pytest.approx(1.1, abs=1e-12)


@pytest.mark.parametrize("x,y", [(2, 0), (0, 2), (3, 3), (2, 1), (1, 2)])
def test_tau_other_cells_are_one(x, y):
    assert float(tau(x, y, 1.5, 1.2, -0.1)) == pytest.approx(1.0, abs=1e-12)


def test_tau_vectorised():
    x = np.array([0, 0, 1, 1, 2])
    y = np.array([0, 1, 0, 1, 0])
    out = np.asarray(tau(x, y, 1.5, 1.2, -0.1))
    np.testing.assert_allclose(out, [1.18, 0.85, 0.88, 1.1, 1.0], atol=1e-12)


# --------------------------------------------------------------- score_matrix


def test_score_matrix_rho_zero_is_outer_product():
    lh, la, g = 1.7, 1.1, 10
    M = score_matrix(lh, la, 0.0, g)
    assert M.shape == (g + 1, g + 1)
    ks = np.arange(g + 1)
    expected = np.outer(poisson.pmf(ks, lh), poisson.pmf(ks, la))
    np.testing.assert_allclose(M, expected, atol=1e-12, rtol=0)


def _direct(lh, la, rho, g):
    M = np.zeros((g + 1, g + 1))
    for x in range(g + 1):
        for y in range(g + 1):
            t = 1.0
            if (x, y) == (0, 0):
                t = 1 - lh * la * rho
            elif (x, y) == (0, 1):
                t = 1 + lh * rho
            elif (x, y) == (1, 0):
                t = 1 + la * rho
            elif (x, y) == (1, 1):
                t = 1 - rho
            M[x, y] = poisson.pmf(x, lh) * poisson.pmf(y, la) * t
    return M


def test_score_matrix_matches_direct_and_mass():
    lh, la, rho, g = 2.4, 1.9, -0.12, 6
    M = score_matrix(lh, la, rho, g)
    D = _direct(lh, la, rho, g)
    np.testing.assert_allclose(M, D, atol=1e-12)
    assert M.sum() == pytest.approx(D.sum(), abs=1e-9)
    assert M.sum() < 1.0


def test_score_matrix_sums_to_one_with_large_max_goals():
    M = score_matrix(0.8, 0.7, -0.1, 30)
    assert M.sum() == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------- markets_from_matrix


def test_markets_basic_consistency():
    M = score_matrix(1.6, 1.1, -0.08, 10)
    Mn = M / M.sum()
    out = markets_from_matrix(M)
    assert out["p_home"] + out["p_draw"] + out["p_away"] == pytest.approx(1.0, abs=1e-9)
    assert out["p_over"] + out["p_under"] == pytest.approx(1.0, abs=1e-9)
    assert out["p_btts"] == pytest.approx(Mn[1:, 1:].sum(), abs=1e-9)
    assert out["p_home"] == pytest.approx(np.tril(Mn, -1).sum(), abs=1e-9)
    assert out["p_draw"] == pytest.approx(np.trace(Mn), abs=1e-9)
    x, y = np.indices(Mn.shape)
    assert out["p_over"] == pytest.approx(Mn[(x + y) > 2.5].sum(), abs=1e-9)


@pytest.mark.parametrize("line", [-1.5 + 0.25 * i for i in range(13)])
def test_ah_probabilities_sum_to_one(line):
    M = score_matrix(1.6, 1.1, -0.08, 10)
    out = markets_from_matrix(M, ah_line=line)
    total = sum(
        out[k] for k in ("ah_full_win", "ah_half_win", "ah_push", "ah_half_loss", "ah_full_loss")
    )
    assert total == pytest.approx(1.0, abs=1e-9)
    assert out["ah_line"] == line


def test_ah_line_zero_fair_odds():
    M = score_matrix(1.6, 1.1, -0.08, 10)
    out = markets_from_matrix(M, ah_line=0.0)
    assert 1 / out["ah_fair_odds"] == pytest.approx(
        out["p_home"] / (out["p_home"] + out["p_away"]), abs=1e-9
    )


def test_ah_line_half_goal():
    M = score_matrix(1.6, 1.1, -0.08, 10)
    out = markets_from_matrix(M, ah_line=-0.5)
    assert out["ah_full_win"] == pytest.approx(out["p_home"], abs=1e-9)
    assert out["ah_full_loss"] == pytest.approx(out["p_draw"] + out["p_away"], abs=1e-9)
    assert out["ah_half_win"] == pytest.approx(0.0, abs=1e-12)
    assert out["ah_half_loss"] == pytest.approx(0.0, abs=1e-12)
    assert out["ah_push"] == pytest.approx(0.0, abs=1e-12)


def test_ah_fair_odds_zero_expected_profit_quarter_line():
    M = score_matrix(1.6, 1.1, -0.08, 10)
    out = markets_from_matrix(M, ah_line=-0.25)
    o = out["ah_fair_odds"]
    ev = (
        out["ah_full_win"] * (o - 1)
        + out["ah_half_win"] * 0.5 * (o - 1)
        - out["ah_half_loss"] * 0.5
        - out["ah_full_loss"]
    )
    assert ev == pytest.approx(0.0, abs=1e-9)


# ------------------------------------------------------------------- fit_dc


def _true_params(teams, rng, sd=0.25):
    att = {t: rng.normal(0, sd) for t in teams}
    dfn = {t: rng.normal(0, sd) for t in teams}
    return att, dfn


def _simulate(n, teams, att, dfn, mu, home_adv, rho, rng, start="2019-08-01", days=1095):
    rows = []
    start = pd.Timestamp(start)
    for _ in range(n):
        h, a = rng.choice(len(teams), size=2, replace=False)
        th, ta = teams[h], teams[a]
        lh = np.exp(mu + home_adv + att[th] - dfn[ta])
        la = np.exp(mu + att[ta] - dfn[th])
        M = score_matrix(lh, la, rho, 10)
        M = M / M.sum()
        k = rng.choice(M.size, p=M.ravel())
        x, y = divmod(k, M.shape[1])
        rows.append(
            {
                "date": start + pd.Timedelta(days=int(rng.integers(0, days))),
                "home": th, "away": ta, "home_goals": int(x), "away_goals": int(y),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


@pytest.fixture(scope="module")
def sim():
    rng = np.random.default_rng(2024)
    teams = [f"T{i}" for i in range(10)]
    att, dfn = _true_params(teams, rng)
    df = _simulate(3000, teams, att, dfn, 0.1, 0.25, -0.10, rng)
    return teams, att, dfn, df


def test_parameter_recovery(sim):
    teams, att, dfn, df = sim
    ref = df["date"].max() + pd.Timedelta(days=1)
    fit = fit_dc(df, ref, make_cfg(xi=0.0, l2=0.01))
    assert fit["success"] in (True, False)
    assert fit["n_matches"] == len(df)
    assert fit["teams"] == sorted(teams)
    # standard errors with n=3000 are roughly 0.03 (home_adv) and 0.04 (rho)
    assert abs(fit["home_adv"] - 0.25) < 0.08
    assert abs(fit["rho"] - (-0.10)) < 0.12
    true_s = [att[t] - dfn[t] for t in sorted(teams)]
    fit_s = [fit["att"][t] - fit["def"][t] for t in sorted(teams)]
    assert np.corrcoef(true_s, fit_s)[0, 1] > 0.9


def test_fit_dc_requires_strictly_earlier_matches(sim):
    _, _, _, df = sim
    small = df.iloc[:300]
    ref = small["date"].max()
    with pytest.raises(AssertionError):
        fit_dc(small, ref, make_cfg())


def test_warm_start_matches_cold(sim):
    _, _, _, df = sim
    small = df.iloc[:500]
    ref = small["date"].max() + pd.Timedelta(days=1)
    cfg = make_cfg()
    cold = fit_dc(small, ref, cfg)
    warm = fit_dc(small, ref, cfg, init=cold)
    assert warm["mu"] == pytest.approx(cold["mu"], abs=1e-3)
    assert warm["home_adv"] == pytest.approx(cold["home_adv"], abs=1e-3)
    assert warm["rho"] == pytest.approx(cold["rho"], abs=1e-3)
    for t in cold["teams"]:
        assert warm["att"][t] == pytest.approx(cold["att"][t], abs=1e-3)
        assert warm["def"][t] == pytest.approx(cold["def"][t], abs=1e-3)


def test_l2_shrinkage(sim):
    _, _, _, df = sim
    small = df.iloc[:800]
    ref = small["date"].max() + pd.Timedelta(days=1)
    strong = fit_dc(small, ref, make_cfg(xi=0.0, l2=1e6))
    weak = fit_dc(small, ref, make_cfg(xi=0.0, l2=0.001))
    s_vals = list(strong["att"].values()) + list(strong["def"].values())
    assert max(abs(v) for v in s_vals) < 0.05
    w_att = np.std(list(weak["att"].values()))
    s_att = np.std(list(strong["att"].values()))
    assert w_att > s_att


# ------------------------------------------------------------- walk_forward


def _league_frame(seed=11, teams=None, league="L1", prefix="m"):
    rng = np.random.default_rng(seed)
    teams = teams or [f"T{i}" for i in range(8)]
    att = {t: rng.normal(0, 0.25) for t in teams}
    dfn = {t: rng.normal(0, 0.25) for t in teams}
    rows = []
    day = pd.Timestamp("2019-08-03")
    n = 0
    for s, season in enumerate(["1920", "2021", "2122"]):
        pairs = [(h, a) for h in teams for a in teams if h != a]
        order = rng.permutation(len(pairs))
        for idx in order:
            h, a = pairs[idx]
            lh = np.exp(0.1 + 0.25 + att[h] - dfn[a])
            la = np.exp(0.1 + att[a] - dfn[h])
            rows.append(
                {
                    "match_id": f"{prefix}{n:04d}", "league": league, "season": season,
                    "date": day, "home": h, "away": a,
                    "home_goals": int(rng.poisson(lh)), "away_goals": int(rng.poisson(la)),
                }
            )
            n += 1
            day = day + pd.Timedelta(days=7)
        day = day + pd.Timedelta(days=30)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def wf_data():
    return _league_frame()


@pytest.fixture(scope="module")
def wf_cfg():
    return make_cfg(refit_days=14)


@pytest.fixture(scope="module")
def wf_base(wf_data, wf_cfg):
    return walk_forward(wf_data, wf_cfg)


def _sorted(df):
    return df.sort_values("match_id").reset_index(drop=True)


def test_walk_forward_structure(wf_data, wf_base, wf_cfg):
    pred = wf_base
    later = wf_data[wf_data["season"] != "1920"]
    assert len(pred) == len(later)
    assert sorted(pred["match_id"]) == sorted(later["match_id"])
    assert pred["match_id"].is_unique
    assert not (pred["season"] == "1920").any()
    assert (pred["fit_ref_date"] <= pred["date"]).all()
    t0 = later["date"].min()
    step = wf_cfg["model"]["refit_days"]
    offs = (pred["fit_ref_date"] - t0).dt.days
    assert (offs % step == 0).all()
    assert ((pred["date"] - pred["fit_ref_date"]).dt.days < step).all()
    s = pred["p_home"] + pred["p_draw"] + pred["p_away"]
    np.testing.assert_allclose(s, 1.0, atol=1e-9)
    np.testing.assert_allclose(pred["p_over25"] + pred["p_under25"], 1.0, atol=1e-9)
    assert pred["fit_ok"].dtype == bool
    for c in ("lambda_home", "lambda_away", "rho", "home_adv", "p_btts", "truncated_mass",
              "n_train_matches", "flag_home_few_matches", "flag_away_few_matches"):
        assert c in pred.columns


def test_walk_forward_new_team_flagged(wf_data, wf_cfg):
    df = wf_data.copy()
    first_s2 = df[df["season"] == "2021"].index[0]
    df.loc[first_s2, "home"] = "NEWTEAM"
    pred = walk_forward(df, wf_cfg)
    mid = df.loc[first_s2, "match_id"]
    row = pred[pred["match_id"] == mid].iloc[0]
    assert bool(row["flag_home_few_matches"]) is True
    assert np.isfinite(row["lambda_home"])
    assert np.isfinite(row["p_home"])
    # regular teams have enough history at the start of season two
    assert bool(row["flag_away_few_matches"]) is False
    assert pred["fit_ok"].dtype == bool


def test_walk_forward_ah_columns(wf_data, wf_cfg):
    df = wf_data.copy()
    df["ah_line_pre"] = np.where(np.arange(len(df)) % 2 == 0, -0.25, np.nan)
    pred = walk_forward(df, wf_cfg).merge(df[["match_id", "ah_line_pre"]], on="match_id")
    has = pred["ah_line_pre"].notna()
    assert has.any() and (~has).any()
    assert (pred.loc[has, "ah_line"] == pred.loc[has, "ah_line_pre"]).all()
    assert pred.loc[~has, "ah_line"].isna().all()
    assert pred.loc[~has, "ah_fair_odds"].isna().all()
    assert pred.loc[has, "ah_fair_odds"].notna().all()
    probs = pred.loc[has, ["ah_full_win", "ah_half_win", "ah_push", "ah_half_loss", "ah_full_loss"]]
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, atol=1e-9)


def test_walk_forward_no_lookahead(wf_data, wf_cfg, wf_base):
    df2 = wf_data.copy()
    s3 = df2[df2["season"] == "2122"]
    pos = s3.index[len(s3) // 2]
    changed_date = df2.loc[pos, "date"]
    df2.loc[pos, "home_goals"] = df2.loc[pos, "home_goals"] + 3
    df2.loc[pos, "away_goals"] = 0
    pred2 = walk_forward(df2, wf_cfg)
    a, b = _sorted(wf_base), _sorted(pred2)
    assert list(a["match_id"]) == list(b["match_id"])
    early = a["fit_ref_date"] <= changed_date
    assert early.any()
    pd.testing.assert_frame_equal(
        a[early].reset_index(drop=True), b[early].reset_index(drop=True), check_exact=True
    )
    late = ~early
    assert late.any()
    diff = np.abs(a.loc[late, "lambda_home"].to_numpy() - b.loc[late, "lambda_home"].to_numpy())
    assert (diff > 0).any()


def test_walk_forward_training_season_change_affects_later(wf_data, wf_cfg, wf_base):
    df2 = wf_data.copy()
    pos = df2[df2["season"] == "1920"].index[3]
    df2.loc[pos, "home_goals"] = df2.loc[pos, "home_goals"] + 4
    pred2 = walk_forward(df2, wf_cfg)
    a, b = _sorted(wf_base), _sorted(pred2)
    assert (np.abs(a["lambda_home"].to_numpy() - b["lambda_home"].to_numpy()) > 0).any()


def test_walk_forward_multiple_leagues(wf_cfg):
    a = _league_frame(seed=1, league="L1", prefix="a")
    b = _league_frame(seed=2, league="L2", prefix="b")
    pred = walk_forward(pd.concat([a, b], ignore_index=True), wf_cfg)
    assert set(pred["league"]) == {"L1", "L2"}
    assert not (pred["season"] == "1920").any()
    assert len(pred) == 2 * 112
