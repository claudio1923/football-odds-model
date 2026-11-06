import copy
import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from fbmodel.config import load_config
from fbmodel.data.clean import (
    assign_ref_source,
    build_matches,
    flag_quality,
    match_id,
    overround,
    parse_dates,
)
from fbmodel.data.columns import classify_column
from fbmodel.data.read_raw import read_raw_csv
from fbmodel.io_guard import sha256_file

ROOT = Path(__file__).resolve().parents[1]


def _yaml(name):
    with open(ROOT / "config" / name, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


# ---------------------------------------------------------------- parse_dates


def test_parse_dates_day_first_and_two_digit_year():
    s = pd.Series(["05/03/2024", "05/03/24", "31/12/2023"])
    out = parse_dates(s)
    assert list(out) == [
        pd.Timestamp("2024-03-05"),
        pd.Timestamp("2024-03-05"),
        pd.Timestamp("2023-12-31"),
    ]
    assert str(out.dtype).startswith("datetime64")


@pytest.mark.parametrize("bad", ["2024-03-05", "31/02/2024", "", np.nan])
def test_parse_dates_raises_on_unparsed(bad):
    s = pd.Series(["05/03/2024", bad])
    with pytest.raises(ValueError):
        parse_dates(s)


# ------------------------------------------------------------------ overround


def test_overround_value_and_invalid():
    df = pd.DataFrame(
        {
            "h": [2.0, np.nan, 2.0, 2.0],
            "d": [3.4, 3.4, 3.4, 3.4],
            "a": [4.0, 4.0, 0.0, -1.0],
        }
    )
    out = overround(df)
    assert out.iloc[0] == pytest.approx(1.0441176, abs=1e-6)
    assert out.iloc[1:].isna().all()


# ------------------------------------------------------------------- match_id


def test_match_id_deterministic_and_distinct():
    base = ("E0", pd.Timestamp("2024-03-05"), "Arsenal", "Chelsea")
    a = match_id(*base)
    assert isinstance(a, str)
    assert a == match_id(*base)
    assert a != match_id("E1", base[1], base[2], base[3])
    assert a != match_id(base[0], pd.Timestamp("2024-03-06"), base[2], base[3])
    assert a != match_id(base[0], base[1], "Chelsea", "Arsenal")
    assert a != match_id(base[0], base[1], base[2], "Everton")


def test_match_id_date_types_equivalent():
    a = match_id("E0", pd.Timestamp("2024-03-05"), "A", "B")
    b = match_id("E0", datetime.date(2024, 3, 5), "A", "B")
    c = match_id("E0", "2024-03-05", "A", "B")
    assert a == b == c


# ------------------------------------------------------------ assign_ref_source

RULE = {
    "cutoff_month": {"E0": "2026-01", "I2": "2025-10"},
    "pin_columns": ["a", "b", "c"],
    "min_valid_odds": 1.0,
}


def _ref_df(rows):
    out = []
    for league, date, susp, odds in rows:
        r = {"league": league, "date": pd.Timestamp(date), "suspect_month": susp}
        r.update(dict(zip(["a", "b", "c"], odds)))
        out.append(r)
    return pd.DataFrame(out)


GOOD = (2.0, 3.4, 4.0)


@pytest.mark.parametrize(
    "league,date,expected",
    [
        ("E0", "2025-12-31", "pin"),
        ("E0", "2026-01-01", "none"),
        ("E0", "2026-01-31", "none"),
        ("I2", "2025-09-30", "pin"),
        ("I2", "2025-10-01", "none"),
        ("ZZ", "2020-01-01", "none"),
    ],
)
def test_ref_source_cutoff_boundaries(league, date, expected):
    df = _ref_df([(league, date, False, GOOD)])
    assert assign_ref_source(df, RULE).iloc[0] == expected


def test_ref_source_suspect_month_none():
    df = _ref_df([("E0", "2025-01-10", True, GOOD)])
    assert assign_ref_source(df, RULE).iloc[0] == "none"


@pytest.mark.parametrize("bad", [np.nan, 1.0, 0.9])
def test_ref_source_invalid_odds_none(bad):
    df = _ref_df([("E0", "2025-01-10", False, (2.0, bad, 4.0))])
    assert assign_ref_source(df, RULE).iloc[0] == "none"


def test_ref_source_missing_column_all_none_and_index():
    df = _ref_df([("E0", "2025-01-10", False, GOOD), ("E0", "2025-01-11", False, GOOD)])
    df.index = [5, 9]
    out = assign_ref_source(df, RULE)
    assert list(out.index) == [5, 9]
    assert list(out) == ["pin", "pin"]
    out2 = assign_ref_source(df.drop(columns=["c"]), RULE)
    assert list(out2) == ["none", "none"]
    assert set(out) <= {"pin", "none"}


# --------------------------------------------------------------- flag_quality

QA_FLAGS = [
    "qa_exact_duplicate",
    "qa_duplicate_key",
    "qa_team_twice_same_date",
    "qa_result_goals_mismatch",
]


def _qa_row(league="E0", date="2024-03-05", home="A", away="B", hg=1, ag=0, res="H", season="2324"):
    return {
        "league": league, "season": season, "date": pd.Timestamp(date), "home": home,
        "away": away, "home_goals": hg, "away_goals": ag, "result": res,
    }


def test_flag_quality_clean_frame_and_untouched():
    df = pd.DataFrame(
        [
            _qa_row(home="A", away="B", hg=1, ag=0, res="H"),
            _qa_row(home="C", away="D", hg=1, ag=1, res="D"),
            _qa_row(home="E", away="F", hg=0, ag=2, res="A"),
            _qa_row(date="2024-03-06", home="A", away="C", hg=2, ag=1, res="H"),
        ],
        index=[10, 20, 30, 40],
    )
    orig = df.copy(deep=True)
    out = flag_quality(df)
    pd.testing.assert_frame_equal(df, orig)
    assert list(out.index) == [10, 20, 30, 40]
    pd.testing.assert_frame_equal(out[list(orig.columns)], orig)
    for f in QA_FLAGS:
        assert f in out.columns
        assert not out[f].any()


def test_flag_exact_duplicate():
    df = pd.DataFrame(
        [_qa_row(), _qa_row(), _qa_row(home="C", away="D", hg=0, ag=0, res="D")]
    )
    out = flag_quality(df)
    assert list(out["qa_exact_duplicate"]) == [True, True, False]
    assert list(out["qa_duplicate_key"]) == [True, True, False]
    assert len(out) == 3


def test_flag_duplicate_key_not_exact():
    df = pd.DataFrame(
        [
            _qa_row(hg=1, ag=0, res="H"),
            _qa_row(hg=2, ag=0, res="H"),
            _qa_row(home="C", away="D", hg=0, ag=0, res="D"),
        ]
    )
    out = flag_quality(df)
    assert list(out["qa_duplicate_key"]) == [True, True, False]
    assert list(out["qa_exact_duplicate"]) == [False, False, False]


def test_flag_team_twice_same_date():
    df = pd.DataFrame(
        [
            _qa_row(home="A", away="B", hg=1, ag=0, res="H"),
            _qa_row(home="C", away="A", hg=1, ag=1, res="D"),
            _qa_row(home="D", away="E", hg=0, ag=1, res="A"),
            _qa_row(league="I1", home="A", away="Z", hg=0, ag=0, res="D"),
        ]
    )
    out = flag_quality(df)
    assert list(out["qa_team_twice_same_date"]) == [True, True, False, False]
    assert list(out["qa_duplicate_key"]) == [False] * 4
    assert list(out["qa_exact_duplicate"]) == [False] * 4


def test_flag_result_goals_mismatch():
    df = pd.DataFrame(
        [
            _qa_row(home="A", away="B", hg=1, ag=0, res="H"),
            _qa_row(home="C", away="D", hg=0, ag=1, res="H"),
            _qa_row(home="E", away="F", hg=2, ag=2, res="A"),
            _qa_row(home="G", away="H", hg=np.nan, ag=np.nan, res="H"),
            _qa_row(home="I", away="J", hg=0, ag=3, res="A"),
        ]
    )
    out = flag_quality(df)
    assert list(out["qa_result_goals_mismatch"]) == [False, True, True, True, False]
    assert len(out) == 5


# ------------------------------------------------------------ config artefacts

RAW_NAMES = [
    "Div", "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR", "HTHG", "HTAG",
    "HTR", "B365H", "B365D", "B365A", "B365CH", "PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA",
    "MaxH", "MaxCH", "AvgH", "AvgCH", "B365>2.5", "B365<2.5", "P>2.5", "PC<2.5", "Max>2.5",
    "AvgC>2.5", "AHh", "AHCh", "B365AHH", "PAHH", "PCAHA", "MaxAHH", "AvgCAHA", "WHH",
    "WHCH", "BFECH", "Bb1X2",
]


@pytest.fixture(scope="module")
def column_map():
    return _yaml("column_map.yaml")


@pytest.fixture(scope="module")
def availability_yaml():
    return _yaml("column_availability.yaml")


def test_every_odds_column_mapped_or_dropped(column_map):
    mapped, dropped = column_map["map"], column_map["dropped"]
    for name in RAW_NAMES:
        fam = classify_column(name)["family"]
        if fam.startswith("odds_") or fam == "ah_line":
            assert (name in mapped) != (name in dropped), name
    assert not (set(mapped) & set(dropped))
    for name, reason in dropped.items():
        assert isinstance(reason, str) and reason.strip(), name


@pytest.mark.parametrize(
    "raw,canon",
    [
        ("PSH", "odds_1x2_pin_pre_h"),
        ("PSCH", "odds_1x2_pin_close_h"),
        ("AHh", "ah_line_pre"),
        ("AHCh", "ah_line_close"),
        ("P>2.5", "odds_ou25_pin_pre_over"),
        ("PCAHH", "odds_ah_pin_close_home"),
        ("MaxCH", "odds_1x2_max_close_h"),
        ("AvgC<2.5", "odds_ou25_avg_close_under"),
    ],
)
def test_specific_canonical_names(column_map, raw, canon):
    assert column_map["map"][raw] == canon


def test_pre_close_consistent_with_classifier(column_map):
    for raw, canon in column_map["map"].items():
        timing = classify_column(raw)["timing"]
        if "_pre_" in canon:
            assert timing == "pre", (raw, canon)
        if "_close_" in canon:
            assert timing == "close", (raw, canon)


def _synthetic_raw(league="E0", season="2122", start="2022-01-15", n=40, step=3):
    rng = np.random.default_rng(7)
    rows = []
    d0 = pd.Timestamp(start)
    for i in range(n):
        ph = rng.uniform(0.30, 0.55)
        pd_ = rng.uniform(0.20, 0.30)
        p = np.array([ph, pd_, 1 - ph - pd_])
        pre = 1.0 / (p * 1.04)
        close = 1.0 / ((p + np.array([0.005, -0.003, -0.002])) * 1.04)
        hg, ag = int(rng.integers(0, 4)), int(rng.integers(0, 4))
        res = "H" if hg > ag else ("A" if hg < ag else "D")
        r = {
            "Div": league,
            "Date": (d0 + pd.Timedelta(days=step * i)).strftime("%d/%m/%Y"),
            "Time": "15:00",
            "HomeTeam": f"T{i % 20}",
            "AwayTeam": f"T{(i + 7) % 20}",
            "FTHG": hg, "FTAG": ag, "FTR": res,
        }
        for pref, o in (("PS", pre), ("Avg", pre * 1.005), ("Max", pre * 1.02)):
            for k, v in zip("HDA", o):
                r[f"{pref}{k}"] = round(float(v), 4)
        for pref, o in (("PSC", close), ("AvgC", close * 1.005), ("MaxC", close * 1.02)):
            for k, v in zip("HDA", o):
                r[f"{pref}{k}"] = round(float(v), 4)
        rows.append(r)
    cols = [
        "Div", "Date", "Time", "HomeTeam", "AwayTeam", "FTHG", "FTAG", "FTR",
        "PSH", "PSD", "PSA", "PSCH", "PSCD", "PSCA", "AvgH", "AvgD", "AvgA",
        "AvgCH", "AvgCD", "AvgCA", "MaxH", "MaxD", "MaxA", "MaxCH", "MaxCD", "MaxCA",
    ]
    return pd.DataFrame(rows)[cols]


def _usa_raw(season, start):
    rng = np.random.default_rng(3)
    rows = []
    d0 = pd.Timestamp(start)
    for i in range(10):
        p = np.array([0.45, 0.27, 0.28])
        o = 1.0 / (p * 1.05)
        hg, ag = int(rng.integers(0, 4)), int(rng.integers(0, 4))
        res = "H" if hg > ag else ("A" if hg < ag else "D")
        rows.append(
            {
                "Country": "USA", "League": "MLS", "Season": season,
                "Date": (d0 + pd.Timedelta(days=4 * i)).strftime("%d/%m/%Y"),
                "Time": "20:00", "Home": f"U{i}", "Away": f"V{i}",
                "HG": hg, "AG": ag, "Res": res,
                "PSCH": round(float(o[0]), 4), "PSCD": round(float(o[1]), 4),
                "PSCA": round(float(o[2]), 4),
                "MaxCH": round(float(o[0]) * 1.02, 4), "MaxCD": round(float(o[1]) * 1.02, 4),
                "MaxCA": round(float(o[2]) * 1.02, 4),
                "AvgCH": round(float(o[0]), 4), "AvgCD": round(float(o[1]), 4),
                "AvgCA": round(float(o[2]), 4),
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def cfg():
    return load_config()


@pytest.fixture(scope="module")
def built(cfg):
    return build_matches({("E0", "2122"): _synthetic_raw()}, cfg)


def test_availability_covers_mapped_and_matches_columns(column_map, availability_yaml, built, cfg):
    matches, _ = built
    avail = column_map["availability"]
    fams = availability_yaml["families"]
    names = set(column_map["map"].values()) | set(matches.columns)
    for n in names:
        assert n in avail, n
        fam, timing = avail[n]["family"], avail[n]["timing"]
        assert fam in fams, (n, fam)
        assert timing in fams[fam], (n, fam, timing)


def test_feature_eligibility(column_map, availability_yaml, cfg):
    elig = cfg["feature_eligibility"]
    assert isinstance(elig, list) and len(elig) > 0
    avail = column_map["availability"]
    fams = availability_yaml["families"]
    for n in elig:
        assert n in avail, n
        fam, timing = avail[n]["family"], avail[n]["timing"]
        assert timing != "close", n
        assert fam not in ("result", "match_stats", "derived", "qa"), n
        assert fams[fam][timing]["use"] == "feature_ok", n


def test_reference_price_cutoffs():
    data = _yaml("reference_price.yaml")
    cm = {k: str(v) for k, v in data["cutoff_month"].items()}
    expected = {
        "E0": "2026-01", "I1": "2026-01", "SP1": "2026-01", "D1": "2026-01",
        "F1": "2026-01", "P1": "2026-01", "I2": "2025-10", "N1": "2025-10",
        "DNK": "2025-11", "SWE": "2025-08", "USA": "2025-08",
    }
    assert cm == expected


def test_team_aliases_empty():
    data = _yaml("team_aliases.yaml")
    assert "aliases" in data
    assert (data["aliases"] or {}) == {}


# --------------------------------------------------------------- build_matches


def test_build_matches_columns_and_basic(built):
    matches, excl = built
    for c in [
        "match_id", "league", "season", "season_note", "date", "kickoff", "home", "away",
        "stage", "home_goals", "away_goals", "result", "odds_1x2_pin_pre_h",
        "ref_source_1x2_pre", "ref_source_1x2_close", "ref_source_ou25_pre",
        "ref_source_ah_close", "qa_exact_duplicate", "qa_duplicate_key",
        "qa_team_twice_same_date", "qa_result_goals_mismatch", "qa_odds_out_of_range",
        "qa_overround_out_of_range",
    ]:
        assert c in matches.columns, c
    assert len(matches) == 40
    assert matches["match_id"].is_unique
    for r in matches.itertuples():
        assert r.match_id == match_id(r.league, r.date, r.home, r.away)
    assert matches["date"].is_monotonic_increasing
    for c in [c for c in matches.columns if c.startswith("ref_source_")]:
        assert set(matches[c]) <= {"pin", "none"}, c
    assert (matches["ref_source_ou25_pre"] == "none").all()
    assert (matches["ref_source_ah_close"] == "none").all()


def test_build_matches_pin_before_cutoff_and_none_after(cfg):
    m, _ = build_matches({("E0", "2122"): _synthetic_raw(start="2022-01-15")}, cfg)
    assert (m["ref_source_1x2_pre"] == "pin").all()
    m2, _ = build_matches(
        {("E0", "2526"): _synthetic_raw(season="2526", start="2026-02-03", n=12)}, cfg
    )
    assert (m2["ref_source_1x2_pre"] == "none").all()


def test_build_matches_odds_unaltered(built):
    matches, _ = built
    raw = _synthetic_raw()
    np.testing.assert_array_equal(matches["odds_1x2_pin_pre_h"].to_numpy(), raw["PSH"].to_numpy())
    np.testing.assert_array_equal(
        matches["odds_1x2_pin_close_a"].to_numpy(), raw["PSCA"].to_numpy()
    )


def test_build_matches_excludes_missing_results(cfg):
    raw = _synthetic_raw()
    raw.loc[[3, 7], ["FTR", "FTHG", "FTAG"]] = np.nan
    m, excl = build_matches({("E0", "2122"): raw}, cfg)
    assert len(m) == 38
    assert set(m["result"]) <= {"H", "D", "A"}
    for c in ["league", "season", "n_raw", "n_excluded_no_result", "n_kept"]:
        assert c in excl.columns
    row = excl[(excl["league"] == "E0") & (excl["season"] == "2122")].iloc[0]
    assert row["n_raw"] == 40
    assert row["n_excluded_no_result"] == 2
    assert row["n_kept"] == 38


def test_build_matches_result_goals_mismatch_kept(cfg):
    raw = _synthetic_raw()
    raw.loc[5, ["FTR", "FTHG", "FTAG"]] = ["H", 0, 1]
    m, _ = build_matches({("E0", "2122"): raw}, cfg)
    assert len(m) == 40
    d = pd.to_datetime(raw.loc[5, "Date"], dayfirst=True)
    target = m[m["date"] == d]
    assert len(target) == 1
    assert bool(target.iloc[0]["qa_result_goals_mismatch"]) is True
    assert int(m["qa_result_goals_mismatch"].sum()) == 1


def test_build_matches_odds_out_of_range_single_row(cfg):
    raw = _synthetic_raw()
    raw.loc[9, "PSH"] = 0.9
    m, _ = build_matches({("E0", "2122"): raw}, cfg)
    flagged = m[m["qa_odds_out_of_range"].astype(bool)]
    assert len(flagged) == 1
    assert flagged.iloc[0]["date"] == pd.to_datetime(raw.loc[9, "Date"], dayfirst=True)


def test_build_matches_bad_date_raises(cfg):
    raw = _synthetic_raw()
    raw.loc[2, "Date"] = "2022-01-15"
    with pytest.raises(ValueError):
        build_matches({("E0", "2122"): raw}, cfg)


def test_build_matches_idempotent_and_input_unchanged(cfg):
    frames = {("E0", "2122"): _synthetic_raw()}
    before = copy.deepcopy(frames)
    m1, e1 = build_matches(frames, cfg)
    m2, e2 = build_matches(frames, cfg)
    pd.testing.assert_frame_equal(m1, m2)
    pd.testing.assert_frame_equal(e1, e2)
    pd.testing.assert_frame_equal(frames[("E0", "2122")], before[("E0", "2122")])


def test_build_matches_extra_league_notes_and_no_pre(cfg):
    m20, _ = build_matches({("USA", "2020"): _usa_raw(2020, "2020-08-01")}, cfg)
    assert (m20["season_note"] == "no_crowd_2020").all()
    m19, _ = build_matches({("USA", "2019"): _usa_raw(2019, "2019-04-01")}, cfg)
    assert m19["season_note"].isna().all()
    for m in (m20, m19):
        for c in [c for c in m.columns if c.startswith("ref_source_") and c.endswith("_pre")]:
            assert (m[c] == "none").all(), c


def test_build_matches_from_csv_leaves_file_unchanged(tmp_path, cfg):
    p = tmp_path / "E0_2122.csv"
    _synthetic_raw().to_csv(p, index=False)
    before = sha256_file(p)
    df, _enc = read_raw_csv(p)
    m, _ = build_matches({("E0", "2122"): df}, cfg)
    assert len(m) == 40
    assert sha256_file(p) == before
