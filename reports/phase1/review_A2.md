# Independent re-review of Phase 1A (after the divergence fix)

Reviewer scope: read-only except this file. Snapshot 2026-11-06. Python run as
`PYTHONNOUSERSITE=1 conda run -n fbmodel python <script>`; throwaway scripts lived in the session scratchpad, not in the project.

## Verdict per check

| # | Check | Result |
|---|---|---|
| 1 | Divergence fix recomputed independently, non-null counts, tests test values | PASS (one test gap, minor) |
| 2 | First suspect months vs thresholds; USA 2017-2020 suspect count | PASS |
| 3 | No config-worthy literals in reliability.py / run_phase1a.py | PARTIAL (small list below) |
| 4 | pytest, manifest, raw read-only | PASS |
| 5 | Report consistency for USA 2017-2026 | PASS |
| 6 | Misleading content in reports | FAIL (medium: pooled tables hide the Pinnacle outage) |
| 7 | Banned-word grep | PASS (0 hits) |

## 1. Divergence fix

Own code (pandas, positional numpy arrays, percentile 95 of max abs difference between normalised Pinnacle and Avg implied probabilities, valid = all 3 present and > 1.0) on raw CSVs
(`data/raw/football-data/2026-11-06/`), 24 league-month-timing cells (E0, I1, D1 x 2022-03, 2023-08, 2024-01, 2025-10 x pre/close). All 24 equal `divergence_{pre,close}_p95` in
`reports/phase1/pinnacle_reliability.csv` to at least 6 decimals (e.g. E0 2025-10 close 0.025584 vs 0.02558438; D1 2025-10 close 0.02829 vs 0.02829018). The count of rows used by my
computation equals `pin_{t}_coverage * n_matches` in every cell (32, 20, 30, 29, 30, 36, 40, 20, 26, 27, 28, 18), so the non-null base is the same.
Extra probe: a 4-row frame with a non-contiguous index (7,3,9,1) and one Avg NaN in the middle: the function returned median 0.017249 and p95 0.035614, identical to my positional computation.
Tests (`tests/test_reliability.py`): they do test values (zero divergence when Avg == Pinnacle with `abs=1e-12`; single-match expected value computed independently; NaN when Avg columns absent; large divergence gives a suspect with reason `divergence`).
Gap (low): no regression test with a non-default index plus a partially invalid row, which is the situation that triggered the original label-alignment bug; the existing value test uses one row. Suggest adding my probe as a test.

## 2. Suspect months

USA 1X2 close, own computation from raw (played only, seasons 2017-2026, 98 months): suspect = coverage < 0.95 or median overround outside [1.00, 1.08] or divergence p95 > 0.05.
Suspect months 2017-2020: mine 0, report 0 (month-level values for all 36 months match; USA 2020-08 coverage 0.975 is above 0.95; 2020-07 overround 1.0489 is inside the range).
Total suspect months over all 98: mine 11, report 11, symmetric difference of the two month sets empty. The 11: 2025-08 (divergence 0.0550), 2025-11 (coverage 0.316), 2026-02..05, 2026-07..11 (coverage 0). USA 2026-06 has no rows (not a gap in the check).
First suspect month USA = 2025-08 (summary table agrees). Other leagues: main leagues 2026-01 (I2 and N1 2025-10), SWE 2025-08, DNK 2025-11, consistent with the suspect list in `pinnacle_reliability.md`.

## 3. Literals still in code

reliability.py and run_phase1a.py take min_valid_odds, quantiles, coverage, stale, overround range, divergence max, ah_sign_bins/min_rows, last_weeks, played codes, sources, result columns from config. Remaining:
- Config key `reliability_reference_source: avg` exists but is read nowhere (grep over src, scripts, tests); the comparison source "avg" is hardcoded in `MARKET_COLUMNS` use and in `_group_row`. (medium-low: a dead parameter)
- Output column names `*_p5` / `*_p95` and the "p95" divergence name are fixed strings while the quantiles come from config; changing `quantile_low/high` would make the labels lie. (low)
- `inventory_summary.md` text "Last 10 calendar weeks" is typed, while `inventory.last_weeks` is the parameter. (low)
- Source lists in `cov()` (`["pinnacle"]`, `["max","avg"]`, `["pinnacle","max","avg"]`), the weekly frequency `"W-SUN"`, column names `Date`, `Season`, `Home`, `Away`, number formats `{:.4f}`/`.2f`, month format `%Y-%m`, `"1x2"` in `first_suspect_month`/retention. These are structural or presentational; acceptable but not in config.
- Test file duplicates the thresholds in a local `CFG` dict instead of loading config (acceptable for unit tests).

## 4. Tests, manifest, raw

- `PYTHONNOUSERSITE=1 conda run -n fbmodel python -m pytest -q`: 199 passed.
- `scripts/run_phase1a.py 2026-11-06` ran once: no download (snapshot exists), `manifest OK`; md5 of all `reports/phase1/*.csv`, `inventory_summary.md`, `pinnacle_reliability.md` identical before and after the run (deterministic).
- Raw files carry the read-only attribute (`attrib` shows R, mode r--r--r--). `git ls-files data` lists only `.gitkeep` files; no data committed.

## 5. Report consistency (USA 2017-2026)

`inventory_summary.md` section (d): seasons 2017..2026 present (e.g. 2017: 391 played rows, 2020: 324, 2026 495 rows ending 2026-11-02); "Declared limit" section present and states closing-only, no CLV, for USA/DNK/SWE. Retention USA close: played 4583; (i) 3911, (ii) 4580, (iii) 4012, shares 0.8534 / 0.9993 / 0.8754 (shares equal count/4583; 4583 matches my filtered row count). pre rows empty for USA/DNK/SWE as stated. Summary months (98) = month rows in the csv = 98. No inconsistency found.

## 6. Misleading or weak points (ranked)

1. Medium. Pooled availability table (c) in `inventory_summary.md` shows Pinnacle coverage such as 0.90 (I1), 0.85 (I2), 0.91 (E0) pooled over seasons, with no sentence saying the missing share is a contiguous outage from 2025-10/2026-01 to the end of the data (coverage 0.000 in later months), not scattered gaps. The same holds for the per-season coverage table (2526 season only partly missing). A reader could take 0.90 as random missingness. The outage is visible only by reading the suspect list. Add an explicit "Pinnacle outage" note with the first month of zero coverage per league.
2. Medium. Retention scenario (ii) ("Pinnacle if reliable, else Avg") reports 0.9993-1.0000 kept. This is a different price source for the whole 2026 outage window (USA 2026-02 onward, all main leagues 2026-01 onward), so the share overstates usable Pinnacle data; the report text says what (ii) is but not that the substituted period is one block and that Avg is not the same price. Present (iii) as the Pinnacle-only figure and flag (ii) as mixed source.
3. Low-medium. `first_suspect_month` for USA (2025-08) and SWE (2025-08) is triggered by a divergence breach in a month with full coverage; USA 2025-09 and 2025-10 are then not suspect, so "before the first suspect month" is a conservative cut and not the outage start (outage starts 2025-11 USA, 2026-02 full). Worth one explanatory sentence.
4. Low. Divergence in main leagues is lower than USA/SWE and its p95 rises in 2025-10 (e.g. E0 close 0.0256, D1 0.0283, I1 0.0231) without breaching 0.05; early sign of the outage degrading the line. Informational.
5. Low. Dead config key and test gap (sections 1 and 3).

## 7. Banned-word grep

Case-insensitive search for every term in the commit-msg hook (and the hook file's own list) over all tracked and untracked non-ignored files (57 files, `git ls-files -co --exclude-standard`, excluding `data/`), over `data/manifest`, and over all commit messages and author fields (`git log`): 0 matching files, 0 matching commits. The only match in the working tree is the local exclude entry in `.git/info/exclude` for the local tool folder and rules file, which is outside the repository content. Authors are the single configured author.

## Summary

The divergence fix is correct and verified against raw data (24 cells, plus an index-misalignment probe). USA 2017-2020 has 0 suspect months, 11 suspect months overall, all matching my recomputation. 199 tests pass, manifest verifies, raw is read-only, outputs deterministic, no banned terms. Open: an unused config key, a missing regression test for index misalignment, and the pooled coverage/retention tables that hide the Pinnacle outage window.
