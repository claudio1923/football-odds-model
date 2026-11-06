"""Build README.md from the result files (numbers only from executed code).
PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/build_readme.py
"""
import pandas as pd
import yaml

from fbmodel.config import PROJECT_ROOT, load_config
from fbmodel.io_guard import safe_write_path


def table(df, fmt="{:.4f}"):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.astype(object).iterrows():
        out.append("| " + " | ".join(
            "" if v is None or (isinstance(v, float) and pd.isna(v)) else
            (fmt.format(v) if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(out)


def ci(lo, hi):
    return f"[{lo:.4f}, {hi:.4f}]"


def main():
    cfg = load_config()
    paths, ev = cfg["paths"], cfg["evaluation"]
    rep = paths["reports"] / "phase3"
    m = pd.read_parquet(paths["processed"] / "matches.parquet",
                        columns=["league", "season", "date", "stage"])
    pr = pd.read_parquet(paths["processed"] / "predictions.parquet", columns=["league", "match_id"])
    fq = pd.read_csv(rep / "forecast_quality.csv")
    bs = pd.read_csv(rep / "bet_summary.csv")
    wt = pd.read_csv(rep / "blend_weights.csv")
    ece = pd.read_csv(rep / "calibration_ece.csv")
    ref = yaml.safe_load(open(PROJECT_ROOT / cfg["cleaning"]["paths"]["reference_price"], encoding="utf-8"))
    base = pd.read_csv(rep / "bet_clv_reference.csv")
    main_l = list(cfg["data_source"]["main_leagues"])
    extra_l = list(cfg["data_source"]["extra_leagues"])
    n_all, n_pred = len(m), len(pr)
    d0, d1 = m["date"].min().date(), m["date"].max().date()

    # ---- forecast table (1X2)
    rows = []
    for bench, scope in (("pin_close", "pooled_main"), ("pin_pre", "pooled_main"),
                         ("pin_close", "USA"), ("pin_close", "DNK"), ("pin_close", "SWE")):
        s = fq[(fq.benchmark == bench) & (fq.market == "1x2") & (fq.scope == scope)].set_index("metric")
        ll, br, rp = s.loc["log_loss"], s.loc["brier"], s.loc["rps"]
        rows.append([bench, scope, int(ll.n), ll.model, ll.benchmark_value,
                     f"{ll.diff_model_minus_bench:.4f} {ci(ll.ci_low, ll.ci_high)}",
                     f"{br.diff_model_minus_bench:.4f} {ci(br.ci_low, br.ci_high)}",
                     f"{rp.diff_model_minus_bench:.4f} {ci(rp.ci_low, rp.ci_high)}"])
    fq_tab = pd.DataFrame(rows, columns=["benchmark", "scope", "n", "model log loss",
                                         "benchmark log loss", "diff log loss [CI]",
                                         "diff Brier [CI]", "diff RPS [CI]"])
    ou = fq[(fq.market == "ou25") & (fq.scope == "pooled_main") & (fq.benchmark == "pin_close")
            & (fq.metric == "log_loss")].iloc[0]
    ll_main = fq[(fq.benchmark == "pin_close") & (fq.market == "1x2") & (fq.scope == "pooled_main")
                 & (fq.metric == "log_loss")].iloc[0]
    verdict = ("higher (worse) than" if ll_main.diff_model_minus_bench > 0 else "lower (better) than")

    # ---- bet table (pooled main)
    b = bs[bs.scope == "pooled_main"].sort_values(["market", "signal", "threshold"])
    bt = pd.DataFrame({
        "market": b.market, "signal": b.signal, "threshold": b.threshold, "bets": b.n_bets,
        "ROI [CI]": [f"{r:.4f} {ci(lo, hi)}" for r, lo, hi in zip(b.roi, b.roi_ci_low, b.roi_ci_high)],
        "mean CLV [CI]": [f"{r:.4f} {ci(lo, hi)}" for r, lo, hi in
                          zip(b.mean_clv, b.clv_ci_low, b.clv_ci_high)],
        "CLV bets": b.n_clv.astype(int), "share beating close": b.share_beating_close,
        "max drawdown": b.max_drawdown})
    bt["bets"] = bt["bets"].astype(int)
    cut = ", ".join(f"{k}: {v}" for k, v in ref["cutoff_month"].items())
    w_pos = int((wt["w"] > 0).sum())
    w_all = int(wt["w"].notna().sum())
    blend_note = ""
    if w_pos * 2 < w_all:
        blend_note = (" Because w is 0 in most league-seasons, the blend is mostly the Pinnacle pre-match "
                      "fair price itself; its bets compare that price with the best Max pre-match price, "
                      "so its CLV should not be read as model skill.")
    leagues_txt =", ".join(f"{k} ({v})" for k, v in cfg["data_source"]["main_leagues"].items())
    extra_txt = ", ".join(f"{k} ({v})" for k, v in cfg["data_source"]["extra_leagues"].items())
    seasons = cfg["data_source"]["seasons"]

    md = f"""# football-odds-model

A prototype pipeline that turns public football results and odds into pre-match probabilities, checks them against Pinnacle, and runs a simple, honest bet simulation. It is a research prototype: nothing here is, or claims to be, in live use.

## Data
- Source: football-data.co.uk (snapshot 2026-11-06, raw files kept read-only with a SHA-256 manifest). {n_all} matches from {d0} to {d1}.
- Main leagues, seasons {seasons['E0'][0]}-{seasons['E0'][-1]}: {leagues_txt}. Extra leagues: {extra_txt} (USA {seasons['USA'][0]}-{seasons['USA'][-1]}, SWE {seasons['SWE'][0]}-{seasons['SWE'][-1]}, DNK {seasons['DNK'][0]}-{seasons['DNK'][-1]}).
- Pinnacle outage: in the 2025/26 data the Pinnacle feed degrades and then disappears (see `reports/phase1/pinnacle_reliability.md`). A fixed reference-price rule (`config/reference_price.yaml`) gives a match a Pinnacle reference only if its month is before the league cutoff month ({cut}), the league-month is not flagged in the diagnostics, and all Pinnacle prices of that market and timing are present and above 1.0. Average odds never replace Pinnacle. No match is dropped; it only loses the reference.
- Limit: the USA, DNK and SWE files contain closing 1X2 odds only (no pre-match odds, totals or Asian handicap), so for them the model is compared with Pinnacle closing only.

## Method
- No look-ahead: every prediction uses only matches strictly before the match date; validation is walk-forward only; closing odds are never model inputs.
- Time-decayed Dixon-Coles goal model (xi = {cfg['model']['xi']} per day, L2 shrinkage {cfg['model']['l2_penalty']}), one model per league, refitted every {cfg['model']['refit_days']} days. The first season of each league is training only: {n_pred} predictions.
- All markets (1X2, over/under 2.5, Asian handicap probabilities, both teams to score) come from the same score matrix.

## Forecast quality vs Pinnacle (separate from betting)
Scored on the same matches as the benchmark; diff = model minus benchmark, negative is better for the model; CI from a paired bootstrap over matches (B = {ev['bootstrap_B']}).

{table(fq_tab)}

On the main leagues the model's 1X2 log loss against Pinnacle closing is {verdict} the benchmark (difference {ll_main.diff_model_minus_bench:.4f}, CI {ci(ll_main.ci_low, ll_main.ci_high)}). For over/under 2.5 on the main leagues the log-loss difference is {ou.diff_model_minus_bench:.4f} {ci(ou.ci_low, ou.ci_high)}.

![Reliability of the home-win probability](reports/phase3/calibration_p_home.png)

Expected calibration error, p_home: {"; ".join(f"{r.scope} {r.forecast} {r.ece:.4f}" for r in ece.itertuples())}.

Blend: p = w * model + (1 - w) * Pinnacle pre fair, with w chosen per league on earlier evaluated seasons only; w is above 0 in {w_pos} of {w_all} league-seasons that have a blend (`reports/phase3/blend_weights.csv`).{blend_note}

## Bet simulation (main leagues, pre-match information only; separate from forecast quality)
Decision from model (or blend) probabilities and Max PRE odds only; Pinnacle closing is used afterwards for CLV. One flat-stake bet per match and market on the largest edge; outcomes above {ev['max_bet_odds']} excluded; only matches with a Pinnacle closing reference. Thresholds {ev['bet_thresholds']} were fixed in advance and all are shown. Pooled main leagues:

{table(bt)}

Reference: the mean CLV of an uninformed bet on every 1X2 outcome at Max pre odds is {base.mean_clv.iloc[0]:.4f} ({int(base.n_outcomes.iloc[0])} outcomes); the model-signal cells above should be read against this value, not against zero.

Caveats: Max odds are the best price across many bookmakers and may not be obtainable at size. Several thresholds, markets and signals are tested, so a single positive cell is not evidence. ROI intervals are bootstrap intervals over bets and ignore dependence between bets. Full tables: `reports/phase3/bet_simulation.md`.

## Limits and next steps
- No team news, lineups or expected-goals data; results-only model.
- The Pinnacle outage removes the benchmark for the most recent months of the main leagues.
- MLS, Danish and Swedish data lack pre-match odds: a pre-match odds source for them is the first thing to add.
- Next: expected goals, lineups, and a longer clean history of Pinnacle pre-match odds.

Reproduce: see `diary.md` and the scripts in `scripts/` (`run_phase1a.py`, `run_phase1b.py`, `run_phase2.py`, `run_phase3.py`, `build_readme.py`), run with `PYTHONNOUSERSITE=1 conda run -n fbmodel python <script>`.
"""
    out = safe_write_path(PROJECT_ROOT / "README.md")
    out.write_text(md, encoding="utf-8", newline="\n")
    print("README.md written,", len(md.splitlines()), "lines")


if __name__ == "__main__":
    main()
