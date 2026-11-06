# Independent review of Phase 1A

Reviewer scope: read-only except this file. Python run as `PYTHONNOUSERSITE=1 conda run -n fbmodel python ...` from the project directory. The project rules file is referred to as `[FORBIDDEN-TERM].md` here, because its file name contains a banned word.

## Verdict

Phase 1A is mostly sound, but it has one real bug: **the divergence diagnostic is NaN for every league-month, market and timing.** The `divergence_p95_max` threshold therefore never fires. Everything else I re-derived independently agrees with the reports.

## Findings ranked by severity

### HIGH-1. Divergence vs Avg is never computed (silent no-op check)

- **Where:** `src/fbmodel/data/reliability.py`, `_group_row`.
  - The line is `(implied_probs(pin[both]) - implied_probs(avg[both])).abs().max(axis=1)`.
  - The two frames have different column labels (`PSH/PSD/PSA` vs `AvgH/AvgD/AvgA`).
  - pandas aligns on labels, so the difference is all-NaN.
- **Evidence from the reports:**
  - In `reports/phase1/pinnacle_reliability.csv` (1362 rows), `divergence_pre_median`, `divergence_pre_p95`, `divergence_close_median` and `divergence_close_p95` have 0 non-null values.
  - `max_below_pin_*` is populated (1098 and 1234 non-null), because it uses `.to_numpy()`.
- **Minimal reproduction:** `implied_probs(PS-frame) - implied_probs(Avg-frame)` gives NaN. The same calculation on `.to_numpy()` gives 0.0192.
- **Consequences:**
  - The suspect flag, `first_suspect_month` and the retention table (i)/(ii)/(iii) use only coverage, overround and stale. The fourth configured criterion is inactive.
  - The reports are silent about this: `pinnacle_reliability.md` lists the threshold in its header but never shows any divergence value.
  - Overround never triggered either (0 months flagged), so in practice only coverage and stale drive the results.
  - Retention numbers might change after the fix. I did not test this.
- **Tests:** `tests/test_reliability.py` only checks that the divergence columns exist. It never checks a value.
- **Fix:** use `.to_numpy()` or rename the columns before subtracting. Add a test with a known divergence, and one where divergence alone flags a month.

### MEDIUM-1. Pinnacle disappears from 2026-02 in all 8 main leagues

- **What the data shows:**
  - The raw files contain no valid Pinnacle 1X2 odds from 2026-02 to 2026-05, for pre and close alike. Coverage is 0.0.
  - 2026-01 is partial: 0.49 for E0, 0.59 for I1, and 0.31 for D1 ou25.
  - Example, E0: 2025-12 coverage is 1.0, 2026-01 is 0.4898, 2026-02 to 2026-05 are 0.
  - I2 and N1 become suspect earlier (2025-10 and 2025-11 onward), via coverage and stale.
- **Misleading summaries:**
  - The per-league availability table (c) pools seasons and shows "pinnacle:0.90". That hides a structural, permanent loss in the most recent months.
  - The reports do not state that the 2025/26 tail has zero Pinnacle.
- **Retention (ii) rescues the loss with Avg.** Its numbers (about 0.999 to 1.0) therefore reflect Avg availability, not Pinnacle.
- **Retention (i)/(iii):** shares are 0.83 to 0.90, which is the 2026 outage.
- **Recommendation:** state this explicitly in the Phase 1A diary and report, and check whether `PSH`, `PSCH` and the like come back empty or are absent.

### MEDIUM-2. Extra leagues (USA, DNK, SWE) have closing columns only

- **What the files contain:** they only contain `PSC*`, `MaxC*`, `AvgC*`, `BFEC*` and `B365C*`, with no pre-closing odds, no Over/Under and no Asian handicap.
- **Consequences:**
  - There are no model-feature-eligible odds for these leagues, because closing odds are evaluation-only (rule 1).
  - Retention for "pre" is empty. The report mentions this but does not draw the conclusion.
  - Pinnacle close coverage is 0.83 (USA), 0.88 (DNK) and 0.84 (SWE).
- **Decision for the user:** this is a design matter, not a bug.

### MEDIUM-3. Silent exclusion of rows outside configured seasons

- **What is dropped:**
  - Extra-league files are filtered to config seasons by `load_all`.
  - Dropped rows: USA/SWE 2012-2020, DNK 2012/13-2020/21, and DNK 2026/2027 (78 rows). USA had 6311 rows in total and SWE 3600; DNK had 3030 rows in total.
  - This matches the spec, but no count of excluded rows is written anywhere in the reports.
- **Recommendation:** add an "excluded by season filter" row count to the inventory.

### LOW-1. Magic numbers in code that belong in config (rule 4)

- `reliability.py`: quantiles 0.05 and 0.95, validity threshold `> 1.0`, and the `overround_range` bounds (those are in config, good).
- `scripts/run_phase1a.py`:
  - `.tail(10)` for the last 10 weeks
  - the hard-coded `["USA","SWE"]` and `"2026"` for the in-progress league list
  - the weekday rule `W-SUN`
  - the `SOURCES` list
  - `RESULT_COL` and `OUTCOMES`
  - the played-result codes `H`/`D`/`A`
  - the `Time`-column check
  - the 2-decimals / 4-decimals report formats
- `columns.py` holds the bookmaker lists; this is acceptable as a domain mapping, but it is not in config.
- `config.yaml` has `played_only: true`, but I did not see the code read it.

### LOW-2. Minor notes

- `git ls-files data` lists 3 tracked `.gitkeep` placeholder files (`data/interim/.gitkeep`, `data/processed/.gitkeep`, `data/raw/.gitkeep`), which pre-date Phase 1A. No data content is tracked. This is compatible with rule 7 if the rule is read as "no data content".
- Dates are parsed with two fixed formats (`%d/%m/%Y`, then `%d/%m/%y`). 0 unparsed dates across all 55 league-seasons.
- `stale_share` flags a month only if it exceeds both `stale_share_min` and `3 x median` across that league's months (any market). It never fired for `ou25`/`ah` data in a way I examined, and the I2 2025-10 and N1 2025-10 hits are plausible.
- The per-league summary table counts months, including months with zero Pinnacle coverage.
- The report header says "A month is suspect if any threshold is breached for a timing present in the file". This is accurate for coverage, but for divergence it is misleading until HIGH-1 is fixed.

## Checks performed

| # | Check | Command or method | Result |
|---|---|---|---|
| 1a | Tests | `PYTHONNOUSERSITE=1 conda run -n fbmodel python -m pytest -q` | PASS: 146 passed |
| 1b | Re-run script (snapshot exists, no download) | `... python scripts/run_phase1a.py 2026-11-06`; then `diff -r` of reports/phase1 against a copy made before the run | PASS: reports identical, manifest and log byte-identical, prints "manifest OK" |
| 2a | `verify_raw_manifest` | run inside the script (before and after) | PASS |
| 2b | Raw read-only | `ls -l` mode of all 44 files in `data/raw/football-data/2026-11-06` | PASS: all `-r--r--r--`, none writable |
| 2c | File count vs manifest vs log | 43 csv + `notes.txt` = 44 files; 44 manifest lines; 44 log rows (HTTP 200) + header | PASS |
| 2d | Manifest and log outside raw | paths are `data/manifest/MANIFEST.sha256` and `data/manifest/download_log.csv` | PASS |
| 2e | Nothing under data/ tracked, git status | `git ls-files data`; `git status --short` | PASS with note: only 3 `.gitkeep` tracked. `reports/phase1/`, `scripts/`, `src/fbmodel/data/` and the new tests are untracked (uncommitted). `diary.md`, `config/config.yaml`, `io_guard.py` and `tests/test_io_guard.py` are modified |
| 3a | Row counts per league x season | own pandas (`encoding utf-8-sig`, dropna all-empty rows) over all 43 CSVs vs the (a) table | PASS: all 55 league-seasons match. Main: 380 for I1/I2/E0/SP1 and F1 2122-2223; 306 for D1/N1/P1 and F1 2324-2526. USA 472/489/521/522/540/495; SWE 242/242/240/242/240/216; DNK 193/193/193/192/192 |
| 3b | Pinnacle coverage, 3 league-months | own pandas from raw: E0 2024-03, I2 2025-10, N1 2023-09 (plus E0 2026-01) | PASS: n_matches, pre/close coverage, stale_share and overround median equal the report to full precision. E.g. I2 2025-10: n=43, coverage 0.7907, stale 0.2941, overround 1.0498 |
| 3c | Retention, 2 leagues | own pandas for E0 and N1 (i)/(ii)/(iii), pre and close | PASS: E0 1706 / 1900 / 1706; N1 1287 / 1530 / 1314 (pre and close), as in `pinnacle_retention.csv` |
| 3d | stale_share and overround definitions | read `reliability.py` | PASS. stale_share is the share of valid-pre-and-valid-close rows with all outcomes identical (`==`). Overround is `sum(1/odds)` over valid rows; the monthly median is checked against the config range. Suspect criteria match the config thresholds (stale: `>stale_share_min` and `>multiple x league-market median`) |
| 3e | Divergence definition | read plus numeric reproduction | FAIL: see HIGH-1 |
| 3f | classify_column over all distinct raw column names | own script over every column in the 43 files (about 170 distinct names) | PASS: 0 unclassified, no misclassification found. All `...C?` names map to timing close, others to pre. Aggregate `Max`/`Avg`/`PS`/`P` map to the proper source. `BFD*` (Betfred) vs `BF*` (Betfair) vs `BFE*` (Betfair exchange) split correctly. Ambiguity risk: `BFD`+`D` (`BFDD`) relies on longest-first regex ordering, which works. Extra-league columns `HG/AG/Res` and `Time` are classified as result and id |
| 3g | Notes mapping | `notes.txt` is in the snapshot and states the rule used (pre-closing odds, closing = extra `C`) | PASS |
| 4a | Silent drops | review of `read_raw.py` and the script | PASS with notes. Dropped: empty trailing columns and blank rows (file untouched), unplayed rows (`played_only`; 0 found), rows with unparsed dates (0). See MEDIUM-3 for the unreported season-filter drop |
| 4b | Magic numbers | code review | FAIL (minor): see LOW-1 |
| 4c | Closing odds as features | code review; the availability file maps `close` to `kickoff_closing` / `evaluation_only` in every family | PASS: nothing here builds features. The only use of closing odds is diagnostics. The `use` field in `column_availability.yaml` is not yet enforced by any code, because no feature code exists |
| 4d | Banned words | case-insensitive `grep -rIil -E` of the hook's pattern over all files, excluding `.git`, `__pycache__`, `data` and the git-excluded rules file and `.claude/` | PASS: 0 files in tracked or untracked content (including `diary.md`, reports, tests, config). `data/` also has 0 text hits. The only files containing banned words are the git-excluded rules file and `.claude/`, which are excluded by `.git/info/exclude` |
| 4e | Tests cover spec behaviours | read `tests/` (146 tests) | PARTIAL: see gaps below |
| 5 | Report sanity | read the reports | PASS with notes: MEDIUM-1, MEDIUM-2 |

## Test coverage

Covered:
- `classify_column`: pre vs close mapping, source, side, unclassified.
- `add_raw_file`: write, manifest line, no overwrite, tamper detection.
- `download_all`: success, retries, failures, log append with a single header.
- `build_targets` counts.
- `read_raw_csv`: encodings and BOM.
- `io_guard`.
- Reliability: `implied_probs`, stale share, coverage, single overround, column set, `first_suspect_month`.

Gaps:
1. No test of divergence values, or of a month flagged by divergence alone. This is why HIGH-1 slipped through.
2. No test of an overround-out-of-range month being flagged.
3. No test of a stale-share threshold edge (exactly 0.10, or at 3x median).
4. No test of `max_below_pin_*`.
5. No test of the retention table (i)/(ii)/(iii). Retention logic lives only in `scripts/run_phase1a.py`, which has no tests. The same is true of the AH-sign inference, the USA playoff table, `load_all` season filtering, and `parse_date_col`.
6. No test that `download_all` writes the manifest and raw file only through `add_raw_file`.
7. No end-to-end test of the script on a fixture.
8. `tests/fixtures/` is empty. The `ls` of `tests/fixtures` printed nothing, so tests build their data inline.
9. No test that raw files end up read-only after `download_all` in the real flow.

## Suspicious items in the reports

- The 2026-02 to 2026-05 zero-coverage months (MEDIUM-1). The suspect flag fires there for the main leagues only through coverage.
- D1 `ou25` has 23 suspect months because Over/Under Pinnacle coverage sits at 0.89 to 0.96, just under the 0.95 threshold, in many months. This is mechanically correct but shows the 0.95 threshold is tight for the small German monthly samples (18 to 40 matches a month).
- USA 2026 has no extra-fixture rows yet (modal 33, max 33 matches per team), so the playoff section has no 2026 evidence. 2021 to 2025 show 26 to 60 extra team-matches above the modal count. There is no stage column to identify them (confirmed: no stage-like columns).
- AH sign: Spearman -0.9919 over 12403 rows. The empirical convention is home-line (negative = home favourite), as the report says.

## Pass or fail summary

- Tests: PASS
- Script re-run reproducibility: PASS
- Manifest verification and raw read-only: PASS
- Nothing under data/ tracked (except `.gitkeep`): PASS
- Row counts vs raw: PASS
- Pinnacle coverage/stale/overround for 3 league-months: PASS
- Retention for 2 leagues: PASS
- stale_share and overround definitions: PASS
- Divergence: FAIL (HIGH-1)
- Column classification: PASS
- Magic numbers in config: FAIL (minor)
- No closing odds as features: PASS
- No banned words in tracked or untracked content: PASS
- Test coverage of spec behaviours: PARTIAL
