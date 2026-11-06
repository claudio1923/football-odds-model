# Phase 3 independent review

Scope: evaluation, bet simulation and README. Read-only review; this file is the only thing written. The rules file and the commit-message hook were read first. Throwaway scripts live in the session scratch directory (outside the repo), and every command was run as `PYTHONNOUSERSITE=1 conda run -n fbmodel python <script file>`.

## Verdict

PASS with minor findings. I found no leakage, no formula errors and no reproducibility problems. Every number I recomputed independently matches the reports. The findings are two small rule-4 violations, one missing test and a few wording and visibility points.

## Checks

| # | Check | Result |
|---|---|---|
| 1 | pytest green; re-run is deterministic | PASS |
| 2 | No leakage in bet decisions or blend weights | PASS (residual information of the gate stated below) |
| 3 | Independent recomputation | PASS |
| 4 | AH edge, away side, fair-odds exclusion, NaN skips, AH CLV rule | PASS |
| 5 | Sample definition | PASS |
| 6 | Statistical wording | PASS with notes |
| 7 | Calibration PNG | PASS with notes |
| 8 | Hard-coded parameters | FAIL (minor, 2 items) |
| 9 | Test coverage vs spec | PARTIAL (gaps listed) |
| 10 | Forbidden-term grep | PASS |

### 1. Tests and determinism
- `conda run -n fbmodel python -m pytest -q` gave 305 passed.
- I took sha256 of `reports/phase3/*` and `README.md` before the re-run. Then I re-ran `scripts/run_phase3.py` (rc=0) and `scripts/build_readme.py`. All hashes were identical.
- `data/processed/bets.parquet` is not byte-compared (it is untracked and git-ignored). I re-derived the model bets with `select_bets` and `settle_bets` and compared them to the saved file: 54866 rows, `DataFrame.equals` is True. The blend bets are covered in check 3.

### 2. Leakage
- **Decision code.** In `betting.select_bets` the decision reads only these columns:
  - the probabilities (`p_*`, `bl_*`, the five `ah_*` outcome probabilities);
  - Max PRE odds (`odds_*_max_pre_*`);
  - `ah_line_pre`;
  - the gate `ref_source_<market>_close == "pin"`.
  Closing odds, `ah_line_close` and results are read only in `settle_bets`, after selection. The `bet_stats` function receives profit and CLV only.
- **Scramble experiment (my own).** I took a copy of the main-league matches. I permuted or noised 11 columns: every closing odds column, `ah_line_close`, `result`, `home_goals` and `away_goals`. For thresholds 0.02, 0.05 and 0.10 (model signal), `select_bets` returned identical bets (23135, 18916, 12815 rows) and identical skip tables. The suite also has `test_invariance_to_closing_and_results`.
- **Residual information in the gate.** `ref_source_*_close == "pin"` carries three things:
  - A calendar cutoff month per league, taken from `config/reference_price.yaml`. This was decided after seeing the data, because it encodes the outage.
  - A league-month flag from the Pinnacle-vs-average divergence diagnostics. That statistic is computed over the whole month, including matches after the bet.
  - The presence of all Pinnacle closing prices above 1.0 for the match.
  None of these depends on the match result or on the odds values of the match itself, apart from the >1.0 sanity check. So it is an availability gate, not an outcome gate. It does use hindsight about the Pinnacle outage. It is documented in `bet_simulation.md` ("an availability gate"), and I consider it acceptable.
- **Blend weights.** `evaluation.season_blend_weights` orders seasons by earliest date and fits season i on `order[:i]` only. The first season gets NaN, so no blend.
  - Perturbation test: for each season s, I replaced the results and the model probabilities of all matches from season s onward with random values. The weights for every season up to and including s were unchanged (True for 2324, 2425 and 2526).
  - Blend probabilities for season s in `run_phase3.py` come from `bd.merge(wt, ...)`, which is that season's own weight (fit on earlier seasons). My independent bet derivation used the weights from `blend_weights.csv` per league and season and reproduced the saved blend bets exactly.
- **Note.** Blend weights use results of earlier full seasons only. They are fixed for the whole season, which is conservative.

### 3. Independent recomputation
All numbers below are from my own code. They are not taken from the package.

- **Pooled-main 1X2.** n=9368. I recomputed the log loss, Brier and RPS of the model and of Pinnacle closing (proportional devig) on the same matches. They match `forecast_quality.csv`:

  | | log loss | Brier | RPS |
  |---|---|---|---|
  | model | 0.98667 | 0.58811 | 0.19960 |
  | Pinnacle closing | 0.96170 | 0.57161 | 0.19203 |

- **O/U 2.5.** E0: n=1315, log loss 0.67334 (model) and 0.66614 (Pinnacle). SP1: n=1308, log loss 0.67573 and 0.66254. The Brier scores also match.
- **ECE (10 bins).** Pooled main: model 0.011221, Pinnacle 0.017304. USA: 0.020661 and 0.023252. All match `calibration_ece.csv`.
- **Blend weights, brute force over a 0.01 grid on earlier seasons.** D1: 0.13, 0.0, 0.0. N1: 0.27, 0.05, 0.0. E0: 0.0, 0.0, 0.0. All match `blend_weights.csv`.
- **Bet cells.** I re-derived the bets from `matches.parquet` and `predictions.parquet`, using my own brute-force settle for 1X2, O/U and AH. The AH settle uses a quarter-line split into two half-stakes. Every cell matched `bet_summary.csv` on n bets, ROI, mean CLV, n_clv, longest losing streak and max drawdown:
  - 1X2 model at 0.05: n=7494, ROI -0.100399, CLV -0.013122, streak 28, drawdown 773.54.
  - O/U 2.5 model at 0.02: n=7026, ROI -0.032217, streak 11, drawdown 239.90.
  - AH model at 0.05: n=5982, ROI -0.026482, n_clv=3730, streak 12, drawdown 171.215. AH at 0.10 also matches.
  - 1X2 blend at 0.02, 0.05 and 0.10: n=2067, 649 and 140, all stats match (CLV +0.0254, +0.0358, +0.0558).
  - Only difference: `share_beating_close` differed in the 4th decimal for O/U and AH (0.38429 vs 0.38471, 0.38606 vs 0.38633, 0.40329 vs 0.40371). Cause: my CLV is computed as O*fair-1 and theirs as O/(1/fair)-1, so a few CLV values that are exactly zero or about 1e-16 fall on different sides of `> 0`. It affects 3 to 6 bets per cell and is immaterial.
- The bootstrap CIs were not independently recomputed. Their code is covered by unit tests, and the re-run is deterministic.

### 4. AH, fair-odds exclusion, skips, CLV rule
- **Home edge.** `(fw+0.5hw)(O-1) - 0.5hl - fl`. This is correct: a half win pays half the odds profit, and a half loss costs 0.5.
- **Away edge.** `(fl+0.5hl)(O_away-1) - 0.5hw - fw`. This is correct, since the away side wins where the home side loses. My independent edge calculation reproduces every AH bet.
- **Fair odds.** The package computes `1 + loss_units/win_units` per side. For the home side this equals the `ah_fair_odds` column in predictions (max abs difference 0.0). The away side uses the mirrored probabilities. The five AH probabilities sum to 1 (max deviation 4e-16).
- **Cap on Max odds.** Applied per outcome. The AH fair-odds exclusion is also applied per side, which is a reasonable reading of "lines whose model fair odds exceed it".
- **NaN skips.** `bet_skipped.csv` counts, among rows passing the gate, 1 for 1X2, 1 for O/U and 3 for AH, per model threshold. My independent derivation gives the same counts (1, 1 and 3). The blend count of 2820 is the same at each threshold. It consists of matches with no blend probability (the first season of each league and matches without a Pinnacle pre reference).
- **AH CLV.** Defined only if all closing prices are present and `ah_line_close == ah_line_pre`. A total of 5982 AH bets at 0.05 have only 3730 CLV values. All of this is correct and reported as `n_clv`.
- **Line consistency.** The AH probabilities in predictions are computed at `ah_line`, while the bet is settled at `ah_line_pre`. In the data, `ah_line` equals `ah_line_pre` in all gated main-league rows except 2 where both are NaN. No bet is affected. `select_bets` does not assert this, so a future data change could silently break it (see open items).

### 5. Sample
- Forecast quality uses `ref_source_<market>_<timing> == "pin"` as the filter. Model and benchmark are scored on the same rows (a paired difference on the same array).
- The pooled-main n is 9368 for closing and 9364 for pre. Pinnacle pre and O/U are limited to the main leagues, and USA, DNK and SWE appear against closing 1X2 only.
- Bets, blend and O/U use the main leagues only. Predictions begin at the second season of each league.

### 6. Statistical wording
I found no overclaims.
- The README describes the model as worse than Pinnacle closing on 1X2 (diff +0.0250, CI [0.0215, 0.0285]). That is what the numbers show.
- The README does not claim the model is better calibrated than Pinnacle, though ECE is lower for the model (0.011 vs 0.017). A lower ECE with a worse log loss is possible, because ECE uses 10 bins and is noisy at the extremes.
- The blend section is honest. w is 0 in 21 of 24 league-seasons, so the blend is essentially Pinnacle pre fair. The note says its CLV (+0.025 to +0.056, CI above 0) is not model skill. I agree: it is price shopping, with Max pre odds compared to a Pinnacle pre price. The README gives the uninformed-bet reference CLV (-0.0054) next to the CLV table but does not interpret it. A one-sentence comparison could help.
- All model ROI and CLV cells are negative, and no positive claim is made. The only positive-ROI cell, blend at 0.10 (+0.0103, CI [-0.397, 0.438], n=140), is clearly not significant. The caveat "a single positive cell is not evidence" is present in both the README and `bet_simulation.md`.
- Not quite stated clearly in the README:
  - The AH CLV is a mean over 62% of the AH bets only (lines that moved are dropped). The README table omits `n_clv`. The full report has it.
  - The ROI CI treats bets as independent. This is stated. Bets in the same match across markets are correlated, but each pooled cell is a single market.
  - The README says "no look-ahead: every prediction uses only matches strictly before the match date" and "closing odds are never model inputs". These come from Phase 2 and were not re-verified here.
- Numbers typed by hand in `build_readme.py`: the "snapshot 2026-11-06" date in the template string. It is correct, since the manifest paths carry 2026-11-06, but it is not read from a file. It is the only such item I found. The `Source: football-data.co.uk` text is a literal too.

### 7. Calibration PNG
The plot is clear and readable. Both panels show the model and Pinnacle closing against the diagonal, with the ECE in the legend. On the main leagues both lines track the diagonal. The outermost bins are noisy (model about 0.77 at predicted 0.91; Pinnacle 1.0 at the top). The USA panel shows a model point at 0.0 observed in the lowest bin, and a Pinnacle point near 0.33 at predicted 0.18. These are clearly tiny-n bins. The plot does not show the bin counts, so a reader cannot see this. The text says the outer bins are noisy and points to the CSV. I suggest adding point sizes proportional to n, or counts. This is cosmetic.

### 8. Hard-coded parameters (rule 4)
- `src/fbmodel/betting.py:12`: `OU_LINE = 2.5`. `model.ou_line: 2.5` already exists in the config. The betting code should read it. Minor, as the value is the definition of the market.
- `scripts/run_phase3.py:86`: `> 2.5` for the over indicator. Same point, and it is a literal in a script.
- `scripts/run_phase3.py:127`: the "USA" calibration panel is a literal league. Cosmetic.
- Colours, figure size and the `_CHUNK=250` in the code are presentation or memory-only values. The `_CHUNK` is documented as not affecting results. I do not count them.
- All evaluation parameters (B, seed, CI level, bins, grid, odds cap, thresholds, stake) are in `config.yaml` under `evaluation`. Reading `stake` from config: flat stake 1 is baked into the profit per unit and `stake` is not used in the code (stake=1.0 in config is effectively unused). This is harmless, but it could mislead someone who changes it.

### 9. Test coverage vs spec
Covered: the metrics, bootstrap, blend weight search, season ordering and no-leakage of weights, thresholds, one bet per match, odds cap, NaN skip, the gate, O/U, AH formulas including quarter lines and the away side, settle for 1X2, O/U and AH, the line-moved CLV NaN case, and invariance to closing and results.
Gaps:
- No test of the AH fair-odds exclusion (fair odds above the cap).
- No test that `ah_line` (prediction) equals `ah_line_pre`.
- No end-to-end test of `run_phase3.py` (same-match subset, pin filtering, main-leagues-only for O/U, blend and bets).
- No test of `build_readme.py`, for example that the numbers in the README equal the CSV values.
- No test of per-league scope handling in `bet_stats` pooling.

### 10. Forbidden terms
A case-insensitive grep, with the terms from the commit-message hook, over all tracked files plus untracked non-ignored files gave 0 files with hits. A grep over the whole tree (excluding `.git`, `data/raw` and `.idea`) hit only the rules file, which is excluded from git. The last 6 commit messages have 0 hits. This report itself uses placeholders only.

## Findings ranked

1. (Low) The rule-4 literals listed in check 8. The `stake` config value is unused.
2. (Low) A missing test for the AH fair-odds exclusion, and none for the `ah_line` vs `ah_line_pre` consistency. Also no script-level or README tests.
3. (Low) `select_bets` does not assert `ah_line == ah_line_pre`. It holds in the current data (the only 2 differing rows are NaN in both).
4. (Low, presentation) The README table omits `n_clv`, while the AH CLV covers about 62% of the AH bets. The calibration PNG shows no bin counts. The README lists the uninformed-bet CLV without interpreting it. The skipped table labels the blend NaNs (first season, no Pinnacle pre) as "nan_odds_line_or_probs".
5. (Info) `share_beating_close` can differ from a recomputation by a few bets near CLV = 0 because of floating-point rounding. Streak and drawdown depend on the order within a date (ties by `match_id`, a hash). This is deterministic and arbitrary. Drawdown in "units" is on the stake-1 scale.
6. (Info) The gate carries hindsight about the Pinnacle outage (calendar cutoff and monthly diagnostics). It carries no result information.

## Open items for the caller
- Decide whether to fix findings 1 to 3 now (small edits to code, config and tests) or log them in the diary.
- Optionally add `n_clv` and one interpretation sentence on the uninformed-bet reference to the README generator.
- The bootstrap CIs and the Phase 2 no-look-ahead claim were not re-derived here.
