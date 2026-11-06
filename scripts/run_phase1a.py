"""Phase 1A: download, inventory, Pinnacle reliability. Run from the project root:
PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase1a.py [snapshot_date]
"""
import hashlib
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from fbmodel.config import load_config
from fbmodel.data.columns import classify_column
from fbmodel.data.download import (LOG_COLUMNS, RAW_SUBDIR, add_raw_file, download_all,
                                   make_http_fetch)
from fbmodel.data.read_raw import read_raw_csv
from fbmodel.data.reliability import (MARKET_COLUMNS, first_suspect_month, implied_probs,
                                      monthly_diagnostics, odds_block)
from fbmodel.io_guard import safe_write_path, verify_raw_manifest

INV = {}  # set from config in main(): config section "inventory"
CHK = {}  # config section "pinnacle_checks"


def md_table(df: pd.DataFrame, floatfmt="{:.4f}") -> str:
    if df.empty:
        return "_(empty)_\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.astype(object).iterrows():
        cells = []
        for v in r:
            if isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            else:
                cells.append("" if v is None or v is pd.NA else str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def parse_date_col(s: pd.Series) -> pd.Series:
    s = s.astype("string").str.strip()
    a = pd.to_datetime(s, format="%d/%m/%Y", errors="coerce")
    b = pd.to_datetime(s, format="%d/%m/%y", errors="coerce")
    return a.fillna(b)


def write_text(path: Path, text: str):
    p = safe_write_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


def fetch_notes(cfg, snapshot, fetch):
    ds, paths = cfg["data_source"], cfg["paths"]
    url = ds["notes_url"].format(base_url=ds["base_url"])
    rel = f"{RAW_SUBDIR}/{snapshot}/notes.txt"
    status, content = 0, b""
    for _ in range(1 + ds["max_retries"]):
        try:
            status, content = fetch(url)
        except Exception:  # noqa: BLE001
            status, content = 0, b""
        if status == 200:
            break
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if status == 200:
        add_raw_file(content, rel, paths["raw"], paths["manifest"])
        row = [url, rel, stamp, status, len(content), hashlib.sha256(content).hexdigest()]
    else:
        row = [url, rel, stamp, status, 0, ""]
    log = Path(paths["download_log"])
    pd.DataFrame([row], columns=LOG_COLUMNS).to_csv(log, mode="a", header=not log.exists(),
                                                    index=False)


def load_all(cfg, snapshot):
    """dict (league, season) -> (frame, kind); extras are split by configured season."""
    ds, paths = cfg["data_source"], cfg["paths"]
    base = paths["raw"] / RAW_SUBDIR / snapshot
    out, encodings = {}, []
    for league in ds["main_leagues"]:
        for season in ds["seasons"][league]:
            f = base / f"{league}_{season}.csv"
            if not f.exists():
                continue
            df, enc = read_raw_csv(f)
            out[(league, str(season))] = (df, "main")
            encodings.append((f.name, enc))
    for league in ds["extra_leagues"]:
        f = base / f"{league}_all.csv"
        if not f.exists():
            continue
        df, enc = read_raw_csv(f)
        encodings.append((f.name, enc))
        df["Season"] = df["Season"].astype("string").str.strip()
        for season in [str(s) for s in ds["seasons"][league]]:
            out[(league, season)] = (df[df["Season"] == season].reset_index(drop=True), "extra")
    return out, encodings


def played_mask(df, kind):
    return df[INV["result_columns"][kind]].astype("string").str.strip().isin(INV["played_codes"])


def slot_columns(cols):
    """(market, timing, source) -> {side: first column in file order}."""
    slots = {}
    for c in cols:
        k = classify_column(c)
        if k["family"] in ("odds_1x2", "odds_ou", "odds_ah") and k["source"] in INV["sources"]:
            slots.setdefault((k["market"], k["timing"], k["source"]), {}).setdefault(k["side"], c)
    return slots


def slot_coverage(df, slot):
    cols = list(slot.values())
    b = df[cols].apply(pd.to_numeric, errors="coerce")
    return float((b.notna().all(axis=1) & (b > CHK["min_valid_odds"]).all(axis=1)).mean()) if len(df) else np.nan


def main():
    cfg = load_config()
    INV.update(cfg["inventory"])
    CHK.update(cfg["pinnacle_checks"])
    paths = cfg["paths"]
    snapshot = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    rep = paths["reports"] / "phase1"
    snap_dir = paths["raw"] / RAW_SUBDIR / snapshot

    if snap_dir.exists():
        print(f"snapshot {snapshot} exists; not downloading again")
    else:
        fetch = make_http_fetch(cfg)
        download_all(cfg, snapshot, fetch=fetch)
        fetch_notes(cfg, snapshot, fetch)
    log = pd.read_csv(paths["download_log"])
    verify_raw_manifest(paths["manifest"], paths["raw"])

    data, encodings = load_all(cfg, snapshot)
    enc_df = pd.DataFrame(encodings, columns=["file", "encoding"])
    leagues = list(cfg["data_source"]["main_leagues"]) + list(cfg["data_source"]["extra_leagues"])

    # ---- inventory_columns.csv -------------------------------------------------
    inv_rows = []
    for (league, season), (df, kind) in data.items():
        for c in df.columns:
            k = classify_column(c)
            nn = int(df[c].notna().sum())
            inv_rows.append([league, season, c, k["family"], k["market"], k["source"],
                             k["timing"], k["side"], len(df), nn,
                             nn / len(df) if len(df) else np.nan])
    inv = pd.DataFrame(inv_rows, columns=["league", "season", "column", "family", "market",
                                          "source", "timing", "side", "n_rows", "n_nonnull",
                                          "share_nonnull"])
    safe_write_path(rep / "x").parent.mkdir(parents=True, exist_ok=True)
    inv.to_csv(safe_write_path(rep / "inventory_columns.csv"), index=False)

    # ---- (a) rows ---------------------------------------------------------------
    a_rows = []
    for (league, season), (df, kind) in data.items():
        pm = played_mask(df, kind)
        d = parse_date_col(df["Date"])
        a_rows.append([league, season, len(df), int((~pm).sum()), int(d.isna().sum()),
                       d.max().date().isoformat() if d.notna().any() else "",
                       d[pm].max().date().isoformat() if pm.any() else ""])
    a_tab = pd.DataFrame(a_rows, columns=["league", "season", "rows", "rows_without_result",
                                          "unparsed_dates", "last_date_any_row",
                                          "last_date_played"])
    live = a_tab[a_tab.apply(lambda r: INV["in_progress"].get(r.league) == r.season, axis=1)].copy()
    live["snapshot_date"] = snapshot

    # ---- (b) coverage -----------------------------------------------------------
    b_rows = []
    for (league, season), (df, kind) in data.items():
        pdf = df[played_mask(df, kind)]
        for (market, timing, source), slot in sorted(slot_columns(df.columns).items()):
            if set(slot) != set(INV["market_outcomes"][market]):
                continue
            b_rows.append([league, season, market, timing, source, len(pdf),
                           slot_coverage(pdf, slot)])
    b_tab = pd.DataFrame(b_rows, columns=["league", "season", "market", "timing", "source",
                                          "n_played", "coverage"])
    b_tab.to_csv(safe_write_path(rep / "inventory_coverage.csv"), index=False)

    # ---- (c) per-league capability ------------------------------------------------
    def cov(league, market, timing, sources):
        t = b_tab[(b_tab.league == league) & (b_tab.market == market)
                  & (b_tab.timing == timing) & (b_tab.source.isin(sources))]
        if t.empty:
            return "absent"
        parts = []
        for s, g in t.groupby("source"):
            parts.append(f"{s}:{np.average(g.coverage, weights=g.n_played):.2f}")
        return ", ".join(parts)

    c_rows = []
    for league in leagues:
        has_time = any(INV["kickoff_column"] in df.columns and df[INV["kickoff_column"]].notna().any()
                       for (lg, _), (df, _k) in data.items() if lg == league)
        c_rows.append([league, cov(league, "1x2", "pre", ["pinnacle"]),
                       cov(league, "1x2", "close", ["pinnacle"]),
                       cov(league, "1x2", "pre", ["max", "avg"]),
                       cov(league, "1x2", "close", ["max", "avg"]),
                       cov(league, "ou25", "pre", ["pinnacle", "max", "avg"]),
                       cov(league, "ou25", "close", ["pinnacle", "max", "avg"]),
                       cov(league, "ah", "pre", ["pinnacle", "max", "avg"]),
                       cov(league, "ah", "close", ["pinnacle", "max", "avg"]),
                       "yes" if has_time else "no"])
    c_tab = pd.DataFrame(c_rows, columns=[
        "league", "pin_1x2_pre", "pin_1x2_close", "maxavg_1x2_pre", "maxavg_1x2_close",
        "ou25_pre", "ou25_close", "ah_pre", "ah_close", "kickoff_time_col"])

    # ---- (d) USA playoffs -------------------------------------------------------
    usa = [(s, df) for (lg, s), (df, _k) in data.items() if lg == "USA"]
    stage_like = sorted({c for _s, df in usa for c in df.columns
                         if any(w in c.lower() for w in ("stage", "round", "playoff", "phase"))})
    d_txt = (f"Columns whose name suggests a stage/round/playoff marker: "
             f"{stage_like if stage_like else 'none'}.\n")
    d_rows, wk_rows = [], []
    for s, df in sorted(usa, key=lambda x: x[0]):
        df = df[played_mask(df, "extra")].copy()
        df["d"] = parse_date_col(df["Date"])
        teams = pd.concat([df["Home"], df["Away"]]).value_counts()
        mode = int(teams.mode().iloc[0])
        above = teams[teams > mode]
        d_rows.append([s, len(df), len(teams), mode, int(teams.max()), len(above),
                       int((above - mode).sum()),
                       df["d"].min().date().isoformat(), df["d"].max().date().isoformat()])
        wk = df.groupby(df["d"].dt.to_period("W-SUN")).size().tail(INV["last_weeks"])
        for per, n in wk.items():
            wk_rows.append([s, str(per), int(n)])
    d_tab = pd.DataFrame(d_rows, columns=[
        "season", "played_rows", "teams", "modal_matches_per_team", "max_matches_per_team",
        "teams_above_mode", "extra_team_matches_above_mode", "first_date", "last_date"])
    wk_tab = pd.DataFrame(wk_rows, columns=["season", "week", "matches"])

    # ---- (e) AH sign convention ---------------------------------------------------
    e_parts = []
    for (league, season), (df, kind) in data.items():
        if kind != "main" or "AHh" not in df.columns or "PSH" not in df.columns:
            continue
        pdf = df[played_mask(df, kind)]
        blk, ok = odds_block(pdf, MARKET_COLUMNS["1x2"][("pin", "pre")], CHK["min_valid_odds"])
        ah = pd.to_numeric(pdf["AHh"], errors="coerce")
        keep = ok & ah.notna()
        if keep.any():
            e_parts.append(pd.DataFrame({"p_home": implied_probs(blk[keep])["PSH"],
                                         "AHh": ah[keep]}))
    e_all = pd.concat(e_parts) if e_parts else pd.DataFrame(columns=["p_home", "AHh"])
    if len(e_all) >= cfg["inventory"]["ah_sign_min_rows"]:
        rho = spearmanr(e_all.p_home, e_all.AHh).statistic
        e_all["bin"] = pd.qcut(e_all.p_home, cfg["inventory"]["ah_sign_bins"], labels=False) + 1
        e_tab = e_all.groupby("bin").agg(n=("AHh", "size"), mean_p_home=("p_home", "mean"),
                                         mean_AHh=("AHh", "mean"),
                                         median_AHh=("AHh", "median")).reset_index()
        verdict = ("AHh falls as the Pinnacle pre home-win probability rises: negative AHh means "
                   "the home team is favourite (line quoted for the HOME team; negative = home "
                   "gives goals)." if rho < 0 else
                   "AHh rises with the Pinnacle pre home-win probability: the line is not "
                   "quoted in the usual home-team sign convention.")
        e_txt = (f"Rows used (played, Pinnacle pre 1X2 and AHh present, main leagues, all "
                 f"seasons): {len(e_all)}. Spearman correlation(AHh, Pinnacle pre home-win "
                 f"probability) = {rho:.4f}.\n\n" + md_table(e_tab) + f"\n{verdict}\n")
    else:
        e_txt = "Too few rows for the AH sign check.\n"

    # ---- (f) unclassified -----------------------------------------------------------
    f_tab = (inv[inv.family == "unclassified"].groupby("column")
             .agg(leagues=("league", lambda x: ",".join(sorted(set(x)))),
                  seasons=("season", lambda x: ",".join(sorted(set(x)))),
                  n_nonnull=("n_nonnull", "sum")).reset_index())

    out_rows = []
    for league in cfg["data_source"]["extra_leagues"]:
        f = paths["raw"] / RAW_SUBDIR / snapshot / f"{league}_all.csv"
        if f.exists():
            raw_df, _enc = read_raw_csv(f)
            keep = [str(x) for x in cfg["data_source"]["seasons"][league]]
            sv = raw_df["Season"].astype("string").str.strip()
            for sea, n in sv[~sv.isin(keep)].value_counts().sort_index().items():
                out_rows.append([league, sea, int(n)])
    out_tab = pd.DataFrame(out_rows, columns=["league", "season_label", "rows_not_in_config_seasons"])

    enc_summary = enc_df.groupby("encoding").size().reset_index(name="files")
    md = [f"# Phase 1A inventory summary\n\nSnapshot date: {snapshot}. Generated by "
          f"scripts/run_phase1a.py.\n",
          "## Encodings\n", md_table(enc_summary),
          "## (a) Rows per league x season\n", md_table(a_tab),
          "### USA / SWE 2026 (in progress): last match date included vs snapshot date\n",
          md_table(live),
          "### Extra-league rows outside the configured seasons (not analysed, not deleted)\n",
          md_table(out_tab),
          "## (b) Coverage per league x season x market x timing x source\n"
          "Share of played rows with all outcomes present and above the minimum valid odds (also in "
          "inventory_coverage.csv).\n", md_table(b_tab, "{:.3f}"),
          "## (c) Per league availability (share of played rows, pooled over seasons)\n"
          "Pooled shares hide the Pinnacle outage: Pinnacle is complete until the first suspect "
          "month and then missing or degraded (months in pinnacle_reliability.md). Avg and Max "
          "stay complete throughout.\n",
          md_table(c_tab),
          "## Declared limit: extra leagues (USA, DNK, SWE)\n"
          "These files hold closing 1X2 odds only: no pre-closing odds, no totals and no Asian "
          "handicap. For them there is no CLV, no pre-match edge and no opening-odds blend. "
          "Phase 3 will compare Max closing with the Pinnacle closing fair price only. This is "
          "a declared limit, decided by the project owner at the start of Part B.\n",
          "## (d) USA playoffs\n", d_txt,
          "\nPer-team match counts per season (modal = regular-season count; teams above "
          "it played extra matches):\n", md_table(d_tab),
          f"\nLast {INV['last_weeks']} calendar weeks (Mon-Sun) of each season, played matches:\n",
          md_table(wk_tab),
          "\n## (e) Asian handicap sign convention (inferred empirically)\n", e_txt,
          "\n## (f) Unclassified columns\n", md_table(f_tab)]
    write_text(rep / "inventory_summary.md", "\n".join(md))

    # ---- Pinnacle reliability -----------------------------------------------------
    diags, frames = [], {}
    for league in leagues:
        parts = []
        for (lg, _season), (df, kind) in data.items():
            if lg != league:
                continue
            p = df[played_mask(df, kind)].copy()
            p["date"] = parse_date_col(p["Date"])
            p["league"] = league
            parts.append(p)
        if not parts:
            continue
        lf = pd.concat(parts, ignore_index=True)
        lf = lf[lf["date"].notna()].reset_index(drop=True)
        frames[league] = lf
        diags.append(monthly_diagnostics(lf, cfg))
    diag = pd.concat(diags, ignore_index=True)
    diag.to_csv(safe_write_path(rep / "pinnacle_reliability.csv"), index=False)
    first = first_suspect_month(diag)

    ret_rows = []
    d1 = diag[diag.market == "1x2"]
    for league, lf in frames.items():
        lf = lf.copy()
        lf["month"] = lf["date"].dt.strftime("%Y-%m")
        susp = d1[d1.league == league].set_index("month")["suspect"].to_dict()
        lf["suspect"] = lf["month"].map(susp).fillna(False).astype(bool)
        fs = first[league]
        n = len(lf)
        for timing in ("pre", "close"):
            pb, pok = odds_block(lf, MARKET_COLUMNS["1x2"][("pin", timing)], CHK["min_valid_odds"])
            ab, aok = odds_block(lf, MARKET_COLUMNS["1x2"][("avg", timing)], CHK["min_valid_odds"])
            if pb is None:
                ret_rows.append([league, timing, n, fs, None, None, None])
                continue
            if aok is None:
                aok = pd.Series(False, index=lf.index)
            before = pd.Series(True, index=lf.index) if fs is None else lf["month"] < fs
            ret_rows.append([league, timing, n, fs, int((pok & before).sum()),
                             int(((pok & ~lf.suspect) | (aok & lf.suspect)).sum()),
                             int((pok & ~lf.suspect).sum())])
    ret = pd.DataFrame(ret_rows, columns=[
        "league", "timing", "played_matches", "first_suspect_month",
        "kept_i_pin_before_first_suspect", "kept_ii_pin_reliable_else_avg",
        "kept_iii_pin_excl_suspect_months"])
    for c in list(ret.columns[4:]):
        ret[c.replace("kept_", "share_", 1)] = ret[c].astype(float) / ret["played_matches"]
    ret.to_csv(safe_write_path(rep / "pinnacle_retention.csv"), index=False)

    summ = d1.groupby("league").agg(months=("month", "size"),
                                    suspect_months=("suspect", "sum")).reset_index()
    summ["first_suspect_month"] = summ.league.map(first)
    reasons = d1[d1.suspect].assign(r=lambda x: x.suspect_reasons.str.split(";")).explode("r")
    rc = reasons.groupby(["league", "r"]).size().reset_index(name="months")
    sus_list = d1[d1.suspect][["league", "month", "n_matches", "pin_pre_coverage",
                               "pin_close_coverage", "stale_share", "overround_pre_median",
                               "overround_close_median", "divergence_pre_p95",
                               "divergence_close_p95", "suspect_reasons"]]
    other = diag[(diag.market != "1x2") & diag.suspect].groupby(["league", "market"]).size() \
        .reset_index(name="suspect_months")
    chk = cfg["pinnacle_checks"]
    pr = [f"# Pinnacle reliability (Phase 1A)\n\nThresholds (config pinnacle_checks, set before "
          f"any betting analysis): {chk}.\n\nFull per league x month x market table with all "
          f"statistics: pinnacle_reliability.csv. A month is suspect if any threshold is "
          f"breached for a timing present in the file; USA/DNK/SWE files contain closing odds "
          f"only, so only close is checked there. first_suspect_month and the retention tables "
          f"use the 1X2 rows. Played matches only.\n",
          "## Per league summary (1X2)\n", md_table(summ),
          "## Suspect months by reason (1X2; a month can have several reasons)\n", md_table(rc),
          "## Suspect months in other markets (count)\n", md_table(other),
          "## Retention (1X2; matches kept, and share of played matches)\n"
          "Note: (ii) is near 100% only because Avg fills the whole outage window; it is not "
          "Pinnacle retention (the adopted rule never substitutes Avg, see sample_retention.md). "
          "The first suspect month can come from a divergence breach in a fully covered month "
          "(USA, SWE 2025-08): a conservative cut, not the start of the outage.\n"
          "(i)Pinnacle valid, only months before the first suspect month; (ii) Pinnacle valid "
          "in non-suspect months, Avg valid in suspect months; (iii) Pinnacle valid, suspect "
          "months excluded. 'pre' rows are empty where the file has no pre columns.\n",
          md_table(ret), "## All suspect months (1X2)\n", md_table(sus_list)]
    write_text(rep / "pinnacle_reliability.md", "\n".join(pr))

    print(log.assign(ok=log.http_status == 200).groupby("ok").size())
    print(log[log.http_status != 200].to_string())
    print(enc_df.to_string())
    verify_raw_manifest(paths["manifest"], paths["raw"])
    print("manifest OK")


if __name__ == "__main__":
    main()
