"""Market maths: implied probabilities, de-vigging, expected value, bet settlement.

Pure, vectorised numpy. Odds arrays carry the outcomes on the LAST axis.
"""
import numpy as np

# Bisection depth for devig_power: 200 halvings of the bracket reach machine precision;
# an algorithmic constant, not a tunable parameter.
_BISECTION_STEPS = 200


def implied_probs(odds):
    """1 / odds."""
    return 1.0 / np.asarray(odds, dtype=float)


def overround(odds):
    """Sum of 1/odds over the last axis."""
    return implied_probs(odds).sum(axis=-1)


def devig_proportional(odds):
    """(1/odds) / row sum."""
    p = implied_probs(odds)
    return p / p.sum(axis=-1, keepdims=True)


def devig_power(odds):
    """p_i = (1/o_i)^k with k solved per row so that sum p_i = 1 (bisection)."""
    p = implied_probs(odds)
    lo = np.zeros(p.shape[:-1] + (1,))
    hi = np.full(p.shape[:-1] + (1,), 64.0)
    for _ in range(_BISECTION_STEPS):
        mid = 0.5 * (lo + hi)
        s = (p ** mid).sum(axis=-1, keepdims=True)
        too_big = s > 1.0          # sum decreases in k: need a larger k
        lo = np.where(too_big, mid, lo)
        hi = np.where(too_big, hi, mid)
    return p ** (0.5 * (lo + hi))


def expected_value(p, odds):
    """p * odds - 1."""
    return np.asarray(p, dtype=float) * np.asarray(odds, dtype=float) - 1.0


def half_lines(line):
    """The two (equal-weight) lines a stake is split on; identical for non-quarter lines."""
    line = np.asarray(line, dtype=float)
    q = np.round(line * 4.0) % 2 != 0
    return np.where(q, line - 0.25, line), np.where(q, line + 0.25, line)


def _unit(margin, odds):
    """Profit of one whole stake given margin (>0 win, 0 push, <0 lose)."""
    return np.where(margin > 0, odds - 1.0, np.where(margin < 0, -1.0, 0.0))


def settle_ah(home_goals, away_goals, line, odds, side):
    """Profit per 1 unit staked. line = HOME handicap (negative = home favourite)."""
    hg = np.asarray(home_goals, dtype=float)
    ag = np.asarray(away_goals, dtype=float)
    odds = np.asarray(odds, dtype=float)
    l1, l2 = half_lines(line)
    if side == "home":
        m1, m2 = hg - ag + l1, hg - ag + l2
    elif side == "away":
        m1, m2 = ag - hg - l1, ag - hg - l2
    else:
        raise ValueError("side must be 'home' or 'away'")
    return 0.5 * (_unit(m1, odds) + _unit(m2, odds))


def settle_ou(total_goals, line, odds, side):
    """Profit per 1 unit staked on over/under; quarter lines split into two halves."""
    tg = np.asarray(total_goals, dtype=float)
    odds = np.asarray(odds, dtype=float)
    l1, l2 = half_lines(line)
    if side == "over":
        m1, m2 = tg - l1, tg - l2
    elif side == "under":
        m1, m2 = l1 - tg, l2 - tg
    else:
        raise ValueError("side must be 'over' or 'under'")
    return 0.5 * (_unit(m1, odds) + _unit(m2, odds))
