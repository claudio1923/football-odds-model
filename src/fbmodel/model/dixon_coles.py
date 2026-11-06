"""Dixon-Coles goal model with time decay and L2 shrinkage; one model per league.

Inputs: date, league, home, away and full-time goals of PAST matches only. No odds.
"""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from fbmodel.market import half_lines

_PARAM_HEAD = 3  # mu, home_adv, rho


def tau(x, y, lam, mu, rho):
    """Dixon-Coles correction for scores 0-0, 1-0, 0-1, 1-1 (lam home, mu away goals)."""
    x, y, lam, mu, rho = np.broadcast_arrays(*(np.asarray(v) for v in (x, y, lam, mu, rho)))
    t = np.ones(x.shape, dtype=float)
    t = np.where((x == 0) & (y == 0), 1.0 - lam * mu * rho, t)
    t = np.where((x == 0) & (y == 1), 1.0 + lam * rho, t)
    t = np.where((x == 1) & (y == 0), 1.0 + mu * rho, t)
    t = np.where((x == 1) & (y == 1), 1.0 - rho, t)
    return t


def score_matrix(lam_h, lam_a, rho, max_goals):
    """P(home=x, away=y) for x,y in 0..max_goals, NOT renormalised (sum = 1 - truncated mass)."""
    g = np.arange(max_goals + 1)
    base = np.outer(poisson.pmf(g, lam_h), poisson.pmf(g, lam_a))
    xx, yy = np.meshgrid(g, g, indexing="ij")
    return base * tau(xx, yy, lam_h, lam_a, rho)


def markets_from_matrix(M, ah_line=None, ou_line=2.5):
    """Market probabilities from a (renormalised) score matrix; AH probabilities are for the
    HOME side at ah_line (home handicap, negative = home favourite)."""
    M = np.asarray(M, dtype=float)
    M = M / M.sum()
    g = np.arange(M.shape[0])
    xx, yy = np.meshgrid(g, g, indexing="ij")
    diff, total = xx - yy, xx + yy
    out = {
        "p_home": M[diff > 0].sum(), "p_draw": M[diff == 0].sum(), "p_away": M[diff < 0].sum(),
        "p_over": M[total > ou_line].sum(), "p_under": M[total < ou_line].sum(),
        "p_btts": M[(xx > 0) & (yy > 0)].sum(),
    }
    if ah_line is not None:
        l1, l2 = half_lines(ah_line)
        s = (np.sign(diff + l1) + np.sign(diff + l2)) / 2.0
        fw, hw, pu = M[s == 1.0].sum(), M[s == 0.5].sum(), M[s == 0.0].sum()
        hl, fl = M[s == -0.5].sum(), M[s == -1.0].sum()
        win_units, loss_units = fw + 0.5 * hw, 0.5 * hl + fl
        out.update({
            "ah_line": float(ah_line), "ah_full_win": fw, "ah_half_win": hw, "ah_push": pu,
            "ah_half_loss": hl, "ah_full_loss": fl,
            "ah_fair_odds": 1.0 + loss_units / win_units if win_units > 0 else np.inf,
        })
    return out


def _neg_loglik(theta, h, a, x, y, w, n_teams, l2, rho_floor_tau):
    mu, ha, rho = theta[0], theta[1], theta[2]
    att = theta[_PARAM_HEAD:_PARAM_HEAD + n_teams]
    dfn = theta[_PARAM_HEAD + n_teams:]
    eta_h = mu + ha + att[h] - dfn[a]
    eta_a = mu + att[a] - dfn[h]
    lh, la = np.exp(eta_h), np.exp(eta_a)
    m00, m01 = (x == 0) & (y == 0), (x == 0) & (y == 1)
    m10, m11 = (x == 1) & (y == 0), (x == 1) & (y == 1)
    t = np.ones_like(lh)
    t = np.where(m00, 1.0 - lh * la * rho, t)
    t = np.where(m01, 1.0 + lh * rho, t)
    t = np.where(m10, 1.0 + la * rho, t)
    t = np.where(m11, 1.0 - rho, t)
    ok = t > rho_floor_tau
    tc = np.where(ok, t, rho_floor_tau)
    ll = w * (np.log(tc) + x * eta_h - lh + y * eta_a - la)
    inv = np.where(ok, 1.0 / tc, 0.0)
    d_lh = np.where(m00, -la * rho, np.where(m01, rho, 0.0)) * inv
    d_la = np.where(m00, -lh * rho, np.where(m10, rho, 0.0)) * inv
    d_rho = np.where(m00, -lh * la, np.where(m01, lh, np.where(m10, la, np.where(m11, -1.0, 0.0)))) * inv
    g_h = w * (x - lh + lh * d_lh)
    g_a = w * (y - la + la * d_la)
    g_att = np.bincount(h, g_h, n_teams) + np.bincount(a, g_a, n_teams)
    g_def = -np.bincount(a, g_h, n_teams) - np.bincount(h, g_a, n_teams)
    grad = np.concatenate([[g_h.sum() + g_a.sum(), g_h.sum(), (w * d_rho).sum()], g_att, g_def])
    f = -ll.sum() + l2 * (np.sum(att ** 2) + np.sum(dfn ** 2))
    pen = np.concatenate([np.zeros(_PARAM_HEAD), 2 * l2 * att, 2 * l2 * dfn])
    return f, -grad + pen


def fit_dc(matches, ref_date, cfg, init=None):
    """Weighted maximum-likelihood fit on matches strictly before ref_date.

    matches: one league, columns date, home, away, home_goals, away_goals. Raises
    AssertionError if any match is not strictly before ref_date. init: an earlier fit
    (warm start, matched by team name).
    """
    m = cfg["model"]
    ref_date = pd.Timestamp(ref_date)
    if not (pd.to_datetime(matches["date"]) < ref_date).all():
        raise AssertionError("fit_dc received a match on or after ref_date")
    teams = sorted(set(matches["home"]) | set(matches["away"]))
    pos = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    h = matches["home"].map(pos).to_numpy()
    a = matches["away"].map(pos).to_numpy()
    x = matches["home_goals"].to_numpy(dtype=float)
    y = matches["away_goals"].to_numpy(dtype=float)
    days = (ref_date - pd.to_datetime(matches["date"])).dt.days.to_numpy(dtype=float)
    w = np.exp(-m["xi"] * days)
    theta0 = np.zeros(_PARAM_HEAD + 2 * n)
    if init is not None:
        theta0[0], theta0[1], theta0[2] = init["mu"], init["home_adv"], init["rho"]
        for t, i in pos.items():
            theta0[_PARAM_HEAD + i] = init["att"].get(t, 0.0)
            theta0[_PARAM_HEAD + n + i] = init["def"].get(t, 0.0)
    else:
        theta0[0] = np.log(max(np.mean(np.concatenate([x, y])), 1e-3))
    lo, hi = m["rho_bounds"]
    bounds = [(None, None), (None, None), (lo, hi)] + [(None, None)] * (2 * n)
    theta0[2] = min(max(theta0[2], lo), hi)
    res = minimize(_neg_loglik, theta0, args=(h, a, x, y, w, n, m["l2_penalty"], m["tau_floor"]),
                   jac=True, method="L-BFGS-B", bounds=bounds, options={"maxiter": m["maxiter"]})
    th = res.x
    return {
        "teams": teams, "mu": float(th[0]), "home_adv": float(th[1]), "rho": float(th[2]),
        "att": {t: float(th[_PARAM_HEAD + i]) for t, i in pos.items()},
        "def": {t: float(th[_PARAM_HEAD + n + i]) for t, i in pos.items()},
        "success": bool(res.success and np.all(np.isfinite(th))), "n_matches": int(len(matches)),
        "nit": int(res.nit), "fun": float(res.fun), "message": str(res.message),
    }


def walk_forward(matches, cfg):
    """Predictions for every match after the first season of each league.

    Refit on a grid of refit_days starting at the first date of the first predicted
    season; each block is predicted from a fit on matches strictly before the block start.
    """
    m = cfg["model"]
    rows = []
    for league, g in matches.groupby("league", sort=True):
        g = g.sort_values(["date", "match_id"], kind="mergesort").reset_index(drop=True)
        first_season = g.groupby("season")["date"].min().idxmin()
        pred = g[g["season"] != first_season]
        if pred.empty:
            continue
        t0 = pred["date"].min()
        block = ((pred["date"] - t0).dt.days // m["refit_days"]).to_numpy()
        init = None
        for b in np.unique(block):
            pb = pred[block == b]
            ref = t0 + pd.Timedelta(days=int(b) * m["refit_days"])
            train = g[g["date"] < ref]
            fit = fit_dc(train, ref, cfg, init=init)
            if np.isfinite([fit["mu"], fit["home_adv"], fit["rho"]]).all():
                init = fit
            played = pd.concat([train["home"], train["away"]]).value_counts()
            for r in pb.itertuples(index=False):
                lam_h = np.exp(fit["mu"] + fit["home_adv"] + fit["att"].get(r.home, 0.0)
                               - fit["def"].get(r.away, 0.0))
                lam_a = np.exp(fit["mu"] + fit["att"].get(r.away, 0.0) - fit["def"].get(r.home, 0.0))
                M = score_matrix(lam_h, lam_a, fit["rho"], m["max_goals"])
                line = getattr(r, "ah_line_pre", np.nan)
                has_line = line is not None and not pd.isna(line)
                mk = markets_from_matrix(M, ah_line=line if has_line else None, ou_line=m["ou_line"])
                rows.append({
                    "match_id": r.match_id, "league": league, "season": r.season, "date": r.date,
                    "stage": getattr(r, "stage", None),
                    "fit_ref_date": ref, "lambda_home": lam_h, "lambda_away": lam_a,
                    "rho": fit["rho"], "home_adv": fit["home_adv"],
                    "p_home": mk["p_home"], "p_draw": mk["p_draw"], "p_away": mk["p_away"],
                    "p_over25": mk["p_over"], "p_under25": mk["p_under"], "p_btts": mk["p_btts"],
                    "truncated_mass": 1.0 - M.sum(),
                    "ah_line": float(line) if has_line else np.nan,
                    "ah_full_win": mk.get("ah_full_win", np.nan), "ah_half_win": mk.get("ah_half_win", np.nan),
                    "ah_push": mk.get("ah_push", np.nan), "ah_half_loss": mk.get("ah_half_loss", np.nan),
                    "ah_full_loss": mk.get("ah_full_loss", np.nan),
                    "ah_fair_odds": mk.get("ah_fair_odds", np.nan),
                    "n_train_matches": len(train),
                    "flag_home_few_matches": bool(played.get(r.home, 0) < m["min_team_matches"]),
                    "flag_away_few_matches": bool(played.get(r.away, 0) < m["min_team_matches"]),
                    "fit_ok": bool(fit["success"]),
                })
    return pd.DataFrame(rows)
