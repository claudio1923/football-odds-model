"""Forecast-quality metrics, calibration, paired bootstrap and blend weights.

Class index convention for 1X2: 0 = home, 1 = draw, 2 = away.
"""
import numpy as np
import pandas as pd

_CHUNK = 250  # resamples per vectorised chunk (memory only; does not change results)


def _onehot(y, k):
    y = np.asarray(y, dtype=int)
    out = np.zeros((len(y), k))
    out[np.arange(len(y)), y] = 1.0
    return out


def log_loss_rows(p, y):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=int)
    return -np.log(p[np.arange(len(y)), y])


def brier_rows(p, y):
    p = np.asarray(p, dtype=float)
    return ((p - _onehot(y, p.shape[1])) ** 2).sum(axis=1)


def brier_binary_rows(p, o):
    return (np.asarray(p, dtype=float) - np.asarray(o, dtype=float)) ** 2


def rps_rows(p, y):
    p = np.asarray(p, dtype=float)
    k = p.shape[1]
    diff = np.cumsum(p, axis=1)[:, :-1] - np.cumsum(_onehot(y, k), axis=1)[:, :-1]
    return (diff ** 2).sum(axis=1) / (k - 1)


def calibration_table(p, o, n_bins):
    p = np.asarray(p, dtype=float)
    o = np.asarray(o, dtype=float)
    b = np.minimum((p * n_bins).astype(int), n_bins - 1)
    rows = []
    for i in range(n_bins):
        m = b == i
        if m.any():
            rows.append([i, i / n_bins, (i + 1) / n_bins, int(m.sum()), p[m].mean(), o[m].mean()])
    return pd.DataFrame(rows, columns=["bin", "lower", "upper", "n", "mean_p", "mean_o"])


def expected_calibration_error(p, o, n_bins):
    t = calibration_table(p, o, n_bins)
    return float((t["n"] / t["n"].sum() * (t["mean_o"] - t["mean_p"]).abs()).sum())


def _boot_means(x, n_boot, seed):
    """Means of n_boot resamples (with replacement), chunked."""
    rng = np.random.default_rng(seed)
    n = len(x)
    out = np.empty(n_boot)
    for s in range(0, n_boot, _CHUNK):
        e = min(s + _CHUNK, n_boot)
        idx = rng.integers(0, n, size=(e - s, n))
        out[s:e] = x[idx].mean(axis=1)
    return out


def _ci(means, ci_level):
    a = (1.0 - ci_level) / 2.0
    return float(np.quantile(means, a)), float(np.quantile(means, 1.0 - a))


def paired_bootstrap_diff(a, b, n_boot, seed, ci_level):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b
    lo, hi = _ci(_boot_means(d, n_boot, seed), ci_level)
    return {"mean_diff": float(a.mean() - b.mean()), "ci_low": lo, "ci_high": hi, "n": int(len(d))}


def bootstrap_mean_ci(x, n_boot, seed, ci_level):
    x = np.asarray(x, dtype=float)
    lo, hi = _ci(_boot_means(x, n_boot, seed), ci_level)
    return {"mean": float(x.mean()), "ci_low": lo, "ci_high": hi, "n": int(len(x))}


def estimate_blend_weight(p_model, p_bench, y, grid):
    pm, pb = np.asarray(p_model, dtype=float), np.asarray(p_bench, dtype=float)
    best_w, best = None, np.inf
    for w in np.asarray(grid, dtype=float):
        p = w * pm + (1.0 - w) * pb
        p = p / p.sum(axis=1, keepdims=True)
        ll = log_loss_rows(p, y).mean()
        if ll < best:
            best, best_w = ll, float(w)
    return best_w


def season_blend_weights(df, grid):
    """Weight per league x season from ALL EARLIER seasons of that league only."""
    rows = []
    for league, g in df.groupby("league", sort=True):
        order = g.groupby("season")["date"].min().sort_values(kind="mergesort").index.tolist()
        for i, season in enumerate(order):
            if i == 0:
                rows.append([league, season, np.nan, 0])
                continue
            prev = g[g["season"].isin(order[:i])]
            w = estimate_blend_weight(prev[["m_h", "m_d", "m_a"]].to_numpy(),
                                      prev[["b_h", "b_d", "b_a"]].to_numpy(),
                                      prev["y"].to_numpy(), grid)
            rows.append([league, season, w, len(prev)])
    return pd.DataFrame(rows, columns=["league", "season", "w", "n_fit"])
