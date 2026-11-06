"""Pinnacle reliability diagnostics. Evaluation of data quality only: implied
probabilities here are diagnostics, never model features."""
import numpy as np
import pandas as pd

# market -> (source, timing) -> raw football-data column names, outcome order fixed
MARKET_COLUMNS = {
    "1x2": {
        ("pin", "pre"): ["PSH", "PSD", "PSA"],
        ("pin", "close"): ["PSCH", "PSCD", "PSCA"],
        ("avg", "pre"): ["AvgH", "AvgD", "AvgA"],
        ("avg", "close"): ["AvgCH", "AvgCD", "AvgCA"],
        ("max", "pre"): ["MaxH", "MaxD", "MaxA"],
        ("max", "close"): ["MaxCH", "MaxCD", "MaxCA"],
    },
    "ou25": {
        ("pin", "pre"): ["P>2.5", "P<2.5"],
        ("pin", "close"): ["PC>2.5", "PC<2.5"],
        ("avg", "pre"): ["Avg>2.5", "Avg<2.5"],
        ("avg", "close"): ["AvgC>2.5", "AvgC<2.5"],
        ("max", "pre"): ["Max>2.5", "Max<2.5"],
        ("max", "close"): ["MaxC>2.5", "MaxC<2.5"],
    },
    "ah": {
        ("pin", "pre"): ["PAHH", "PAHA"],
        ("pin", "close"): ["PCAHH", "PCAHA"],
        ("avg", "pre"): ["AvgAHH", "AvgAHA"],
        ("avg", "close"): ["AvgCAHH", "AvgCAHA"],
        ("max", "pre"): ["MaxAHH", "MaxAHA"],
        ("max", "close"): ["MaxCAHH", "MaxCAHA"],
    },
}
OUTPUT_COLUMNS = [
    "league", "month", "market", "n_matches", "pin_pre_coverage", "pin_close_coverage",
    "stale_share", "overround_pre_median", "overround_pre_p5", "overround_pre_p95",
    "overround_close_median", "overround_close_p5", "overround_close_p95",
    "divergence_pre_median", "divergence_pre_p95", "divergence_close_median",
    "divergence_close_p95", "max_below_pin_pre", "max_below_pin_close",
    "suspect", "suspect_reasons",
]


def implied_probs(odds: pd.DataFrame) -> pd.DataFrame:
    """(1/odds) / row sum. Rows with NaN or odds <= 0 become all-NaN. Diagnostic only."""
    o = odds.astype(float)
    bad = o.isna().any(axis=1) | (o <= 0).any(axis=1)
    inv = 1.0 / o.where(~bad)
    return inv.div(inv.sum(axis=1), axis=0)


def odds_block(g: pd.DataFrame, cols):
    """Odds block as floats, plus the validity mask (all present and > 1.0)."""
    if not all(c in g.columns for c in cols):
        return None, None
    b = g[cols].apply(pd.to_numeric, errors="coerce")
    return b, b.notna().all(axis=1) & (b > 1.0).all(axis=1)


def _stats(overround: pd.Series):
    if overround.empty:
        return np.nan, np.nan, np.nan
    return overround.median(), overround.quantile(0.05), overround.quantile(0.95)


def _group_row(g: pd.DataFrame, market: str) -> dict:
    cols = MARKET_COLUMNS[market]
    n = len(g)
    row = {"n_matches": n}
    blocks = {k: odds_block(g, c) for k, c in cols.items()}
    for timing in ("pre", "close"):
        pin, ok = blocks[("pin", timing)]
        if pin is None:
            row.update({f"pin_{timing}_coverage": np.nan,
                        f"overround_{timing}_median": np.nan,
                        f"overround_{timing}_p5": np.nan, f"overround_{timing}_p95": np.nan,
                        f"divergence_{timing}_median": np.nan,
                        f"divergence_{timing}_p95": np.nan,
                        f"max_below_pin_{timing}": np.nan})
            continue
        row[f"pin_{timing}_coverage"] = ok.sum() / n
        over = (1.0 / pin[ok]).sum(axis=1)
        (row[f"overround_{timing}_median"], row[f"overround_{timing}_p5"],
         row[f"overround_{timing}_p95"]) = _stats(over)
        avg, avg_ok = blocks[("avg", timing)]
        if avg is None:
            row[f"divergence_{timing}_median"] = row[f"divergence_{timing}_p95"] = np.nan
        else:
            both = ok & avg_ok
            div = pd.Series(np.abs(implied_probs(pin[both]).to_numpy()
                                    - implied_probs(avg[both]).to_numpy()).max(axis=1))
            row[f"divergence_{timing}_median"] = div.median() if len(div) else np.nan
            row[f"divergence_{timing}_p95"] = div.quantile(0.95) if len(div) else np.nan
        mx, mx_ok = blocks[("max", timing)]
        if mx is None:
            row[f"max_below_pin_{timing}"] = np.nan
        else:
            both = ok & mx_ok
            row[f"max_below_pin_{timing}"] = (
                (mx[both].to_numpy() < pin[both].to_numpy()).any(axis=1).mean()
                if both.any() else np.nan)
    pre, ok_pre = blocks[("pin", "pre")]
    cl, ok_cl = blocks[("pin", "close")]
    if pre is None or cl is None:
        row["stale_share"] = np.nan
    else:
        both = ok_pre & ok_cl
        row["stale_share"] = (
            (pre[both].to_numpy() == cl[both].to_numpy()).all(axis=1).mean()
            if both.any() else np.nan)
    return row


def monthly_diagnostics(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """One row per league x calendar month x market (market present in df)."""
    chk = cfg["pinnacle_checks"]
    d = df.copy()
    d["month"] = pd.to_datetime(d["date"]).dt.strftime("%Y-%m")
    rows = []
    for market, cols in MARKET_COLUMNS.items():
        if not any(c in d.columns for k in (("pin", "pre"), ("pin", "close")) for c in cols[k]):
            continue
        for (league, month), g in d.groupby(["league", "month"], sort=True):
            r = _group_row(g, market)
            r.update({"league": league, "month": month, "market": market})
            rows.append(r)
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=OUTPUT_COLUMNS)
    med = out.groupby(["league", "market"])["stale_share"].transform("median")
    lo, hi = chk["overround_range"]
    suspect, reasons = [], []
    for i, r in out.iterrows():
        why = []
        for t in ("pre", "close"):
            cov = r[f"pin_{t}_coverage"]
            if pd.notna(cov) and cov < chk["min_coverage"]:
                why.append(f"coverage_{t}")
            o = r[f"overround_{t}_median"]
            if pd.notna(o) and not (lo <= o <= hi):
                why.append(f"overround_{t}")
            dv = r[f"divergence_{t}_p95"]
            if pd.notna(dv) and dv > chk["divergence_p95_max"]:
                why.append(f"divergence_{t}")
        s = r["stale_share"]
        if (pd.notna(s) and s > chk["stale_share_min"]
                and s > chk["stale_share_multiple"] * med[i]):
            why.append("stale")
        suspect.append(bool(why))
        reasons.append(";".join(why))
    out["suspect"] = suspect
    out["suspect_reasons"] = reasons
    return out[OUTPUT_COLUMNS].reset_index(drop=True)


def first_suspect_month(diag: pd.DataFrame) -> dict:
    """league -> earliest 'YYYY-MM' with a suspect 1X2 row, else None."""
    one = diag[diag["market"] == "1x2"]
    result = {}
    for league in diag["league"].unique():
        m = one[(one["league"] == league) & (one["suspect"].astype(bool))]["month"]
        result[league] = min(m) if len(m) else None
    return result
