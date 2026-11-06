# Independent review of Phase 1B (cleaning)

Reviewer scripts live in the session scratchpad (v1.py to v6.py, run with `PYTHONNOUSERSITE=1 conda run -n fbmodel python <file>`). They read the raw CSVs directly with their own code (string dtype, own encoding fallback, own date parser) and do not import src/fbmodel.

## Verdict per check

| # | Check | Result |
|---|-------|--------|
| 1 | Re-run run_phase1b.py + pytest; outputs unchanged; manifest; raw hashes | PASS |
| 2 | Row counts league x season vs raw; no silent drop | PASS |
| 3 | pre/close mapping + value equality vs raw | PASS |
| 4 | feature_eligibility and availability tags | PASS (one minor inconsistency) |
| 5 | Recompute ref_source (6 columns, all rows) and sample_retention | PASS |
| 6 | USA stage rule | PASS for validated seasons; two weaknesses (2020, 2026) |
| 7 | Non-numeric tokens | PASS |
| 8 | QA flags | PASS |
| 9 | Hard-coded parameters | PASS with minor notes |
| 10 | Test coverage vs spec | PARTIAL (gaps listed) |
| 11 | Banned-word grep | PASS |
| 12 | Other | see findings |

## Checks with commands and evidence

1. `sha256sum` of matches.parquet and all reports/phase1/*.csv|md before and after `PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase1b.py`: identical (diff empty). The script printed manifest OK before and after, "idempotent in memory: OK", "identical to previous matches.parquet: OK", shape (20836, 98). SHA-256 of every file under data/raw before and after: identical. `python -m pytest -q`: 199 passed.
2. v1.py: for each of the 62 (league, season) groups in config, played rows (result in H/D/A) in the raw file equal rows in the parquet; total 20836 = 20836, 0 mismatching groups. No raw row inside the configured seasons has a missing/other result (0 exclusions, consistent with the script output). Note: the extra files hold seasons outside the config list (USA 2012-2016, SWE 2012-2020, DNK 2012/13-2020/21 and DNK 2026/2027 with 78 rows). These are not in the parquet by configuration, and nothing in the script counts or reports them as excluded (see finding L3).
3. v1.py: for every raw column that is in column_map `map`, every row of every league-season, the raw value (numeric parse for numeric columns, stripped string for text) equals the parquet value: 1,181,224 cell comparisons, 0 real differences (2 reported differences were artefacts of my own comparison: trailing blank in a referee name, NaN-vs-NaN). That covers Pinnacle, Avg, Max, Bet365, AH odds, O/U odds, AH lines, goals, stats. For every parquet column with an odds_ name: the tag in the name (`_pre_` / `_close_`) agrees with the availability timing. The notes.txt rule (extra C after bookmaker/Max/Avg = closing; Avg<2.5 / P>2.5 without C = pre; AHh = pre line, AHCh = closing line) matches the map (spot-read of all entries).
4. v2.py: every parquet column has an availability entry and vice versa. The 35 feature_eligibility columns all resolve to family/timing with available=pre_match and use=feature_ok; none contains "close", ref_, qa_, stage, and none is a result, match-stat, derived or qa column. Every other feature_ok-tagged column is covered except match_id and season_note (see L1).
5. v2.py: I rebuilt ref_source for 1x2, ou25, ah x pre, close from the rule text: cutoff month from config/reference_price.yaml, suspect league-months from reports/phase1/pinnacle_reliability.csv (market 1x2, suspect == True; 73 league-months), Pinnacle outcomes all present and > 1.0. Differences against the parquet: 0 in all six columns over all 20836 rows. Pin counts: 1x2 pre 12180, close 18050; ou25 pre 12106, close 12123; ah pre 12176, close 12185. No "pin" on or after the cutoff month, none in a suspect month, no "avg" value anywhere. Leagues without pre columns (USA, DNK, SWE) are "none" in pre columns. sample_retention.csv: all 122 rows (league x season x timing) match my counts of played/pin/none; the pre-timing played total is 20836.
6. v4.py, v5.py. For 2017-2019 and 2021-2025 I recomputed modal N (34), the flagged set (both teams' prior matches >= N) and the totals: playoff counts 17, 17, 13, 13, 13, 28, 29, 30, equal to the parquet; regular count equals teams x 34 / 2 each season (374, 391, 408, 459, 476, 493, 493, 510); in each season no regular-labelled match is dated on or after the first playoff match; all 2017-2025 team counts are at least N, so no team is short. These counts also match the real MLS postseason structure for those years (13 matches for the 14-team format, 17 for the 12-team format), which is independent supporting evidence. The validation (rows - playoff == teams x N / 2, unique mode, even product) is a strong total-count check; it cannot catch a swap of one regular for one playoff match, but by construction a regular match cannot have both teams already past N matches.
7. v6.py: scanning every mapped numeric column in every raw file, the only non-numeric tokens are "#" (N1 2223, B365CH, Utrecht-Feyenoord, 08/01/2023) and "x" (USA 2025, AvgCH, Atlanta Utd-New England, 12/04/2025). nonnumeric_values.csv lists exactly these two rows. In the parquet these two cells are NaN and all other cells are unchanged (check 3). They appear only in closing columns, so no ref_source is affected. Other conversions: zero odds are kept as 0.0 (12 cells, 4 matches in ou25 columns), not turned into NaN, and flagged.
8. v3.py: exact duplicates 0, duplicate key 0, team twice same date 0, result vs goals mismatch 0 (recomputed from home_goals/away_goals; no null goals), qa_odds_out_of_range 4 rows (E0 2021-12-19 Newcastle, F1 2025-04-19 Paris SG, D1 2025-05-10 Bayern Munich, SP1 2025-10-18 Barcelona; all zero O/U odds), qa_overround_out_of_range 1 row (SP1 2023-08-27 Valencia-Osasuna; flag computed with pin and b365, per market and timing, bounds 1.00 to 1.25): the recomputed boolean vectors equal the parquet columns for all rows.
9. Reading clean.py and run_phase1b.py: thresholds, sane bounds, near-duplicate ratio, loss share, stage leagues, notes are in config. Items still in code, see L2.
11. `git ls-files -co --exclude-standard | grep -v '^data/' | xargs grep -il -E '<terms from the commit-msg hook>'`: 0 files (of 136 tracked or untracked-not-ignored files; the rules file and the local tool folder are excluded from git and were not part of that grep by design). `git log` author and message bodies: 0 matches. Nothing under data/ is tracked (only three .gitkeep); matches.parquet is ignored.

## Findings, ranked

No high-severity defect found. The parquet, flags and reference sources reproduce exactly from raw.

### Medium
M1. USA 2020 stage: 2 playoff matches are labelled "regular" and 2 regular matches are labelled "unknown". In 2020 the unique-mode condition fails (modes 23 and 24; team counts range 19-29), so the code takes the smaller mode (23) as N and marks the matches where both teams have played at least 23 as "unknown". That set (17 rows) contains 2 real regular-season matches of 2020-11-08 (Los Angeles FC-Portland, Philadelphia-New England) and 15 matches dated 2020-11-20 or later. Two further matches on 2020-11-23 (Portland-FC Dallas, Minnesota-Colorado) are dated after a 12-day gap that follows the last regular day (the last regular day is 2020-11-08, then nothing until 2020-11-20) and are labelled "regular"; from the data they are post-regular-season (playoff) matches. Impact: a "regular" label on playoff matches is the unsafe direction; only the 2020 no-crowd season is affected and the numbers are tiny, but the spec says "unknown where not validated", and these 2 rows violate it. Suggested fix: in a non-validated season, label unknown every match dated after the last day with a full matchday or after the first gap larger than a configured number of days, or label the whole season after the rule's first flagged date as unknown; do not use a mode when it is not unique.

### Low
L1. column_availability tags match_id and season_note as feature_ok but they are not in feature_eligibility. Not a leak (neither is derived from post-match data; season_note is a static season label), only an inconsistency. Decide: add to the list or tag as not a feature.
L2. Remaining hard-coded literals in code: "99:99" sentinel for missing kickoff in the sort; the match_id hash prefix length 16 and the SHA-1 choice; `_DATE_FORMATS`; the numeric-column rule (`odds_`, `ah_line`, and goal names) in two places; SOURCES = ("pin", "b365", "max", "avg") and the set ("pin","b365") for the overround flag in run_phase1b.py and clean.py; the stage labels. Rule 4 targets parameters; most of these are structural, but the overround sources, the hash length and the date formats belong in config.
L3. The 2026 USA season (495 matches, in progress) is wholly "unknown". Every team has played exactly 33 matches and none has reached 34, so all 495 are certainly regular-season matches under the same rule; "unknown" is conservative (a loss of information, not a leak). SWE 2026 is treated as regular, which is consistent with a league without playoffs in the file. Also, rows in the extra-league files outside the configured seasons (see check 2; 78 DNK 2026/2027 rows, USA 2012-2016 and others) are neither in the parquet nor in any exclusion count: the exclusion table only counts rows without a result inside the configured seasons. Suggest adding "rows outside configured seasons" to quality_report.md.
L4. Tests (199 pass) do not cover: assign_stage (no test calls it; the USA validation logic, 2020 unique-mode failure, in-progress season, DNK unknown are untested directly; only an end-to-end check exists), nonnumeric_report (only 2 real tokens; no unit test that tokens become NaN and are listed), the monthly suspect-month plumbing from monthly_diagnostics into ref_source (only assign_ref_source with a handcrafted suspect_month), the final sort order with ties (date, kickoff, league, home) and match_id uniqueness on the real data, the odds==1.0 boundary for the odds flag, and the parquet round-trip (the script does it at run time). Also no test asserts that the committed config feature_eligibility has no `season_note`/`match_id`-style leakage beyond names containing close.
L5. In `flag_quality`, `mismatch.fillna(True)` marks a result-vs-goals mismatch when goals are missing; harmless here (no missing goals among played rows) but it would also flag a row for a different reason; document it.

### Informational
- Three zero-valued odds exist in Pinnacle O/U (and Bet365 O/U close) for 4 matches; they are kept, flagged (qa_odds_out_of_range) and invalidate the Pinnacle reference for that market because of the > 1.0 rule. Correct per spec.
- In the quality tables, odds exactly equal to 1.0: 0 cells; values below 1: 12, all the zeros above.
- The `ref_avg` column in sample_retention is always 0 by design.
- Parquet dtypes: odds and goals float64; text columns are pandas string dtype with NaN as missing (the script compares through a None-neutral view); `season_note` is string with missing for non-USA-2020 rows; QA flags are bool; kickoff is a string "HH:MM" or missing (not time-typed). No object None/NaN mixture was detected.

## Open items for the project owner
1. Decide the 2020 USA stage treatment (M1).
2. Decide whether USA 2026 (in progress) should be labelled "regular" where no team can have completed the schedule (L3).
3. Decide where to report rows outside the configured seasons (L3), and whether season_note/match_id belong in the eligible list (L1).
4. Add unit tests for assign_stage and nonnumeric_report (L4).
