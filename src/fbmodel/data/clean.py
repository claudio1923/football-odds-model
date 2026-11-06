"""Phase 1B cleaning: canonical names, QA flags, stage, reference-price source.

Flag, never fix: no value is changed, no row is dropped except rows without a final
result (played_only), which are counted.
"""
import hashlib
import re

import numpy as np
import pandas as pd
import yaml

from fbmodel.config import PROJECT_ROOT
from fbmodel.data.reliability import MARKET_COLUMNS, first_suspect_month, monthly_diagnostics  # noqa: F401

_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y")
MARKETS = ("1x2", "ou25", "ah")
TIMINGS = ("pre", "close")
QA_COLUMNS = ["qa_exact_duplicate", "qa_duplicate_key", "qa_team_twice_same_date",
              "qa_result_goals_mismatch", "qa_odds_out_of_range", "qa_overround_out_of_range"]
REF_COLUMNS = [f"ref_source_{m}_{t}" for m in MARKETS for t in TIMINGS]


# ---------------------------------------------------------------- small helpers
def parse_dates(s: pd.Series) -> pd.Series:
    """dd/mm/yy and dd/mm/yyyy, day first. Raises ValueError on any unparsed value."""
    txt = s.astype("string").str.strip()
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for fmt in _DATE_FORMATS:
        todo = out.isna()
        if not todo.any():
            break
        out[todo] = pd.to_datetime(txt[todo], format=fmt, errors="coerce")
    bad = out.isna()
    if bad.any():
        raise ValueError(f"{int(bad.sum())} unparsed date value(s), first: {s[bad].iloc[0]!r}")
    return out


def overround(odds: pd.DataFrame) -> pd.Series:
    """Sum of 1/odds over the columns; NaN when any outcome is missing or <= 0."""
    o = odds.apply(pd.to_numeric, errors="coerce")
    bad = o.isna().any(axis=1) | (o <= 0).any(axis=1)
    return (1.0 / o.where(~bad)).sum(axis=1, min_count=1).where(~bad)


def match_id(league, date, home, away) -> str:
    """Deterministic 16-hex hash of league, ISO date, home and away names."""
    d = pd.Timestamp(date).strftime("%Y-%m-%d")
    key = "|".join([str(league), d, str(home), str(away)])
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------- config files
def _load_yaml(path):
    with open(PROJECT_ROOT / path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_column_map(cfg) -> dict:
    return _load_yaml(cfg["cleaning"]["paths"]["column_map"])


def load_reference_rule(cfg) -> dict:
    return _load_yaml(cfg["cleaning"]["paths"]["reference_price"])


# ---------------------------------------------------------------- reference price
def assign_ref_source(df: pd.DataFrame, rule: dict) -> pd.Series:
    """'pin' only if: month before the league's cutoff_month AND not suspect_month AND all
    rule['pin_columns'] present and > rule['min_valid_odds']; else 'none'. 'avg' is never
    assigned (Avg never replaces Pinnacle)."""
    none = pd.Series("none", index=df.index, dtype=object)
    cols = list(rule["pin_columns"])
    if not all(c in df.columns for c in cols):
        return none
    month = pd.to_datetime(df["date"]).dt.strftime("%Y-%m")
    cutoff = df["league"].map(rule["cutoff_month"])
    before = cutoff.notna() & (month < cutoff.fillna(""))
    vals = df[cols].apply(pd.to_numeric, errors="coerce")
    valid = vals.notna().all(axis=1) & (vals > rule["min_valid_odds"]).all(axis=1)
    ok = before & valid & ~df["suspect_month"].astype(bool)
    return none.where(~ok, "pin")


# ---------------------------------------------------------------- QA flags
def flag_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Add boolean columns qa_exact_duplicate, qa_duplicate_key, qa_team_twice_same_date,
    qa_result_goals_mismatch. Rows are neither removed nor changed; order is kept."""
    out = df.copy()
    out["qa_exact_duplicate"] = df.duplicated(keep=False).to_numpy()
    out["qa_duplicate_key"] = df.duplicated(["league", "date", "home", "away"], keep=False).to_numpy()
    long = pd.concat([
        pd.DataFrame({"league": df["league"], "date": df["date"], "team": df["home"], "i": df.index}),
        pd.DataFrame({"league": df["league"], "date": df["date"], "team": df["away"], "i": df.index}),
    ])
    twice = long[long.duplicated(["league", "date", "team"], keep=False)]["i"].unique()
    out["qa_team_twice_same_date"] = df.index.isin(twice)
    hg = pd.to_numeric(df["home_goals"], errors="coerce")
    ag = pd.to_numeric(df["away_goals"], errors="coerce")
    derived = pd.Series(np.where(hg > ag, "H", np.where(hg == ag, "D", "A")), index=df.index)
    derived = derived.where(hg.notna() & ag.notna())
    mismatch = (derived != df["result"]) & df["result"].notna()
    out["qa_result_goals_mismatch"] = mismatch.fillna(True).to_numpy().astype(bool)
    return out


def _odds_columns(df):
    return [c for c in df.columns if c.startswith("odds_")]


def odds_group_columns(columns, source, market, timing):
    pat = re.compile(rf"^odds_{market}_{source}_{timing}_")
    return [c for c in columns if pat.match(c)]


# ---------------------------------------------------------------- stage
def assign_stage(df: pd.DataFrame, cfg) -> pd.Series:
    """regular by default; unknown for leagues in stage_unknown_leagues; for playoff
    leagues a match is 'playoff' when both teams already played >= N matches of the
    season (N = unique modal matches per team), but only in seasons where the rule is
    validated: rows - playoff_count == teams * N / 2. In other seasons (and seasons in
    progress) the rule matches are 'unknown'."""
    cl = cfg["cleaning"]
    stage = pd.Series("regular", index=df.index, dtype=object)
    stage[df["league"].isin(cl["stage_unknown_leagues"])] = "unknown"
    in_prog = cfg["inventory"]["in_progress"]
    for (league, season), g in df.groupby(["league", "season"]):
        if league not in cl["playoff_leagues"]:
            continue
        if in_prog.get(league) == season:
            stage[g.index] = "unknown"
            continue
        g = g.sort_values("date", kind="mergesort")
        counts, prior_min = {}, pd.Series(0, index=g.index)
        for _d, day in g.groupby("date", sort=True):
            pm = [min(counts.get(h, 0), counts.get(a, 0)) for h, a in zip(day["home"], day["away"])]
            prior_min[day.index] = pm
            for h, a in zip(day["home"], day["away"]):
                counts[h] = counts.get(h, 0) + 1
                counts[a] = counts.get(a, 0) + 1
        per_team = pd.Series(counts)
        modes = per_team.mode()
        flagged = prior_min >= modes.iloc[0]
        validated = (len(modes) == 1
                     and (per_team.size * int(modes.iloc[0])) % 2 == 0
                     and len(g) - int(flagged.sum()) == per_team.size * int(modes.iloc[0]) // 2)
        if validated:
            stage[flagged[flagged].index] = "playoff"
        elif flagged.any():
            # rule not validated: everything from the first rule-flagged date on is unknown
            first = g.loc[flagged[flagged].index, "date"].min()
            stage[g[g["date"] >= first].index] = "unknown"
    return stage


# ---------------------------------------------------------------- main builder
def _canonical_frame(raw, league, season, cmap, cfg):
    mapping = cmap["map"]
    cols = {}
    for c in raw.columns:
        if c in mapping:
            canon = mapping[c]
            if canon in cols:
                raise ValueError(f"{league} {season}: two columns map to {canon}")
            cols[canon] = raw[c]
        elif c not in cmap["dropped"]:
            raise ValueError(f"{league} {season}: column {c!r} is neither mapped nor dropped")
    return pd.DataFrame(cols, index=raw.index)


def build_matches(raw_frames: dict, cfg):
    """raw_frames: {(league, season): raw DataFrame as returned by read_raw_csv}.
    Returns (matches, exclusions). Rows without a valid final result are excluded and
    counted in exclusions (league, season, n_raw, n_excluded_no_result, n_kept)."""
    cmap = load_column_map(cfg)
    rule = load_reference_rule(cfg)
    inv, chk, cl = cfg["inventory"], cfg["pinnacle_checks"], cfg["cleaning"]
    canon_all = [c for c in cmap["availability"]]
    parts, excl, diag_parts = [], [], {}
    for (league, season), raw in raw_frames.items():
        res_col = "FTR" if "FTR" in raw.columns else "Res"
        played = raw[res_col].astype("string").str.strip().isin(inv["played_codes"])
        excl.append([league, str(season), len(raw), int((~played).sum()), int(played.sum())])
        r = raw[played].copy()
        if r.empty:
            continue
        date = parse_dates(r["Date"])
        c = _canonical_frame(r, league, season, cmap, cfg)
        c["date"] = date
        for col in c.columns:
            if col.startswith("odds_") or col.startswith("ah_line") or col in (
                    "home_goals", "away_goals", "ht_home_goals", "ht_away_goals"):
                c[col] = pd.to_numeric(c[col], errors="coerce")  # tokens listed by nonnumeric_report
        c["league"] = league
        c["season"] = str(season)
        c["season_note"] = cl["season_notes"].get(league, {}).get(str(season))
        parts.append(c)
        d = r.copy()
        d["date"] = date
        d["league"] = league
        diag_parts.setdefault(league, []).append(d)
    excl_df = pd.DataFrame(excl, columns=["league", "season", "n_raw", "n_excluded_no_result", "n_kept"])
    if not parts:
        return pd.DataFrame(columns=canon_all), excl_df
    df = pd.concat(parts, ignore_index=True)
    for col in canon_all:
        if col not in df.columns:
            df[col] = np.nan if col not in ("season_note",) else None
    df["kickoff"] = df["kickoff"].astype("string").str.strip().astype(object).where(df["kickoff"].notna(), None)

    # suspect months from the 1X2 diagnostics of each league (raw column names)
    suspect = {}
    for league, ps in diag_parts.items():
        dg = monthly_diagnostics(pd.concat(ps, ignore_index=True), cfg)
        one = dg[dg["market"] == "1x2"]
        suspect[league] = set(one[one["suspect"].astype(bool)]["month"])
    month = df["date"].dt.strftime("%Y-%m")
    df["suspect_month"] = [m in suspect.get(lg, set()) for lg, m in zip(df["league"], month)]
    for m in MARKETS:
        for t in TIMINGS:
            r_ = dict(rule)
            r_["pin_columns"] = odds_group_columns(df.columns, "pin", m, t)
            r_["min_valid_odds"] = chk["min_valid_odds"]
            df[f"ref_source_{m}_{t}"] = assign_ref_source(df, r_) if r_["pin_columns"] else "none"
    df = df.drop(columns=["suspect_month"])

    df["stage"] = assign_stage(df, cfg)
    df = flag_quality(df.sort_values(["date", "league", "home", "away"], kind="mergesort")
                      .reset_index(drop=True))
    oc = _odds_columns(df)
    vals = df[oc].apply(pd.to_numeric, errors="coerce")
    df["qa_odds_out_of_range"] = ((vals <= chk["min_valid_odds"]) | (vals > cl["odds_max_sane"])).any(axis=1)
    bad = pd.Series(False, index=df.index)
    for src in ("pin", "b365"):
        for m in MARKETS:
            for t in TIMINGS:
                cols = odds_group_columns(df.columns, src, m, t)
                if cols:
                    o = overround(df[cols])
                    bad |= o.notna() & ((o < cl["overround_min"]) | (o > cl["overround_max"]))
    df["qa_overround_out_of_range"] = bad
    df["match_id"] = [match_id(a, b, c, d) for a, b, c, d in
                      zip(df["league"], df["date"], df["home"], df["away"])]
    df["_ko"] = df["kickoff"].fillna("99:99")
    df = (df.sort_values(["date", "_ko", "league", "home"], kind="mergesort")
            .drop(columns="_ko").reset_index(drop=True))
    front = ["match_id", "league", "season", "season_note", "date", "kickoff", "home", "away",
             "stage", "home_goals", "away_goals", "result"]
    rest = [c for c in canon_all if c not in front and c not in REF_COLUMNS and c not in QA_COLUMNS]
    return df[front + rest + REF_COLUMNS + QA_COLUMNS], excl_df


def nonnumeric_report(raw_frames: dict, cfg) -> pd.DataFrame:
    """Non-empty raw values in numeric columns that are not numbers (they become NaN in
    matches; the raw file keeps them). Columns: league, season, column, canonical, value,
    date, home, away."""
    cmap = load_column_map(cfg)
    rows = []
    for (league, season), raw in raw_frames.items():
        for c in raw.columns:
            canon = cmap["map"].get(c)
            if canon is None or not (canon.startswith("odds_") or canon.startswith("ah_line")
                                     or canon in ("home_goals", "away_goals",
                                                  "ht_home_goals", "ht_away_goals")):
                continue
            num = pd.to_numeric(raw[c], errors="coerce")
            bad = raw[c].notna() & num.isna()
            for i in raw.index[bad]:
                home = raw.loc[i, "HomeTeam" if "HomeTeam" in raw.columns else "Home"]
                away = raw.loc[i, "AwayTeam" if "AwayTeam" in raw.columns else "Away"]
                rows.append([league, str(season), c, canon, str(raw.loc[i, c]),
                             raw.loc[i, "Date"], home, away])
    return pd.DataFrame(rows, columns=["league", "season", "column", "canonical", "value",
                                       "date", "home", "away"])
