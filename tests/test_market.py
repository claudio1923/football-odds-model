import itertools

import numpy as np
import pytest

from fbmodel.market import (
    devig_power,
    devig_proportional,
    expected_value,
    implied_probs,
    overround,
    settle_ah,
    settle_ou,
)

ODDS = np.array([2.00, 3.40, 4.00])


def f(x):
    return float(np.asarray(x))


def test_implied_probs_shapes():
    assert f(implied_probs(2.0)) == pytest.approx(0.5, abs=1e-12)
    np.testing.assert_allclose(implied_probs(ODDS), 1 / ODDS, atol=1e-12)
    two_d = np.array([[2.0, 3.4, 4.0], [1.5, 4.0, 7.0]])
    out = implied_probs(two_d)
    assert out.shape == two_d.shape
    np.testing.assert_allclose(out, 1 / two_d, atol=1e-12)


def test_overround():
    assert f(overround(ODDS)) == pytest.approx(1.0441176, abs=1e-6)
    two_d = np.array([[2.0, 3.4, 4.0], [2.0, 2.0, 1e9]])
    out = overround(two_d)
    assert out.shape == (2,)
    assert out[0] == pytest.approx(1.0441176, abs=1e-6)


def test_devig_proportional_hand_values():
    p = devig_proportional(ODDS)
    np.testing.assert_allclose(p, [0.478873, 0.281690, 0.239437], atol=1e-6)
    assert p.sum() == pytest.approx(1.0, abs=1e-12)


def test_devig_power_properties():
    p = devig_power(ODDS)
    assert p.sum() == pytest.approx(1.0, abs=1e-9)
    assert np.all(np.abs(p - devig_proportional(ODDS)) < 0.01)


def test_devig_power_two_outcomes_and_2d_rows_independent():
    two = devig_power(np.array([1.8, 2.1]))
    assert two.sum() == pytest.approx(1.0, abs=1e-9)
    assert two[0] > two[1]
    rows = np.array([[2.0, 3.4, 4.0], [1.4, 5.0, 9.0], [2.6, 3.1, 2.9]])
    out = devig_power(rows)
    assert out.shape == rows.shape
    np.testing.assert_allclose(out.sum(axis=1), 1.0, atol=1e-9)
    for i in range(3):
        np.testing.assert_allclose(out[i], devig_power(rows[i]), atol=1e-9)


def test_expected_value():
    assert f(expected_value(0.5, 2.10)) == pytest.approx(0.05, abs=1e-9)
    np.testing.assert_allclose(
        expected_value(np.array([0.5, 0.4]), np.array([2.1, 2.0])), [0.05, -0.2], atol=1e-9
    )


@pytest.mark.parametrize(
    "hg,ag,line,expected",
    [
        (1, 1, 0.0, 0.0),
        (1, 1, -0.5, -1.0),
        (1, 1, -0.25, -0.5),
        (2, 1, -0.25, 1.0),
        (2, 1, -0.75, 0.5),
        (3, 1, -0.75, 1.0),
        (1, 1, 0.25, 0.5),
        (2, 1, -1.0, 0.0),
    ],
)
def test_settle_ah_home_hand_values(hg, ag, line, expected):
    assert f(settle_ah(hg, ag, line, 2.0, "home")) == pytest.approx(expected, abs=1e-9)


def test_settle_ah_away_mirrors_home():
    lines = [-1.5, -1.25, -1, -0.75, -0.5, -0.25, 0, 0.25, 0.5, 0.75, 1, 1.25, 1.5]
    for h, a, line in itertools.product(range(6), range(6), lines):
        away = f(settle_ah(h, a, line, 1.9, "away"))
        mirror = f(settle_ah(a, h, -line, 1.9, "home"))
        assert away == pytest.approx(mirror, abs=1e-9), (h, a, line)


@pytest.mark.parametrize(
    "goals,line,side,expected",
    [
        (3, 2.5, "over", 1.0),
        (2, 2.25, "over", -0.5),
        (3, 2.75, "over", 0.5),
        (3, 3.0, "under", 0.0),
    ],
)
def test_settle_ou_hand_values(goals, line, side, expected):
    assert f(settle_ou(goals, line, 2.0, side)) == pytest.approx(expected, abs=1e-9)


def test_settle_ou_half_line_exactly_one_wins():
    o_over, o_under = 1.9, 2.1
    for g in range(0, 8):
        po = f(settle_ou(g, 2.5, o_over, "over"))
        pu = f(settle_ou(g, 2.5, o_under, "under"))
        if g >= 3:
            assert po == pytest.approx(o_over - 1, abs=1e-9)
            assert pu == pytest.approx(-1.0, abs=1e-9)
        else:
            assert po == pytest.approx(-1.0, abs=1e-9)
            assert pu == pytest.approx(o_under - 1, abs=1e-9)


def test_settle_ou_vectorised_equals_scalar():
    goals = np.arange(0, 8)
    for line in (2.0, 2.25, 2.5, 2.75):
        for side in ("over", "under"):
            vec = np.asarray(settle_ou(goals, line, 1.95, side))
            sca = [f(settle_ou(int(g), line, 1.95, side)) for g in goals]
            np.testing.assert_allclose(vec, sca, atol=1e-12)


def test_settle_ah_vectorised_equals_scalar():
    hg = np.array([0, 1, 2, 3, 1, 0])
    ag = np.array([0, 1, 0, 1, 3, 2])
    for line in (-0.75, -0.25, 0.0, 0.5):
        for side in ("home", "away"):
            vec = np.asarray(settle_ah(hg, ag, line, 1.9, side))
            sca = [f(settle_ah(int(h), int(a), line, 1.9, side)) for h, a in zip(hg, ag)]
            np.testing.assert_allclose(vec, sca, atol=1e-12)
