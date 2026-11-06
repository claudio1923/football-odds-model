"""Bet selection and settlement from pre-match information; CLV against Pinnacle closing.

The bet decision uses only model/blend probabilities and Max PRE odds. Closing columns are
read only in settle_bets (CLV), after the decision.
"""
import numpy as np
import pandas as pd

from fbmodel.evaluation import bootstrap_mean_ci
from fbmodel.market import devig_proportional, settle_ah, settle_ou

OU_LINE = 2.5  # the "ou25" market is the 2.5 line by definition
BET_COLUMNS = ["match_id", "league", "season", "date", "market", "signal", "outcome", "odds",
               "p", "edge", "threshold"]
MAX_PRE = {
    "1x2": ["odds_1x2_max_pre_h", "odds_1x2_max_pre_d", "odds_1x2_max_pre_a"],
    "ou25": ["odds_ou25_max_pre_over", "odds_ou25_max_pre_under"],
    "ah": ["odds_ah_max_pre_home", "odds_ah_max_pre_away"],
}
PIN_CLOSE = {
    "1x2": ["odds_1x2_pin_close_h", "odds_1x2_pin_close_d", "odds_1x2_pin_close_a"],
    "ou25": ["odds_ou25_pin_close_over", "odds_ou25_pin_close_under"],
    "ah": ["odds_ah_pin_close_home", "odds_ah_pin_close_away"],
}
OUTCOMES = {"1x2": ["H", "D", "A"], "ou25": ["over", "under"], "ah": ["home", "away"]}
_SETTLE_COLUMNS = (["result", "home_goals", "away_goals", "ah_line_pre", "ah_line_close"]
                   + sorted({c for v in PIN_CLOSE.values() for c in v}))


# ------------------------------------------------------------------ statistics
def closing_fair_odds(close_odds, idx):
    fair = devig_proportional(np.asarray(close_odds, dtype=float))
    return 1.0 / fair[np.arange(len(fair)), np.asarray(idx, dtype=int)]


def clv(odds_taken, fair_close_odds):
    return np.asarray(odds_taken, dtype=float) / np.asarray(fair_close_odds, dtype=float) - 1.0


def longest_losing_streak(profits):
    best = run = 0
    for v in np.asarray(profits, dtype=float):
        run = run + 1 if v < 0 else 0
        best = max(best, run)
    return int(best)


def max_drawdown(profits):
    cum = np.concatenate([[0.0], np.cumsum(np.asarray(profits, dtype=float))])
    return float((np.maximum.accumulate(cum) - cum).max())


def bet_stats(bets, n_boot, seed, ci_level):
    b = bets.sort_values(["date", "match_id"], kind="mergesort")
    n = len(b)
    out = {k: np.nan for k in ("roi", "roi_ci_low", "roi_ci_high", "mean_clv", "clv_ci_low",
                               "clv_ci_high", "share_beating_close")}
    out.update({"n_bets": n, "n_clv": 0, "longest_losing_streak": 0, "max_drawdown": 0.0})
    if n == 0:
        return out
    profit = b["profit"].to_numpy(dtype=float)
    r = bootstrap_mean_ci(profit, n_boot, seed, ci_level)
    out.update({"roi": r["mean"], "roi_ci_low": r["ci_low"], "roi_ci_high": r["ci_high"],
                "longest_losing_streak": longest_losing_streak(profit),
                "max_drawdown": max_drawdown(profit)})
    c = b["clv"].to_numpy(dtype=float)
    c = c[~np.isnan(c)]
    out["n_clv"] = int(len(c))
    if len(c):
        rc = bootstrap_mean_ci(c, n_boot, seed, ci_level)
        out.update({"mean_clv": rc["mean"], "clv_ci_low": rc["ci_low"], "clv_ci_high": rc["ci_high"],
                    "share_beating_close": float((c > 0).mean())})
    return out


# ------------------------------------------------------------------ selection
def select_bets(matches, preds, cfg, signal, threshold):
    """Return (bets, skipped). One bet per match and market: the outcome with the largest edge,
    if edge >= threshold. Flat stake 1. Decision inputs: probabilities and Max PRE odds only."""
    max_odds = cfg["evaluation"]["max_bet_odds"]
    d = matches.merge(preds, on="match_id", how="inner", suffixes=("", "_pred"))
    recs, skips = [], []

    def finish(sub, market, edges, odds, probs, fair=None):
        edges = edges.copy()
        edges[odds > max_odds] = -np.inf
        if fair is not None:
            edges[fair > max_odds] = -np.inf
        best = edges.argmax(axis=1)
        be = edges[np.arange(len(sub)), best]
        take = np.isfinite(be) & (be >= threshold)
        names = OUTCOMES[market]
        for i in np.flatnonzero(take):
            r = sub.iloc[i]
            recs.append([r["match_id"], r["league"], r["season"], r["date"], market, signal,
                         names[best[i]], odds[i, best[i]],
                         probs[i, best[i]] if probs is not None else np.nan, be[i], threshold])

    def eligible(market, need):
        elig = d[d["ref_source_" + market + "_close"] == "pin"]
        ok = elig[need].notna().all(axis=1)
        if (~ok).any():
            skips.append([market, "nan_odds_line_or_probs", int((~ok).sum())])
        return elig[ok]

    # ---- 1X2
    pc = ["p_home", "p_draw", "p_away"] if signal == "model" else ["bl_home", "bl_draw", "bl_away"]
    sub = eligible("1x2", MAX_PRE["1x2"] + pc)
    if len(sub):
        P, O = sub[pc].to_numpy(float), sub[MAX_PRE["1x2"]].to_numpy(float)
        finish(sub, "1x2", P * O - 1.0, O, P)

    if signal == "model":
        # ---- O/U 2.5
        pc = ["p_over25", "p_under25"]
        sub = eligible("ou25", MAX_PRE["ou25"] + pc)
        if len(sub):
            P, O = sub[pc].to_numpy(float), sub[MAX_PRE["ou25"]].to_numpy(float)
            finish(sub, "ou25", P * O - 1.0, O, P)

        # ---- AH at ah_line_pre: edge = expected profit from the five outcome probabilities
        need = MAX_PRE["ah"] + ["ah_line_pre", "ah_full_win", "ah_half_win", "ah_push",
                                "ah_half_loss", "ah_full_loss"]
        sub = eligible("ah", need)
        if len(sub):
            O = sub[MAX_PRE["ah"]].to_numpy(float)
            fw, hw = sub["ah_full_win"].to_numpy(float), sub["ah_half_win"].to_numpy(float)
            hl, fl = sub["ah_half_loss"].to_numpy(float), sub["ah_full_loss"].to_numpy(float)
            e_home = (fw + 0.5 * hw) * (O[:, 0] - 1) - 0.5 * hl - fl
            e_away = (fl + 0.5 * hl) * (O[:, 1] - 1) - 0.5 * hw - fw
            with np.errstate(divide="ignore", invalid="ignore"):
                wu_h, lu_h = fw + 0.5 * hw, 0.5 * hl + fl
                wu_a, lu_a = fl + 0.5 * hl, 0.5 * hw + fw
                f_home = np.where(wu_h > 0, 1.0 + lu_h / wu_h, np.inf)
                f_away = np.where(wu_a > 0, 1.0 + lu_a / wu_a, np.inf)
            finish(sub, "ah", np.column_stack([e_home, e_away]), O, None,
                   fair=np.column_stack([f_home, f_away]))
    bets = pd.DataFrame(recs, columns=BET_COLUMNS)
    skipped = pd.DataFrame(skips, columns=["market", "reason", "n"])
    return bets, skipped


# ------------------------------------------------------------------ settlement
def settle_bets(bets, matches):
    """Add profit, fair_close_odds and clv. Closing data is used here only."""
    d = bets.merge(matches[["match_id"] + _SETTLE_COLUMNS], on="match_id", how="left")
    d["profit"] = np.nan
    d["fair_close_odds"] = np.nan
    for market, g in d.groupby("market"):
        i = g.index
        odds = g["odds"].to_numpy(float)
        names = OUTCOMES[market]
        idx = g["outcome"].map({n: k for k, n in enumerate(names)}).to_numpy(int)
        if market == "1x2":
            won = (g["result"] == g["outcome"]).to_numpy()
            d.loc[i, "profit"] = np.where(won, odds - 1.0, -1.0)
        elif market == "ou25":
            tot = (g["home_goals"] + g["away_goals"]).to_numpy(float)
            for side in ("over", "under"):
                m = (g["outcome"] == side).to_numpy()
                d.loc[i[m], "profit"] = settle_ou(tot[m], OU_LINE, odds[m], side)
        else:
            hg, ag = g["home_goals"].to_numpy(float), g["away_goals"].to_numpy(float)
            line = g["ah_line_pre"].to_numpy(float)
            for side in ("home", "away"):
                m = (g["outcome"] == side).to_numpy()
                d.loc[i[m], "profit"] = settle_ah(hg[m], ag[m], line[m], odds[m], side)
        close = g[PIN_CLOSE[market]].to_numpy(float)
        valid = ~np.isnan(close).any(axis=1)
        if market == "ah":
            valid &= g["ah_line_close"].to_numpy(float) == g["ah_line_pre"].to_numpy(float)
        fair = np.full(len(g), np.nan)
        if valid.any():
            fair[valid] = closing_fair_odds(close[valid], idx[valid])
        d.loc[i, "fair_close_odds"] = fair
    d["clv"] = clv(d["odds"], d["fair_close_odds"])
    return d.drop(columns=_SETTLE_COLUMNS)
