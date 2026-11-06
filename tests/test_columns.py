import pytest

from fbmodel.data.columns import classify_column


def _check(name, family, market=None, source=None, timing="none", side=None):
    r = classify_column(name)
    assert r["family"] == family, name
    assert r["market"] == market, name
    assert r["source"] == source, name
    assert r["timing"] == timing, name
    assert r["side"] == side, name


@pytest.mark.parametrize(
    "name",
    ["Div", "Date", "Time", "HomeTeam", "AwayTeam", "Country", "League", "Season", "Home", "Away"],
)
def test_id(name):
    _check(name, "id")


@pytest.mark.parametrize(
    "name", ["FTHG", "HG", "FTAG", "AG", "FTR", "Res", "HTHG", "HTAG", "HTR"]
)
def test_result(name):
    _check(name, "result")


@pytest.mark.parametrize(
    "name",
    ["Attendance", "Referee", "HS", "AS", "HST", "AST", "HHW", "AHW", "HC", "AC", "HF", "AF",
     "HFKC", "AFKC", "HO", "AO", "HY", "AY", "HR", "AR", "HBP", "ABP"],
)
def test_match_stats(name):
    _check(name, "match_stats")


@pytest.mark.parametrize(
    "name,source,timing,side",
    [
        ("B365H", "bet365", "pre", "H"),
        ("B365CD", "bet365", "close", "D"),
        ("PSH", "pinnacle", "pre", "H"),
        ("PSCH", "pinnacle", "close", "H"),
        ("PSA", "pinnacle", "pre", "A"),
        ("PSCA", "pinnacle", "close", "A"),
        ("PH", "pinnacle", "pre", "H"),
        ("MaxH", "max", "pre", "H"),
        ("MaxCH", "max", "close", "H"),
        ("MaxCA", "max", "close", "A"),
        ("AvgD", "avg", "pre", "D"),
        ("AvgCD", "avg", "close", "D"),
        ("WHH", "other", "pre", "H"),
        ("WHCH", "other", "close", "H"),
        ("BFECH", "other", "close", "H"),
        ("BFDH", "other", "pre", "H"),
        ("BFDCA", "other", "close", "A"),
    ],
)
def test_odds_1x2(name, source, timing, side):
    _check(name, "odds_1x2", "1x2", source, timing, side)


@pytest.mark.parametrize(
    "name,source,timing,side",
    [
        ("B365>2.5", "bet365", "pre", "over"),
        ("B365<2.5", "bet365", "pre", "under"),
        ("B365C>2.5", "bet365", "close", "over"),
        ("P>2.5", "pinnacle", "pre", "over"),
        ("P<2.5", "pinnacle", "pre", "under"),
        ("PC>2.5", "pinnacle", "close", "over"),
        ("PC<2.5", "pinnacle", "close", "under"),
        ("Max>2.5", "max", "pre", "over"),
        ("MaxC<2.5", "max", "close", "under"),
        ("Avg>2.5", "avg", "pre", "over"),
        ("AvgC>2.5", "avg", "close", "over"),
        ("AvgC<2.5", "avg", "close", "under"),
        ("BFE>2.5", "other", "pre", "over"),
        ("BFEC<2.5", "other", "close", "under"),
        ("GB>2.5", "other", "pre", "over"),
    ],
)
def test_odds_ou(name, source, timing, side):
    _check(name, "odds_ou", "ou25", source, timing, side)


@pytest.mark.parametrize(
    "name,source,timing,side",
    [
        ("B365AHH", "bet365", "pre", "home"),
        ("B365AHA", "bet365", "pre", "away"),
        ("B365CAHH", "bet365", "close", "home"),
        ("PAHH", "pinnacle", "pre", "home"),
        ("PAHA", "pinnacle", "pre", "away"),
        ("PCAHH", "pinnacle", "close", "home"),
        ("PCAHA", "pinnacle", "close", "away"),
        ("MaxAHH", "max", "pre", "home"),
        ("MaxCAHA", "max", "close", "away"),
        ("AvgAHA", "avg", "pre", "away"),
        ("AvgCAHH", "avg", "close", "home"),
        ("BFEAHH", "other", "pre", "home"),
        ("BFECAHA", "other", "close", "away"),
    ],
)
def test_odds_ah(name, source, timing, side):
    _check(name, "odds_ah", "ah", source, timing, side)


@pytest.mark.parametrize(
    "name,source,timing",
    [
        ("AHh", "market", "pre"),
        ("AHCh", "market", "close"),
        ("B365AH", "bet365", "pre"),
        ("B365CAH", "bet365", "close"),
    ],
)
def test_ah_line(name, source, timing):
    _check(name, "ah_line", "ah", source, timing, None)


@pytest.mark.parametrize("name", ["Bb1X2", "BbOU", "BbAH"])
def test_other(name):
    _check(name, "other")


@pytest.mark.parametrize("name", ["FooBar", "", "Unnamed: 31", "XYZH"])
def test_unclassified(name):
    _check(name, "unclassified")


@pytest.mark.parametrize(
    "pre,close",
    [
        ("PSH", "PSCH"),
        ("Avg>2.5", "AvgC>2.5"),
        ("AHh", "AHCh"),
        ("PAHH", "PCAHH"),
        ("MaxH", "MaxCH"),
    ],
)
def test_pre_and_close_never_confused(pre, close):
    a, b = classify_column(pre), classify_column(close)
    assert a["timing"] == "pre"
    assert b["timing"] == "close"
    assert a["family"] == b["family"]
    assert a["source"] == b["source"]
    assert a["side"] == b["side"]
