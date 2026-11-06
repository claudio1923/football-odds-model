"""Classify football-data.co.uk columns. Rules come from the site's notes.txt:
odds columns are pre-closing odds; the closing version has an extra 'C' after the
bookmaker abbreviation / Max / Avg."""
import re

ID_COLS = {"Div", "Date", "Time", "HomeTeam", "AwayTeam", "Country", "League",
           "Season", "Home", "Away"}
RESULT_COLS = {"FTHG", "HG", "FTAG", "AG", "FTR", "Res", "HTHG", "HTAG", "HTR"}
STATS_COLS = {"Attendance", "Referee", "HS", "AS", "HST", "AST", "HHW", "AHW", "HC", "AC",
              "HF", "AF", "HFKC", "AFKC", "HO", "AO", "HY", "AY", "HR", "AR", "HBP", "ABP"}
OTHER_COLS = {"Bb1X2", "BbOU", "BbAH"}

# bookmaker abbreviations from notes.txt (1X2 block, plus Max/Avg/Betbrain aggregates)
_BK_1X2 = ["1XB", "B365", "BFD", "BFE", "BF", "BMGM", "BV", "BS", "BW", "CL", "GB", "IW",
           "LB", "PP", "PS", "P", "SK", "SO", "SB", "SJ", "SY", "VC", "WH",
           "Max", "Avg", "BbMx", "BbAv"]
_BK_OU = ["B365", "GB", "P", "Max", "Avg", "BFE", "BbMx", "BbAv"]
_BK_AH = ["B365", "GB", "LB", "P", "Max", "Avg", "BFE", "BbMx", "BbAv"]
_BK_LINE = ["B365", "GB", "LB"]

_SOURCE = {"PS": "pinnacle", "P": "pinnacle", "B365": "bet365", "Max": "max", "Avg": "avg"}


def _alt(items):
    return "|".join(sorted(map(re.escape, items), key=len, reverse=True))


_RE_1X2 = re.compile(rf"^(?P<bk>{_alt(_BK_1X2)})(?P<c>C?)(?P<side>[HDA])$")
_RE_OU = re.compile(rf"^(?P<bk>{_alt(_BK_OU)})(?P<c>C?)(?P<dir>[<>])2\.5$")
_RE_AH = re.compile(rf"^(?P<bk>{_alt(_BK_AH)})(?P<c>C?)AH(?P<side>[HA])$")
_RE_LINE = re.compile(rf"^(?P<bk>{_alt(_BK_LINE)})(?P<c>C?)AH$")


def _res(family, market=None, source=None, timing="none", side=None) -> dict:
    return {"family": family, "market": market, "source": source,
            "timing": timing, "side": side}


def classify_column(name: str) -> dict:
    name = "" if name is None else str(name)
    if name in ID_COLS:
        return _res("id")
    if name in RESULT_COLS:
        return _res("result")
    if name in STATS_COLS:
        return _res("match_stats")
    if name in OTHER_COLS:
        return _res("other")
    if name == "AHh":
        return _res("ah_line", "ah", "market", "pre")
    if name == "AHCh":
        return _res("ah_line", "ah", "market", "close")
    if name == "BbAHh":
        return _res("ah_line", "ah", "other", "pre")
    m = _RE_1X2.match(name)
    if m:
        return _res("odds_1x2", "1x2", _SOURCE.get(m["bk"], "other"),
                    "close" if m["c"] else "pre", m["side"])
    m = _RE_OU.match(name)
    if m:
        return _res("odds_ou", "ou25", _SOURCE.get(m["bk"], "other"),
                    "close" if m["c"] else "pre", "over" if m["dir"] == ">" else "under")
    m = _RE_AH.match(name)
    if m:
        return _res("odds_ah", "ah", _SOURCE.get(m["bk"], "other"),
                    "close" if m["c"] else "pre", "home" if m["side"] == "H" else "away")
    m = _RE_LINE.match(name)
    if m:
        return _res("ah_line", "ah", _SOURCE.get(m["bk"], "other"),
                    "close" if m["c"] else "pre")
    return _res("unclassified")
