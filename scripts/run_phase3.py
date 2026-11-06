"""Phase 3: forecast quality vs Pinnacle, bet simulation, calibration figures.
PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase3.py
Forecast quality and betting results are kept in separate sections and files.
"""
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from run_phase1a import md_table, write_text  # scripts/ is on sys.path
from fbmodel.betting import bet_stats, select_bets, settle_bets
from fbmodel.config import load_config
from fbmodel.evaluation import (brier_binary_rows, brier_rows, calibration_table,
                                expected_calibration_error, log_loss_rows, paired_bootstrap_diff,
                                rps_rows, season_blend_weights)
from fbmodel.io_guard import safe_write_path
from fbmodel.market import devig_proportional

RES_IDX = {"H": 0, "D": 1, "A": 2}
P1X2 = ["p_home", "p_draw", "p_away"]
MATCH_COLUMNS = [
    "match_id", "league", "season", "date", "result", "home_goals", "away_goals",
    "ah_line_pre", "ah_line_close",
    "ref_source_1x2_pre", "ref_source_1x2_close", "ref_source_ou25_pre", "ref_source_ou25_close",
    "ref_source_ah_close",
    "odds_1x2_pin_pre_h", "odds_1x2_pin_pre_d", "odds_1x2_pin_pre_a",
    "odds_1x2_pin_close_h", "odds_1x2_pin_close_d", "odds_1x2_pin_close_a",
    "odds_ou25_pin_pre_over", "odds_ou25_pin_pre_under",
    "odds_ou25_pin_close_over", "odds_ou25_pin_close_under",
    "odds_1x2_max_pre_h", "odds_1x2_max_pre_d", "odds_1x2_max_pre_a",
    "odds_ou25_max_pre_over", "odds_ou25_max_pre_under",
    "odds_ah_max_pre_home", "odds_ah_max_pre_away",
    "odds_ah_pin_close_home", "odds_ah_pin_close_away",
]
PRED_COLUMNS = ["match_id", "p_home", "p_draw", "p_away", "p_over25", "p_under25", "ah_line",
                "ah_full_win", "ah_half_win", "ah_push", "ah_half_loss", "ah_full_loss",
                "ah_fair_odds"]


def scopes(df, main, extra):
    """(name, mask) pairs: each league, pooled main, pooled extras, pooled all."""
    out = [(lg, df["league"] == lg) for lg in main + extra]
    out.append(("pooled_main", df["league"].isin(main)))
    out.append(("pooled_extra", df["league"].isin(extra)))
    out.append(("pooled_all", df["league"].isin(main + extra)))
    return out


def metric_rows(name_bench, market, scope, sub, pm, pb, y, ev, extra_cols=None):
    """Paired comparison rows (log loss, Brier, RPS for 1X2; log loss, Brier for O/U)."""
    rows = []
    if market == "1x2":
        funcs = {"log_loss": log_loss_rows, "brier": brier_rows, "rps": rps_rows}
        a_all = {k: f(pm, y) for k, f in funcs.items()}
        b_all = {k: f(pb, y) for k, f in funcs.items()}
    else:
        a_all = {"log_loss": log_loss_rows(np.column_stack([pm, 1 - pm]), 1 - y),
                 "brier": brier_binary_rows(pm, y)}
        b_all = {"log_loss": log_loss_rows(np.column_stack([pb, 1 - pb]), 1 - y),
                 "brier": brier_binary_rows(pb, y)}
    for k in a_all:
        r = paired_bootstrap_diff(a_all[k], b_all[k], ev["bootstrap_B"], ev["bootstrap_seed"],
                                  ev["ci_level"])
        rows.append([name_bench, market, scope, k, r["n"], a_all[k].mean(), b_all[k].mean(),
                     r["mean_diff"], r["ci_low"], r["ci_high"]])
    return rows


FQ_COLS = ["benchmark", "market", "scope", "metric", "n", "model", "benchmark_value",
           "diff_model_minus_bench", "ci_low", "ci_high"]


def main():
    cfg = load_config()
    ev, paths = cfg["evaluation"], cfg["paths"]
    rep = paths["reports"] / "phase3"
    rep.mkdir(parents=True, exist_ok=True)
    main_l = list(cfg["data_source"]["main_leagues"])
    extra_l = list(cfg["data_source"]["extra_leagues"])
    m = pd.read_parquet(paths["processed"] / "matches.parquet", columns=MATCH_COLUMNS)
    pr = pd.read_parquet(paths["processed"] / "predictions.parquet", columns=PRED_COLUMNS)
    d = m.merge(pr, on="match_id", how="inner")
    d["y"] = d["result"].map(RES_IDX)
    d["over"] = ((d["home_goals"] + d["away_goals"]) > cfg["model"]["ou_line"]).astype(float)
    n_pred = len(d)

    # ======================================================= PART 1: forecast quality
    fq = []
    for bench, timing in (("pin_close", "close"), ("pin_pre", "pre")):
        for market in ("1x2", "ou25"):
            ref = d[f"ref_source_{market}_{timing}"] == "pin"
            if market == "1x2":
                cols = [f"odds_1x2_pin_{timing}_{s}" for s in "hda"]
            else:
                cols = [f"odds_ou25_pin_{timing}_over", f"odds_ou25_pin_{timing}_under"]
            sel = d[ref].copy()
            if sel.empty:
                continue
            fair = devig_proportional(sel[cols].to_numpy(float))
            sel["_b"] = list(fair)
            for scope, mask in scopes(sel, main_l, extra_l):
                if bench == "pin_pre" and scope in extra_l + ["pooled_extra", "pooled_all"]:
                    continue
                if market == "ou25" and scope in extra_l + ["pooled_extra", "pooled_all"]:
                    continue
                s = sel[mask]
                if s.empty:
                    continue
                B = np.vstack(s["_b"].to_numpy())
                if market == "1x2":
                    fq += metric_rows(bench, market, scope, s, s[P1X2].to_numpy(float), B,
                                      s["y"].to_numpy(int), ev)
                else:
                    fq += metric_rows(bench, market, scope, s, s["p_over25"].to_numpy(float),
                                      B[:, 0], s["over"].to_numpy(float), ev)
    fq = pd.DataFrame(fq, columns=FQ_COLS)
    fq.to_csv(safe_write_path(rep / "forecast_quality.csv"), index=False)

    # ---- calibration of p_home: model vs Pinnacle closing
    cal_rows, ece_rows = [], []
    sel = d[d["ref_source_1x2_close"] == "pin"].copy()
    fair = devig_proportional(sel[[f"odds_1x2_pin_close_{s}" for s in "hda"]].to_numpy(float))
    sel["pin_home"] = fair[:, 0]
    sel["home_win"] = (sel["y"] == 0).astype(float)
    panels = [("Main leagues (pooled)", sel["league"].isin(main_l)), ("USA", sel["league"] == "USA")]
    nb = ev["calibration_bins"]
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.6), sharex=True, sharey=True)
    style = {"model": ("#1f5fa8", "o", "-"), "Pinnacle closing": ("#c4531a", "s", "--")}
    for ax, (title, mask) in zip(axes, panels):
        s = sel[mask]
        ax.plot([0, 1], [0, 1], color="#999999", lw=1, zorder=1)
        for name, col in (("model", "p_home"), ("Pinnacle closing", "pin_home")):
            t = calibration_table(s[col].to_numpy(), s["home_win"].to_numpy(), nb)
            e = expected_calibration_error(s[col].to_numpy(), s["home_win"].to_numpy(), nb)
            color, mk, ls = style[name]
            ax.plot(t["mean_p"], t["mean_o"], color=color, marker=mk, ls=ls, lw=2, ms=6,
                    label=f"{name} (ECE {e:.3f})", zorder=3)
            for _, r in t.iterrows():
                cal_rows.append([title, name, int(r["bin"]), int(r["n"]), r["mean_p"], r["mean_o"]])
            ece_rows.append([title, name, len(s), e])
        ax.set_title(f"{title}, n={len(s)}", fontsize=11)
        ax.set_xlabel("predicted P(home win)")
        ax.grid(color="#e5e5e5", lw=0.6)
        ax.legend(loc="upper left", fontsize=9, frameon=False)
    axes[0].set_ylabel("observed frequency of home win")
    fig.suptitle("Reliability of home-win probability (10 equal-width bins)", fontsize=12)
    fig.tight_layout()
    fig.savefig(safe_write_path(rep / "calibration_p_home.png"), dpi=130)
    plt.close(fig)
    pd.DataFrame(cal_rows, columns=["scope", "forecast", "bin", "n", "mean_p", "mean_o"]).to_csv(
        safe_write_path(rep / "calibration_p_home.csv"), index=False)
    ece = pd.DataFrame(ece_rows, columns=["scope", "forecast", "n", "ece"])
    ece.to_csv(safe_write_path(rep / "calibration_ece.csv"), index=False)

    # ---- blend (main leagues): weights from earlier evaluated seasons only
    bl = d[d["league"].isin(main_l) & (d["ref_source_1x2_pre"] == "pin")].copy()
    pin_pre = devig_proportional(bl[[f"odds_1x2_pin_pre_{s}" for s in "hda"]].to_numpy(float))
    bd = pd.DataFrame({"league": bl["league"], "season": bl["season"], "date": bl["date"],
                       "y": bl["y"], "m_h": bl["p_home"], "m_d": bl["p_draw"], "m_a": bl["p_away"],
                       "b_h": pin_pre[:, 0], "b_d": pin_pre[:, 1], "b_a": pin_pre[:, 2]},
                      index=bl.index)
    grid = np.linspace(0.0, 1.0, ev["blend_grid_points"])
    wt = season_blend_weights(bd, grid)
    wt.to_csv(safe_write_path(rep / "blend_weights.csv"), index=False)
    bd = bd.merge(wt, on=["league", "season"], how="left").set_index(bl.index)
    has_w = bd["w"].notna()
    M = bd[["m_h", "m_d", "m_a"]].to_numpy()
    Bm = bd[["b_h", "b_d", "b_a"]].to_numpy()
    BL = bd["w"].to_numpy()[:, None] * M + (1 - bd["w"].to_numpy()[:, None]) * Bm
    BL = BL / BL.sum(axis=1, keepdims=True)
    d["bl_home"] = np.nan
    d["bl_draw"] = np.nan
    d["bl_away"] = np.nan
    d.loc[bl.index[has_w.to_numpy()], ["bl_home", "bl_draw", "bl_away"]] = BL[has_w.to_numpy()]
    blr = []
    sub = bd[has_w]
    for scope, mask in scopes(sub, main_l, []):
        if scope in ("pooled_extra", "pooled_all"):
            continue
        s = sub[mask]
        if s.empty:
            continue
        y = s["y"].to_numpy(int)
        pbl = BL[has_w.to_numpy()][mask.to_numpy()]
        for cmp_name, other in (("blend_vs_pin_pre", s[["b_h", "b_d", "b_a"]].to_numpy()),
                                ("blend_vs_model", s[["m_h", "m_d", "m_a"]].to_numpy())):
            blr += metric_rows(cmp_name, "1x2", scope, s, pbl, other, y, ev)
    blr = pd.DataFrame(blr, columns=FQ_COLS)
    blr.to_csv(safe_write_path(rep / "blend_quality.csv"), index=False)

    # ======================================================= PART 2: bet simulation
    mm = m[m["league"].isin(main_l)]
    dd = d[d["league"].isin(main_l)]
    preds_cols = PRED_COLUMNS + ["bl_home", "bl_draw", "bl_away"]
    pp = dd[preds_cols]
    all_bets, skip_rows, stat_rows = [], [], []
    for signal in ("model", "blend"):
        for thr in ev["bet_thresholds"]:
            bets, skipped = select_bets(mm, pp, cfg, signal, thr)
            skipped["signal"], skipped["threshold"] = signal, thr
            skip_rows.append(skipped)
            sb = settle_bets(bets, mm)
            all_bets.append(sb)
            for market in ("1x2", "ou25", "ah"):
                sm = sb[sb["market"] == market]
                if signal == "blend" and market != "1x2":
                    continue
                for scope in main_l + ["pooled_main"]:
                    s = sm if scope == "pooled_main" else sm[sm["league"] == scope]
                    st = bet_stats(s, ev["bootstrap_B"], ev["bootstrap_seed"], ev["ci_level"])
                    stat_rows.append({"threshold": thr, "market": market, "signal": signal,
                                      "scope": scope, **st})
    stats = pd.DataFrame(stat_rows)
    stats.to_csv(safe_write_path(rep / "bet_summary.csv"), index=False)
    skips = pd.concat(skip_rows, ignore_index=True)
    skips.to_csv(safe_write_path(rep / "bet_skipped.csv"), index=False)
    bets_all = pd.concat(all_bets, ignore_index=True)
    bets_all.to_parquet(safe_write_path(paths["processed"] / "bets.parquet"), index=False)

    # reference: CLV of an UNINFORMED 1X2 bet (every outcome at Max pre odds)
    base = dd[(dd["ref_source_1x2_close"] == "pin")]
    mx = base[["odds_1x2_max_pre_h", "odds_1x2_max_pre_d", "odds_1x2_max_pre_a"]].to_numpy(float)
    cl = base[["odds_1x2_pin_close_h", "odds_1x2_pin_close_d", "odds_1x2_pin_close_a"]].to_numpy(float)
    okb = ~(np.isnan(mx).any(axis=1) | np.isnan(cl).any(axis=1))
    base_clv = mx[okb] * devig_proportional(cl[okb]) - 1.0
    base_tab = pd.DataFrame({"reference": ["every 1X2 outcome at Max pre odds"],
                             "n_outcomes": [base_clv.size], "mean_clv": [base_clv.mean()],
                             "share_beating_close": [(base_clv > 0).mean()]})
    base_tab.to_csv(safe_write_path(rep / "bet_clv_reference.csv"), index=False)

    # ======================================================= reports
    chk = ev
    seasons = (d[d["league"].isin(main_l)].groupby("league")["season"].agg(lambda s: ",".join(sorted(set(s)))))
    fq_md = ["# Phase 3 - Forecast quality (no betting here)\n",
             f"Model: walk-forward Dixon-Coles (Phase 2), {n_pred} predictions joined to matches. "
             "Benchmarks: Pinnacle proportional-devigged fair probabilities, closing where "
             "ref_source_<market>_close == pin, pre where ref_source_<market>_pre == pin. Model and "
             "benchmark are always scored on the SAME matches. diff = model minus benchmark (negative "
             "= model better for all three losses). CI: paired bootstrap over matches, "
             f"B={chk['bootstrap_B']}, seed {chk['bootstrap_seed']}, level {chk['ci_level']}. "
             "USA, DNK and SWE have a closing benchmark only (declared limit: no pre-match odds in "
             "the source); O/U 2.5 is evaluated for the main leagues only.\n",
             "## 1X2 against Pinnacle closing\n",
             md_table(fq[(fq.benchmark == "pin_close") & (fq.market == "1x2")].drop(columns=["benchmark", "market"]), "{:.4f}"),
             "## 1X2 against Pinnacle pre-match (main leagues)\n",
             md_table(fq[(fq.benchmark == "pin_pre") & (fq.market == "1x2")].drop(columns=["benchmark", "market"]), "{:.4f}"),
             "## O/U 2.5 against Pinnacle closing (main leagues)\n",
             md_table(fq[(fq.benchmark == "pin_close") & (fq.market == "ou25")].drop(columns=["benchmark", "market"]), "{:.4f}"),
             "## O/U 2.5 against Pinnacle pre-match (main leagues)\n",
             md_table(fq[(fq.benchmark == "pin_pre") & (fq.market == "ou25")].drop(columns=["benchmark", "market"]), "{:.4f}"),
             "## Calibration of p_home\n![calibration](calibration_p_home.png)\n\n"
             "Equal-width bins; the outermost bins hold few matches (counts in "
             "calibration_p_home.csv) and are noisy. ECE = sum over bins of (n_b / N) * |observed - "
             "predicted|.\n\n", md_table(ece, "{:.4f}"),
             "## Blend with Pinnacle pre (main leagues)\n"
             "p_blend = w * model + (1 - w) * Pinnacle pre fair, w per league and season chosen on "
             "1X2 log loss over all EARLIER evaluated seasons of that league only (the first "
             "evaluated season has no blend). Weights:\n", md_table(wt, "{:.2f}"),
             "Scores of the blend on the same matches (diff = blend minus comparator):\n",
             md_table(blr.drop(columns=["market"]), "{:.4f}")]
    write_text(rep / "forecast_quality.md", "\n".join(fq_md))

    bet_md = ["# Phase 3 - Bet simulation (main leagues, pre-match information only)\n",
              "Separate from forecast quality. Decision inputs: model (or blend) probabilities and Max "
              "PRE odds only; Pinnacle closing is used after the decision, for CLV. Edge = p * Max "
              "pre odds - 1 (AH: expected profit from the five outcome probabilities). One bet per "
              "match and market (largest edge), flat stake 1, outcomes with Max pre odds above "
              f"{chk['max_bet_odds']} excluded (AH also when the model fair odds exceed it). Only "
              "matches with ref_source_<market>_close == pin. Thresholds "
              f"{chk['bet_thresholds']} fixed in advance; ALL are reported, none is selected. "
              "Blend bets exist for 1X2 only. CLV = odds taken / Pinnacle closing fair odds - 1; "
              "for AH it is defined only when the closing line equals ah_line_pre (n_clv).\n",
              "**Caveats.** Max odds are the best price across many bookmakers and may not be "
              "obtainable at size. Several thresholds, markets and signals are tested, so a single "
              "positive cell is not evidence. The sample is conditioned on Pinnacle closing odds "
              "being available (an availability gate, not an outcome-based one). The ROI CI is a "
              "bootstrap over bets and ignores correlation between bets.\n"]
    show = ["threshold", "market", "signal", "scope", "n_bets", "roi", "roi_ci_low", "roi_ci_high",
            "mean_clv", "clv_ci_low", "clv_ci_high", "n_clv", "share_beating_close",
            "longest_losing_streak", "max_drawdown"]
    pooled = stats[stats.scope == "pooled_main"][show].sort_values(["market", "signal", "threshold"])
    bet_md += ["## Pooled main leagues, all thresholds\n", md_table(pooled, "{:.4f}"),
               "## Per league, all thresholds\n",
               md_table(stats[stats.scope != "pooled_main"][show].sort_values(
                   ["market", "signal", "threshold", "scope"]), "{:.4f}"),
               "## Reference: CLV of an uninformed bet\n"
               "Max pre odds are the best of many books, so even a bet with no information has a CLV "
               "against the Pinnacle closing fair price; compare the CLV above with this.\n",
               md_table(base_tab, "{:.4f}"),
               "## Skipped match-markets (NaN inputs)\n", md_table(skips.groupby(
                   ["market", "signal", "threshold"], as_index=False)["n"].sum())]
    write_text(rep / "bet_simulation.md", "\n".join(bet_md))
    print(fq[(fq.scope.isin(["pooled_main", "pooled_all"])) & (fq.metric == "log_loss")].to_string())
    print(pooled.to_string())


if __name__ == "__main__":
    main()
