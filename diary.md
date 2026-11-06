# Project diary

## Phase 0 — Project setup (2026-11-06)

### Decisions
- src layout, package `fbmodel`, single config at `config/config.yaml`; `load_config` has no defaults in code and raises `KeyError` on missing keys.
- `io_guard.safe_write_path` takes an optional `raw_dir` so tests can use temporary folders; by default it uses the configured `data/raw`.
- Manifest format: one line per file, `<sha256>  <path relative to the manifest folder>`.
- `data/**` is ignored by git except `.gitkeep` files.
- Commit guard: `.git/hooks/commit-msg` (not versioned) rejects forbidden terms in commit messages.

### Errors and fixes
- `conda env create -f environment.yml` (conda 4.13.0, classic solver) was still solving after more than 15 minutes. It was stopped and the documented fallback was used: `conda create -n fbmodel -c conda-forge python=3.11 pip -y`, then `python -m pip install` of the listed packages. Versions are recorded in `requirements.lock.txt` (`pip freeze`). `environment.yml` is kept as the intended specification.

### Open points
- `config/config.yaml` `data_source:` is a placeholder (TODO_PHASE1).
- The manifest file `data/raw/MANIFEST.sha256` does not exist yet; it is created when raw data is added in Phase 1.

### Phase 0 addendum — corrective task (2026-11-06)

- **Hand edit of the lock.** In the first pass one line of `requirements.lock.txt` (`packaging @ file:///...`, a build-directory path written by `pip freeze`) was replaced by hand with `packaging==26.3`, and this was not recorded. The lock was rebuilt using no manual changes: `PYTHONNOUSERSITE=1 conda run -n fbmodel python -m pip list --format=freeze`, excluding only the `fbmodel==` editable line. The line produced by pip is `packaging==26.3`, the same value.
- **uv finding.** `pip show uv` reported `Requires:` and `Required-by:` both empty, with location `C:\Users\Claud\AppData\Roaming\Python\Python311\site-packages`. So `uv` is not installed in the `fbmodel` env: it is the only package in the user-level site-packages of Python 3.11, which every Python 3.11 on this machine can see, and `pip freeze` inside the env picked it up for that reason. Nothing requires it. Deviation from the task: it was not uninstalled, because that would modify a shared location outside `fbmodel`; instead the lock is produced under `PYTHONNOUSERSITE=1`, which excludes it. The regenerated lock also gained `pip`, `setuptools` and `wheel`, which the first lock lacked.
- **Reproducibility check** (throwaway env `fbmodel_check`, removed afterwards; `conda env list` confirms):
  - Route 1, `conda env create -f environment.yml -n fbmodel_check` with a pip section `-r requirements.lock.txt`: succeeded, but took 12m13s, above the 10-minute limit, so the fallback route was required. `pip install -e .` 27s, `pytest -q` 19 passed.
  - Route 2 (fallback), adopted: `conda create -n fbmodel_check -c conda-forge python=3.11 pip -y` 2m22s; `pip install -r requirements.lock.txt` 4m22s; `pip install -e .` 32s; `pytest -q` 19 passed. The frozen package list of the rebuilt env is identical to `requirements.lock.txt` (`diff` empty).
  - `environment.yml` now holds only the conda layer (python 3.11, pip); the Python packages come from the lock via pip. README describes route 2. The edited `environment.yml` itself was not run through `conda env create` after the change; the README commands are the ones that were executed.
- **Process deviations (recorded as such).** (1) The builder edited the reviewer's report (reworded text that contained words banned by rule 7); in the corrective round nobody but the reviewer edits its report. (2) The test writer was told about the `raw_dir` parameter of `safe_write_path`, which came from the builder's implementation, so it did not write purely from the original spec; a test using the default raw directory from the config was added in this round.
- **Open points** unchanged: `data_source` placeholder; no raw manifest yet.

## Phase 1A — Download, inventory, Pinnacle reliability (2026-11-06)

All numbers below come from `PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase1a.py` (outputs in `reports/phase1/`) and `... python -m pytest -q`.

### Verification of assumptions (site pages fetched 2026-11-06)
- League pages (italym, spainm, germanym, francem, netherlandsm, portugalm, englandm) list `mmz4281/<season>/<code>.csv` for I1, I2, SP1, D1, F1, N1, P1, E0 and for 2122 and 2526. `usa.php`, `sweden.php`, `denmark.php` link `new/USA.csv`, `new/SWE.csv`, `new/DNK.csv`. Codes and URL patterns are confirmed.
- `www.football-data.co.uk` answers every request with HTTP 302 to `football-data.co.uk` (no www); the downloader follows redirects. `base_url` in config is unchanged.
- Season labels in the extra files: USA and SWE use the calendar year (`Season` = 2012..2026); DNK uses `2021/2022` form (also `2026/2027`, excluded as in progress). Labels in config match the file exactly.
- The extra-league files (USA, DNK, SWE) are ONE file per league holding all seasons since 2012, with CLOSING odds only (PSC*, MaxC*, AvgC*, BFEC*, B365C*). They contain no pre-closing odds, no totals and no Asian handicap. The main-league files have the full set. The 2026 rows of the main leagues are not in scope (2526 is the last season).
- Consequence for design: `build_targets` returns one target per main league x season and ONE per extra league (season `all`, `<code>_all.csv`); the configured seasons are applied when the file is read. Added config keys: `max_retries`, `timeout_seconds`, `user_agent`, `inventory.*`, `pinnacle_checks.*`.

### Raw-area rule
- Only `fbmodel.data.download.add_raw_file` writes under `data/raw`: it creates new files, sets them read-only, appends to `data/manifest/MANIFEST.sha256`. `verify_raw_manifest(manifest, raw_dir)` resolves entries relative to `raw_dir`; existing tests updated. Snapshot: `data/raw/football-data/2026-11-06/` plus `notes.txt` in the same folder.

### notes.txt (exact sentences)
- "The following key to betting odds data is described below. These are for pre-closing odds. For the closing odds, as below but with an additional "C" character following the bookmaker abbreviation/Max/Avg (e.g. B365CH = closing Bet365 home win odds)."
- "Betting odds for weekend games are collected Friday afternoons, and on Tuesday afternoons for midweek games."
- notes.txt does NOT state when the closing odds are collected. "Closing = at kick-off" is the working assumption of the spec, not a documented fact. It also says nothing about the AH sign convention (inferred empirically, see inventory_summary.md section e).
- Availability file: `config/column_availability.yaml` (results and match stats = post_match; closing = kickoff_closing, evaluation only).

### Findings (see reports for the numbers)
- Download: 44 requests logged (43 data files + notes.txt), 0 failed URLs. Encodings: all 43 CSV files read as utf-8 (with BOM).
- Rows without result: 0 in every league x season (section a lists rows per league x season). USA/SWE 2026 end 2026-11-02 / 2026-11-03 against snapshot 2026-11-06.
- Pinnacle disappears (coverage; plus the divergence check, see Errors below): from 2026-01 (E0, D1, F1, I1, P1, SP1) and from 2025-10/2025-11 for I2 and N1, Pinnacle coverage falls and is 0 from 2026-02 onwards. For USA/DNK/SWE closing Pinnacle is 0 in most months from 2026-02 on. Average and Max stay complete. See `pinnacle_reliability.md`: first suspect months, reasons, retention tables (i)(ii)(iii).
- USA playoffs: no stage column; matches per team above the regular-season mode in 2021-2025 show playoff matches are present (section d). Not dropped.
- AH sign: AHh falls as the Pinnacle pre home-win probability rises (Spearman in section e): negative = home favourite, quoted for the home team.
- Unclassified columns: none.

### Decisions and interpretations
- Retention (ii) is read month-wise: Pinnacle in non-suspect months, Avg in suspect months. Retention (i) removes every month from the first suspect month on. Both interpretations are the builder's; to be confirmed in "go B".
- `monthly_diagnostics` suspect flag is evaluated per market; first_suspect_month and retention use 1X2 only. For leagues with closing-only files, only the close timing is tested.
- Stale share is computed on matches with valid Pinnacle pre AND close; the multiple-of-median condition uses the league's monthly median per market.

### Process
- Tests written by a separate agent from the spec only (no access to src/); 146 tests pass. Reviewer report: `reports/phase1/review_A.md`.

### Open points
- Reference-price rule awaits "go B".
- Extra leagues have no pre-match odds at all: the model cannot use pre-match odds as a feature there; decision for the user.

### Errors and fixes (Phase 1A)
- Reviewer finding (high): the divergence check never fired because the Pinnacle and Avg probability frames have different column labels, so pandas aligned them to all-NaN; all divergence columns were empty. Fixed by subtracting the underlying arrays; five tests with known divergence values were added (151 tests pass). After the fix, divergence_close_p95 is non-null in 1234 rows and the first suspect month of USA and SWE moves to 2025-08 (divergence), N1 gets one divergence month; E0/I1/etc. are unchanged. Numbers in `reports/phase1/pinnacle_reliability.*` are from the fixed code. `review_A.md` was written before the fix and is left as the reviewer wrote it.
- Reviewer finding (medium): extra-league rows outside the configured seasons are now listed with counts in inventory_summary.md (not deleted).
- Reviewer finding (low, open): a few constants remain in code rather than config (0.05/0.95 quantiles, validity threshold > 1.0, `tail(10)` in the weekly table, the source/outcome lists); to be moved to config in a later pass.
- Process: the first patch of run_phase1a.py contained a broken string literal (SyntaxError) and was fixed the same session. One no-op workflow call was made by mistake; it ran no agents.

## Phase 1B — Cleaning (2026-11-06)

All numbers from `PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase1b.py` (reports in `reports/phase1/`), `... python -m pytest -q` and the Part A script.

### Decisions at "go B" (project owner), with reasons
1. **MLS history extended to 2017..2026** (calendar years). No new download: the snapshot file already holds them. Column `season_note` = `no_crowd_2020` for USA 2020 (rows kept). Part A re-run on 2017..2026: USA 2017-2020 has 0 suspect months (1X2, close), so the stop condition (more than 2) did not trigger. Reason: more history for the closing-price comparison, with the 2020 no-crowd season labelled instead of removed.
2. **Reference-price rule** (`config/reference_price.yaml`, verbatim): `ref_source` for a match, market and timing = "pin" only if ALL hold: (a) the match month is before the league `cutoff_month`; (b) the league-month is not suspect in the 1X2 diagnostics (any reason, any timing); (c) all Pinnacle outcomes of that market and timing for that match are present and > 1.0. Otherwise "none". Avg never replaces Pinnacle as reference; Avg and Max stay as data columns. Stored as `ref_source_{1x2,ou25,ah}_{pre,close}` ("none" where the file has no such columns). Cutoffs: E0, I1, SP1, D1, F1, P1: 2026-01; I2, N1: 2025-10; DNK: 2025-11; SWE: 2025-08; USA: 2025-08.
   Motivation: the Pinnacle feed degrades before it disappears (SWE: three months of divergence above threshold, then zero coverage), so months after the first flag are not trusted; Avg includes slow, high-margin books and would change the benchmark exactly in the most recent period; no match is dropped, it only loses the reference. Retention below `max_loss_share` for USA and SWE is accepted by this decision (config `loss_exempt_leagues`) and does not trigger the early stop; numbers are reported anyway.
3. **Declared limit, extra leagues**: USA, DNK and SWE have closing 1X2 only (no pre-closing odds, no totals, no Asian handicap). For them: no CLV, no pre-match edge, no opening-odds blend. Phase 3 compares Max closing with the Pinnacle closing fair price only. Written in `inventory_summary.md`.
4. **USA stage** (rule from the data, evidence in `usa_stage_evidence.csv`): per season, N = unique modal matches per team; a match is a playoff match when both teams already played at least N matches of that season on earlier dates; the rule is accepted for a season only if rows - playoff matches = teams x N / 2 (a complete regular schedule). It validates for 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025. Not validated: 2020 (no unique mode, unequal schedules) - rule matches are "unknown"; 2026 is in progress - superseded by the final decisions below (2026 = "regular"). Counts per season are in the table of the quality report. Other leagues: "regular"; DNK "unknown" because its split phases exist but are not identifiable in the file.
5. **Part A fixes**: literals moved to config (`pinnacle_checks.min_valid_odds/quantile_low/quantile_high`, `inventory.*`); second review `review_A2.md`; `review_A.md` rewritten so the forbidden-term grep is empty (verdicts unchanged, first line "Superseded by review_A2.md").

### Design
- `config/column_map.yaml` is generated by `scripts/make_column_map.py` from the raw headers: original -> canonical `odds_{market}_{source}_{timing}_{side}` for Pinnacle (pin), Max, Avg, Bet365 (b365); `ah_line_pre/close` for AHh/AHCh; other bookmakers (and Betbrain helper counts) are listed under `dropped:` with a reason (kept in raw). `availability:` gives family and timing of every canonical column; `feature_eligibility` in config.yaml = pre-match columns only. `config/team_aliases.yaml` is empty: names are never merged.
- Played only: rows without H/D/A result are excluded and counted (exclusions table); in this snapshot that count is 0. Odds are never imputed or changed. Flags only: qa_exact_duplicate, qa_duplicate_key, qa_team_twice_same_date, qa_result_goals_mismatch, qa_odds_out_of_range, qa_overround_out_of_range.
- Suspect months for rule (b) are recomputed inside `build_matches` from the same `monthly_diagnostics` as Part A (1X2 rows, per league, all seasons loaded).
- `matches.parquet`: sorted by date, kickoff (null last), league, home; written twice in memory and compared (assert_frame_equal) and against any previous file.

### Findings
- Two non-numeric tokens in numeric odds columns (N1 2022/23 B365CH '#'; USA 2025 AvgCH 'x'; `nonnumeric_values.csv`). They become NaN in `matches.parquet` (a typed column needs it); the raw files are unchanged. This is the only value-level conversion and is listed here for confirmation.
- Quality summary, retention and per-season counts: see `quality_report.md`, `sample_retention.md` and the acceptance evidence given at the end of the phase.

### Errors and fixes
- First run failed on the non-numeric tokens (ValueError); fixed by coercion plus an explicit report (above).
- Parquet round trip compared None against NaN in `season_note`; the comparison in the script now uses a null-neutral view.
- A multi-line `python -c` is not supported by `conda run`; scratch scripts are used instead.

### Open points
- Confirm the non-numeric-token handling.
- Near-duplicate team names are listed in `near_duplicate_team_names.csv` for the owner's decision; `team_aliases.yaml` stays empty.

### Review follow-up (Phase 1A re-review and Phase 1B review)
- `review_A2.md`: divergence fix confirmed (24 league-month-timing cells recomputed from raw); USA 2017-2020 has 0 suspect months. Open/fixed: pooled availability table and retention (ii) could hide the Pinnacle outage -> explanatory notes added to `inventory_summary.md` and `pinnacle_reliability.md`; "last N weeks" label now read from config. Left open (low): `reliability_reference_source` config key unused; p5/p95 column names fixed strings.
- `review_B.md`: parquet, flags, ref_source (all 20836 rows x 6 columns) and retention reproduce independently; no high-severity defect. Fixed: in seasons where the USA stage rule is not validated (2020) every match from the first rule-flagged date on is now "unknown" (before, 2 late-November 2020 matches were labelled "regular"); parquet regenerated, then run twice (identical). 2026 was "unknown" at that point; changed in the final decisions below. Open (low): rows of extra files outside the configured seasons are counted in `inventory_summary.md` (Part A) but not in a Part B exclusion table; sort sentinel, hash length, date formats and the pin/b365 overround source list are in code; no direct tests for `assign_stage`, `nonnumeric_report` and the suspect-month plumbing.

## Phase 1 — final decisions (2026-11-06)

Project owner's decisions on the Part B report:
1. Non-numeric tokens "#" (N1 2022/23 B365CH) and "x" (USA 2025 AvgCH) become NaN: confirmed. Non-odds tokens become missing; they stay listed in `nonnumeric_values.csv`; raw files unchanged.
2. USA 2026: stage = "regular". Reason: every team has played exactly 33 matches, none beyond the regular count. Implemented in `assign_stage`: a season in progress is "regular" while every team has played the same number of matches, otherwise "unknown". USA 2020 (unequal schedules, 30 matches "unknown" from the first rule-flagged date) and DNK (split phases not identifiable) stay "unknown". `matches.parquet` regenerated and run twice (identical); 199 tests pass.
3. Reggiana / Reggina (I2) are two different clubs: never merge. `team_aliases.yaml` stays empty.
4. Retention (ii) of Part A is near 100% only because Avg fills the outage window: noted. `sample_retention.md` is the reference number.
Housekeeping: at the start of this step one leftover process (a reviewer's scratch script under `conda run`) was found running and stopped; no agent was running; the working tree was clean at commit 0e4b6d8.

## Phase 2 — Market math and Dixon-Coles model (2026-11-06)

Numbers from `PYTHONNOUSERSITE=1 conda run -n fbmodel python scripts/run_phase2.py` (`reports/phase2/model_summary.md`) and `... python -m pytest -q`.

### What was built
- `src/fbmodel/market.py`: implied_probs, overround, devig_proportional, devig_power (per-row bisection on k, 200 halvings: an algorithmic constant, not a parameter), expected_value, settle_ah, settle_ou (quarter lines split in two half stakes; `half_lines` is the shared helper). Odds arrays carry the outcomes on the last axis.
- `src/fbmodel/model/dixon_coles.py`: `tau`, `score_matrix` (not renormalised; sum = 1 - truncated mass), `markets_from_matrix` (renormalises; AH full/half win, push, half/full loss for the home side, fair odds with expected profit 0), `fit_dc` (weighted ML, analytic gradient, L-BFGS-B, L2 on att and def, rho bounded), `walk_forward`. Gradient checked against finite differences on real data (error about 1e-4 against a gradient norm of about 1.2e3).
- `scripts/run_phase2.py` writes `data/processed/predictions.parquet` and `reports/phase2/model_summary.md`.

### Decisions (all parameters in config `model:`; none tuned on evaluation seasons)
- xi = 0.0019 per day (given), l2_penalty = 3.0 (prior sd of att/def about 0.4, chosen a priori), refit_days 7, max_goals 10, min_team_matches 10, rho_bounds [-0.3, 0.3], tau_floor 1e-6, ou_line 2.5. xi was NOT tuned.
- `fit_dc` raises AssertionError if any passed match has date >= ref_date (the caller filters). I read "assert it" this way because filtering inside would make the assertion vacuous.
- Refit grid: t0 = first date of the first predicted season of the league; block k = [t0 + 7k, t0 + 7(k+1)); every match of a block is predicted from the fit on matches strictly before the block start (so a prediction can be up to 6 days staler than strictly necessary: conservative). `fit_ref_date` = block start. Warm start from the previous block's parameters, matched by team name; unseen teams start at 0. Team list of a fit = teams present in its training matches only, so a future result cannot change earlier fits.
- The first season of each league (earliest dated) is training only: D1/E0/F1/I1/I2/N1/P1/SP1 start predictions in 2022/23, DNK in 2022/23, SWE in 2022, USA in 2018 (USA 2017 is training only).
- All matches (including USA playoffs and the USA 2026 season in progress) are predicted and used in later fits; `stage` is carried through for later filtering.
- `ah_line_pre` (a pre-match line, not an odds price) is used only to price the AH probabilities of the output; it is never an input to a fit. No odds column enters the model.
- Predictions parquet columns: match_id, league, season, date, stage, fit_ref_date, lambda_home, lambda_away, rho, home_adv, p_home, p_draw, p_away, p_over25, p_under25, p_btts, truncated_mass, ah_line, ah_full_win, ah_half_win, ah_push, ah_half_loss, ah_full_loss, ah_fair_odds, n_train_matches, flag_home_few_matches, flag_away_few_matches, fit_ok.

### Results (see model_summary.md)
- Predictions shape (17192, 28) over 11 leagues; every league was fitted; failed fits (optimizer not reporting success): 0 in all leagues; maximum truncated mass 7.9e-03 (D1; mean about 1e-5 to 1e-4). Total runtime 80.7 s.
- Home advantage per league lies between about 0.08 (DNK) and 0.55 (USA 2018, falling over time); rho is small and varies in sign by league.
- Few-matches flags are frequent in I2 (promotion/relegation).

### Process notes
- Test writer worked from the spec only; a failing run printed a few lines of implementation code in a traceback, and the spec did not list `ou_line` among the config keys (it was added to the config and the test configuration). 258 tests pass.
- Reviewer report: `reports/phase2/review.md`.

### Open points
- No evaluation scores, edges or bets in this phase (next phase).

### Reviewer follow-up (reports/phase2/review.md: no high or medium defects, 10 checks pass)
- Confirmed by the reviewer: bit-identical earlier predictions when later results change (late, middle and early-predicted matches), fit_ref_date <= date for all 17192 rows, gradient and likelihood checks, market functions against a brute-force implementation, parquet byte-identical on re-run.
- Noted, not changed (low): predictions depend slightly on the warm-start chain (up to 3.3e-4 in lambda against a cold refit; deterministic, no look-ahead); time decay is measured from the block start and matches inside the current 7-day block are not used; `devig_power` returns a mixed row for NaN odds, so Phase 3 must drop incomplete rows first; fair AH odds can be very large for strong underdogs, so cap or skip them when computing edges; playoff, unknown-stage matches and USA 2020 are used in training without special handling; literals still in code (1e-3 floor in `fit_dc`, 64.0 bracket in `devig_power`, fixed `p_over25`/`p_under25` names with a configurable ou_line); missing tests (gradient vs finite differences, NaN odds, run_phase2.py, ah_line_pre invariance).
- Fixed: dead `_ym` column removed from run_phase2.py.
