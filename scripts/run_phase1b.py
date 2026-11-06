"""Phase 1B: cleaning -> data/processed/matches.parquet and quality/retention reports.
PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase1b.py [snapshot_date]
"""
import difflib
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

from run_phase1a import load_all, md_table, write_text  # same folder (scripts/)
from fbmodel.config import load_config
from fbmodel.data.clean import (MARKETS, QA_COLUMNS, TIMINGS, build_matches, nonnumeric_report, odds_group_columns,
                                overround)
from fbmodel.data.download import RAW_SUBDIR
from fbmodel.io_guard import safe_write_path, verify_raw_manifest

SOURCES = ("pin", "b365", "max", "avg")


def norm(df):
    """Null-representation-neutral view (None vs NaN) for round-trip comparisons."""
    return df.astype(object).where(df.notna(), None)


def norm_name(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return "".join(ch for ch in s.lower() if ch.isalnum())


def main():
    cfg = load_config()
    paths, cl = cfg["paths"], cfg["cleaning"]
    snapshot = sys.argv[1] if len(sys.argv) > 1 else "2026-11-06"
    rep = paths["reports"] / "phase1"
    verify_raw_manifest(paths["manifest"], paths["raw"])
    print("manifest OK (before)")

    data, _enc = load_all(cfg, snapshot)
    raw_frames = {k: v[0] for k, v in data.items()}
    m1, excl = build_matches(raw_frames, cfg)
    m2, _ = build_matches(raw_frames, cfg)
    pd.testing.assert_frame_equal(m1, m2)
    print("idempotent in memory: OK")
    m = m1
    out = safe_write_path(paths["processed"] / "matches.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        prev = pd.read_parquet(out)
        pd.testing.assert_frame_equal(norm(prev), norm(m), check_dtype=False)
        print("identical to previous matches.parquet: OK")
    m.to_parquet(out, index=False)
    back = pd.read_parquet(out)
    pd.testing.assert_frame_equal(norm(back), norm(m), check_dtype=False)
    print("matches.parquet shape", m.shape)

    # ------------------------------------------------------------ quality CSVs
    def save(df, name):
        df.to_csv(safe_write_path(rep / name), index=False)

    nn = nonnumeric_report(raw_frames, cfg)
    save(nn, "nonnumeric_values.csv")
    key = ["league", "season", "date", "home", "away"]
    dup = m[m.qa_exact_duplicate | m.qa_duplicate_key][key + ["qa_exact_duplicate", "qa_duplicate_key"]]
    twice = m[m.qa_team_twice_same_date][key]
    mism = m[m.qa_result_goals_mismatch][key + ["home_goals", "away_goals", "result"]]
    save(dup, "qa_duplicates.csv")
    save(twice, "qa_team_twice_same_date.csv")
    save(mism, "qa_result_goals_mismatch.csv")

    rows = []
    for (lg, se), g in m.groupby(["league", "season"]):
        t = pd.concat([g["home"], g["away"]]).value_counts()
        n = len(t)
        rows.append([lg, se, n, len(g), int(t.min()), int(t.median()), int(t.max()), n * (n - 1),
                     len(g) - n * (n - 1), lg in cl["split_phase_leagues"]])
    teams = pd.DataFrame(rows, columns=["league", "season", "teams", "matches", "min_per_team",
                                        "median_per_team", "max_per_team", "n_times_n_minus_1",
                                        "matches_minus_n_times_n_minus_1", "playoff_or_split"])
    save(teams, "teams_per_season.csv")

    canon = [c for c in m.columns if c not in QA_COLUMNS]
    miss = (m[canon].isna().groupby([m.league, m.season]).sum()
            .stack().rename("n_missing").reset_index())
    miss.columns = ["league", "season", "column", "n_missing"]
    size = m.groupby(["league", "season"]).size().rename("n_rows").reset_index()
    miss = miss.merge(size, on=["league", "season"])
    miss["share_missing"] = miss.n_missing / miss.n_rows
    save(miss, "missing_values.csv")

    oc = [c for c in m.columns if c.startswith("odds_")]
    vals = m[oc].apply(pd.to_numeric, errors="coerce")
    bad = (vals <= cfg["pinnacle_checks"]["min_valid_odds"]) | (vals > cl["odds_max_sane"])
    orows = m[m.qa_odds_out_of_range][key].copy()
    orows["columns"] = [",".join(c for c in oc if bad.loc[i, c]) for i in orows.index]
    save(orows, "odds_out_of_range.csv")

    ov = []
    for (lg, se), g in m.groupby(["league", "season"]):
        for src in SOURCES:
            for mk in MARKETS:
                for tm in TIMINGS:
                    cols = odds_group_columns(g.columns, src, mk, tm)
                    if not cols:
                        continue
                    o = overround(g[cols]).dropna()
                    if o.empty:
                        continue
                    outside = int(((o < cl["overround_min"]) | (o > cl["overround_max"])).sum())
                    ov.append([lg, se, src, tm, mk, len(o), o.median(), o.min(), o.max(),
                               outside if src in ("pin", "b365") else np.nan,
                               float((o < 1.0).mean())])
    ovd = pd.DataFrame(ov, columns=["league", "season", "source", "timing", "market", "n", "median",
                                    "min", "max", "n_outside_bounds_flagged",
                                    "share_below_1_report_only"])
    save(ovd, "overround_summary.csv")

    near = []
    for lg, g in m.groupby("league"):
        names = sorted(set(g["home"]) | set(g["away"]))
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                r = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
                if r >= cl["near_duplicate_threshold"] or norm_name(a) == norm_name(b):
                    near.append([lg, a, b, round(r, 3)])
    nd = pd.DataFrame(near, columns=["league", "name_a", "name_b", "ratio"])
    save(nd, "near_duplicate_team_names.csv")

    # ------------------------------------------------------------ USA stage evidence
    srows = []
    for se, g in m[m.league == "USA"].groupby("season"):
        t = pd.concat([g["home"], g["away"]]).value_counts()
        mode = t.mode()
        st = g["stage"].value_counts()
        po = g[g.stage == "playoff"]
        srows.append([se, len(g), len(t), ",".join(map(str, mode.tolist())),
                      len(t) * int(mode.iloc[0]) // 2 if len(mode) == 1 else None,
                      int(st.get("regular", 0)), int(st.get("playoff", 0)), int(st.get("unknown", 0)),
                      po.date.min().date().isoformat() if len(po) else "",
                      g.date.max().date().isoformat()])
    stage_tab = pd.DataFrame(srows, columns=["season", "matches", "teams", "modal_matches_per_team",
                                             "expected_regular_matches", "regular", "playoff",
                                             "unknown", "first_playoff_date", "last_date"])
    save(stage_tab, "usa_stage_evidence.csv")
    stage_all = m.groupby(["league", "stage"]).size().reset_index(name="matches")

    # ------------------------------------------------------------ retention
    rr = []
    for (lg, se), g in m.groupby(["league", "season"]):
        has_pre = g[odds_group_columns(g.columns, "pin", "1x2", "pre")].notna().any().any()
        for tm in TIMINGS:
            col = f"ref_source_1x2_{tm}"
            vc = g[col].value_counts()
            n = len(g)
            rr.append([lg, se, tm, n, int(vc.get("pin", 0)), int(vc.get("avg", 0)),
                       int(vc.get("none", 0)), float(vc.get("none", 0)) / n, has_pre])
    ret = pd.DataFrame(rr, columns=["league", "season", "timing", "played_matches", "ref_pin",
                                    "ref_avg", "ref_none", "share_lost", "league_season_has_pin_pre"])
    save(ret, "sample_retention.csv")
    # league-level primary timing: pre when the league has pre columns, else close
    prim = []
    for lg, g in ret.groupby("league"):
        tm = "pre" if g[g.timing == "pre"].league_season_has_pin_pre.any() else "close"
        s = g[g.timing == tm]
        n, p = int(s.played_matches.sum()), int(s.ref_pin.sum())
        loss = 1 - p / n
        exempt = lg in cl["loss_exempt_leagues"]
        flag = ("OK" if (loss <= cl["max_loss_share"] and p >= cl["min_valid_matches"])
                else ("ACCEPTED BY DECISION" if exempt else "STOP: report"))
        prim.append([lg, tm, n, p, int(s.ref_none.sum()), loss, flag])
    prim = pd.DataFrame(prim, columns=["league", "timing_used", "played", "ref_pin", "ref_none",
                                       "share_lost", "check_vs_max_loss_share_min_valid"])
    wide = ret.pivot_table(index=["league", "season"], columns="timing",
                           values=["played_matches", "ref_pin", "ref_avg", "ref_none", "share_lost"],
                           aggfunc="first")
    wide.columns = [f"{a}_{b}" for a, b in wide.columns]
    wide = wide.reset_index()
    wide = wide[["league", "season", "played_matches_pre", "ref_pin_pre", "ref_avg_pre", "ref_none_pre",
                 "share_lost_pre", "ref_pin_close", "ref_avg_close", "ref_none_close",
                 "share_lost_close"]]
    write_text(rep / "sample_retention.md", "\n".join([
        "# Sample retention (played matches by reference source)\n",
        f"Rule: config/reference_price.yaml. ref_avg is always 0: Avg never replaces Pinnacle. "
        f"Thresholds: max_loss_share {cl['max_loss_share']}, min_valid_matches "
        f"{cl['min_valid_matches']} (leagues {cl['loss_exempt_leagues']} accepted by decision). "
        f"Pre columns absent in USA/DNK/SWE files, so their pre columns are all 'none'.\n",
        "## Per league (pooled seasons; pre for leagues with pre odds, else close)\n", md_table(prim),
        "## Per league x season, 1X2 reference source\n", md_table(wide)]))

    # ------------------------------------------------------------ quality_report.md
    summary = pd.DataFrame({"flag": QA_COLUMNS, "rows_flagged": [int(m[c].sum()) for c in QA_COLUMNS]})
    unparsed = 0  # parse_dates raises on any unparsed value, so reaching this point means 0
    q = ["# Quality report (Phase 1B)\n",
         f"Rows in matches.parquet: {len(m)}; columns: {m.shape[1]}. Rows without a final result "
         f"excluded (counted below). Unparsed dates: {unparsed} (parse_dates raises otherwise). "
         f"Nothing is fixed: flags only.\n",
         "## Flag summary\n", md_table(summary),
         "## Rows excluded (no final result)\n", md_table(excl),
         "## Exact duplicates / same league+date+home+away (qa_duplicates.csv)\n",
         md_table(dup.head(50)),
         "## Team playing twice on one date (qa_team_twice_same_date.csv)\n", md_table(twice.head(50)),
         "## Result inconsistent with goals (qa_result_goals_mismatch.csv)\n", md_table(mism.head(50)),
         "## Teams and matches per league x season (n*(n-1) shown for all; double round robin "
         "applies to leagues without playoffs/split phases; split-phase leagues: "
         f"{cl['split_phase_leagues']}, report only)\n", md_table(teams),
         "## Stage counts per league\n", md_table(stage_all),
         "## USA stage evidence per season\n", md_table(stage_tab),
         "## Odds <= min valid or > odds_max_sane (odds_out_of_range.csv)\n",
         f"Rows flagged: {len(orows)}.\n", md_table(orows.head(50)),
         "## Overround per source / timing / market per league x season (overround_summary.csv)\n"
         f"Bounds for single-bookmaker rows (pin, b365): [{cl['overround_min']}, "
         f"{cl['overround_max']}] (flag). Max: share below 1.0 reported only. Aggregate by source:\n",
         md_table(ovd.groupby(["source", "timing", "market"]).agg(
             n=("n", "sum"), outside=("n_outside_bounds_flagged", "sum"),
             worst_min=("min", "min"), worst_max=("max", "max")).reset_index()),
         "## Max rows with overround below 1.0 (report only)\n",
         md_table(ovd[ovd.source == "max"].groupby(["league", "timing", "market"]).apply(
             lambda g: pd.Series({"n": g.n.sum(),
                                  "share_below_1": float((g.share_below_1_report_only * g.n).sum() / g.n.sum())}),
             include_groups=False).reset_index()),
         "## Missing values per canonical column x league x season\n"
         "Full table: missing_values.csv. Columns with missing values in at least one league-season "
         "(count of league-seasons affected):\n",
         md_table(miss[miss.n_missing > 0].groupby("column").agg(
             league_seasons=("n_missing", "size"), missing_total=("n_missing", "sum")).reset_index()),
         "## Near-duplicate team names (for your decision; team_aliases.yaml is empty)\n", md_table(nd)]
    write_text(rep / "quality_report.md", "\n".join(q))

    verify_raw_manifest(paths["manifest"], paths["raw"])
    print("manifest OK (after)")
    print(excl.n_excluded_no_result.sum(), "rows excluded (no result)")
    print(summary.to_string())
    print(prim.to_string())


if __name__ == "__main__":
    main()
