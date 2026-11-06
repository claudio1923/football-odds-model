# Phase 2 independent review (market maths + Dixon-Coles)

Scope: read-only review. Scratch scripts (not in the repo) were run as
`PYTHONNOUSERSITE=1 conda run -n fbmodel python <script>`. Only this file was written.

## Verdict
No high or medium severity defect found. Look-ahead test passed, gradient and likelihood are correct,
market maths match an independent brute force, outputs are reproducible byte for byte.
Findings below are low severity.

## Checks (pass/fail)

1. PASS - `python -m pytest -q`: 258 passed. `scripts/run_phase2.py` re-run: `predictions.parquet` is byte-identical
   to the previous file (`cmp`); `model_summary.md` differs only in the Runtime table and total runtime line.
   17192 rows x 28 columns, 0 failed fits in every league.
2. PASS - no look-ahead.
   - E0 `walk_forward`; goals changed (+3 home, +1 away) for (a) the 3 last matches, (b) 3 matches in the middle (2023-12-30),
     (c) 2 matches early in the predicted period (2022-08-20). All rows with `fit_ref_date <= altered date` are bit-identical
     over all columns (late: 1520 rows, mid: 578, early: 30). All later rows changed (942 and 1490), so the test has power.
   - All 17192 rows: `fit_ref_date <= date` (max gap 6 days); `n_train_matches` equals the count of league matches with
     `date < fit_ref_date` for every row (0 mismatches).
   - 3 random blocks (SWE 2026-06-27, SP1 2023-09-29, D1 2023-10-06) re-fitted cold with `fit_dc` on matches strictly before
     `fit_ref_date`: max |diff lambda| 1.0e-4 to 3.3e-4 (explained below, finding L1); latest training date is before the ref date.
   - I1: replacing `ah_line_pre` by random values leaves every non-AH output column bit-identical, so `ah_line_pre` is never a
     fit input; only AH output columns change. `INPUT_COLUMNS` in the script contain no odds except `ah_line_pre`
     (pre-match snapshot, used only to choose the line for pricing). `stage` is read and passed through but not used by the model.
3. PASS - `_neg_loglik`: analytic gradient vs finite differences (E0 data to 2023-03-01, random parameters, 3 draws):
   max |diff| about 6e-4 where |grad| reaches 49-199 (finite-difference step 1e-6), i.e. relative error under 1e-5.
   Independent loglik (own loop-based tau + `scipy.stats.poisson.logpmf`) agrees with the code up to a constant
   -448.1474047664 identical in all 3 draws: the code drops the sum of w*log(x!y!) term (parameter-independent).
   `fit_dc` converges on that data.
4. PASS - market.py. Hand values: devig_proportional = 0.47887324, 0.28169014, 0.23943662; EV(0.5, 2.10) = 0.05; all 8 AH and
   4 OU hand-solved values exact. Brute force (own implementation): AH 6664 cases (lines -2..2 step 0.25, goals 0..6, 4 odds,
   both sides) max diff 0; OU 1482 cases (lines 0.5..5 step 0.25) max diff 0; vectorised vs scalar 500 random cases diff 0.
   devig_power: 1000 random 3-way rows, row-sum error 4e-16, constant k per row (spread 7e-16); 2-way also 1.
5. PASS - markets_from_matrix on 3 parameter sets x 17 lines (-2..2): five AH probabilities sum to 1 (error under 1e-12);
   expected profit of the home side at fair odds computed with `settle_ah` on the normalised matrix is below 1e-10 in absolute
   value everywhere; line 0 fair odds equal 1/(draw-no-bet probability); p_over (2.5), p_under, p_btts and 1X2 equal direct sums.
   In the parquet: 1X2 sum error 7e-16, OU 4e-16, AH sum error 4e-16, no infinite or missing fair odds where a line exists,
   `ah_line` equals `ah_line_pre` exactly.
6. PASS - the expected prediction set (all matches except each league's first season by earliest date) equals the predicted
   set: 17192 = 17192, no duplicate `match_id`, no first-season match predicted, counts per league x season equal the match counts.
   Flags: sample of 300 rows recomputed from raw past matches, 0 mismatches (flag totals 439 home, 473 away). Unseen teams get
   att = def = 0 via `.get(..., 0.0)` and are always flagged (0 < min_team_matches). No NaN goals or dates in `matches.parquet`.
7. PASS with notes (rule 4) - model parameters are all in `config.yaml` (`model:`). Remaining literals, all low:
   `1e-3` floor and the starting rho 0 / att 0 in `fit_dc`; `64.0` upper bracket for k in `devig_power` (the 200 steps are
   named and commented); `p_over25`/`p_under25` column names are fixed while `ou_line` is configurable (changing it would
   mislabel columns); the `{:.3e}` table format in the script.
8. Coverage gaps (low): no test that compares the analytic gradient with finite differences (checked here only); no test for NaN
   or non-positive odds in `devig_power`; no test that `ah_line_pre` does not influence non-AH output columns (done here);
   no test for the `run_phase2.py` script / its input column list; no test that `truncated_mass` is reported and small;
   no test of the exact `refit_days` grid or of `fit_ok` flag behaviour.
9. PASS with notes - `model_summary.md` content is faithful: all fits succeeded, truncated mass max 7.9e-3 (D1), mean at most
   9.1e-5; matrices are renormalised before markets (documented in code). Home advantage 0.05-0.54 over all fits; league means
   mostly 0.15-0.30 as expected, but DNK is low (about 0.08-0.14) and USA high early (0.49 in 2018, then 0.27-0.39). rho in
   [-0.19, +0.14], never at the +-0.3 bound; sign is not stable (P1 is positive on average, 0.03-0.09, and E0/SP1/SWE flip sign
   between seasons), so rho should be read as noisy. The report says "28 columns", which is correct only by accident
   (see L3).
10. PASS - case-insensitive grep of the four forbidden pattern groups in the commit-msg hook over all tracked and untracked
    non-data files (66 files, including the new Phase 2 files and this report's siblings): 0 matching files. The local tool
    folder and the rules file are excluded from the repo and were not part of this grep.

## Findings (ranked)

- L1 (low) Warm-start dependence: predictions come from a warm-started chain of fits, so a cold refit differs by up to
  3.3e-4 in lambda (L-BFGS-B default tolerances). Not look-ahead (the chain only uses earlier fits; verified bit-identical
  tests above) and deterministic, but results are tied to the exact refit grid and start values. Consider tighter `ftol`/`gtol`
  in config or note it in the diary.
- L2 (low) `devig_power` with one NaN odds returns a mixed row (for example [1, nan, 1]) instead of all-NaN. The Phase 3
  caller must drop incomplete rows before devigging. Odds sum below 1 (under-round) are handled sensibly.
- L3 (low) `run_phase2.py` adds a dead `_ym` column to `pred` before the report and uses `pred.shape[1] - 1` for the column
  count; the number is right only because of that compensation. Remove both.
- L4 (low, design) Time decay is measured from the block start (`ref`), not from each match date: all matches in a 7-day block
  share one fit. Matches played inside the current block (up to 6 days before the predicted one) are never used. This is
  conservative and consistent with "strictly before", but the spec's "days before prediction date" is met only at block level.
- L5 (info) `stage` (playoff, unknown) rows are used for training with no special handling; summary values (rho, home advantage)
  include them. USA 2020 (COVID) is not treated specially. Worth a diary note.
- L6 (info) `_neg_loglik` omits the constant log-factorial term, so `fit["fun"]` is not a true penalised log-likelihood
  (constant offset only).
- L7 (info) For extreme AH lines fair odds can be huge (63360 for a line -3 with strong underdog); the caller should cap or
  skip such rows when computing edges.

## Open items
- Decide on L1 (tolerances) and L3 (cleanup) before Phase 3; add the missing tests listed in check 8.
- Document in the diary: first/last/mean tables in the summary use row order within a season; DNK home advantage and the unstable
  sign of rho are data properties, not bugs; no evaluation scores, edges or bets were produced (none found in the outputs).
