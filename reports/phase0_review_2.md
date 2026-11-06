# Phase 0 review 2 (corrective round)

Scope: working tree (uncommitted) on top of the single existing commit. Read-only review.

## Verdicts

1. Lock file: PASS.
   - `PYTHONNOUSERSITE=1 conda run -n fbmodel python -m pip list --format=freeze`, minus the editable project line, CRLF stripped, diffed against `requirements.lock.txt`: no differences (printed SAME).
   - No '@ file' entries, no absolute paths, no `uv` line (36 pinned lines read by eye).
   - `uv` explanation in diary: PASS. `pip show uv` without the isolation flag gives Location in the user-level Roaming Python311 site-packages, empty Requires and Required-by. With the isolation flag it reports "Package(s) not found: uv". `pip list --user` lists only `uv 0.13.0`. This matches the diary text.
2. environment.yml and README: PASS.
   - environment.yml: channels conda-forge and nodefaults, dependencies python=3.11 and pip, nothing else.
   - README Environment section: the create command, the lock install, and `pip install -e .`. These match route 2 as written in the diary. README contains nothing else unverified.
   - Caveat, disclosed by the diary: environment.yml was not itself run through `conda env create` after the edit, and the nodefaults channel was not exercised by route 2 (CLI used only conda-forge).
3. Tests: PASS. `conda run -n fbmodel python -m pytest -q` printed `19 passed in 0.50s`.
   - New test `test_safe_write_path_default_raw_dir_from_config`: calls `safe_write_path` with no `raw_dir` argument, so it takes the default from config (the code path `_raw_dir()`). It rejects `paths["raw"]/x.csv`, rejects `processed/../raw/x.csv`, accepts `processed/x.csv` (returns the resolved path), and asserts the target does not exist. It performs no writes.
   - `data/` listing afterwards: only the three `.gitkeep` files. `git status` shows no new untracked files.
4. Code diff: PASS. `git diff HEAD --stat` shows 5 files: README.md, diary.md, environment.yml, requirements.lock.txt, tests/test_io_guard.py. `git diff HEAD -- src config pyproject.toml tests` shows only the 13 added lines in tests/test_io_guard.py. Nothing in src, config or pyproject changed.
5. Diary addendum honesty: PASS with limits.
   - Lock content claims (generated line `packaging==26.3`, gained pip/setuptools/wheel, no manual edits, identical to freeze) are confirmed.
   - `conda env list` shows no `fbmodel_check`: confirmed.
   - Durations (12m13s, 2m22s, 4m22s, 27s, 32s) and the "19 passed" in the throwaway env come from earlier runs; they cannot be verified now.
   - Claim that the README commands were executed is consistent with route 2 as described.
6. Forbidden-term grep: FAIL (see defect 1).
   - Tracked-file grep hits only diary.md (two lines). Hits with --no-index over diary.md, README.md, reports/, environment.yml, tests/ also only diary.md.
   - The hit is a substring match of one forbidden two-word phrase inside ordinary verbs ("re-" prefixed form and plain form) in addendum bullets 1 and 2. The match is case-insensitive and not word-bounded.
   - No tracked file name contains a forbidden term. The rules file and local tool folder are excluded via `.git/info/exclude` and untracked.
7. Rules and hook: PASS.
   - Rules 1-8 re-read from the rules file on disk; they are intact (sole author, no trailers, no forbidden mentions, origin/main only, data never committed).
   - Hook `.git/hooks/commit-msg` exists. Tested on temp files: a plain message gives exit 0; a message with a co-author trailer gives exit 1; a message containing the tool-vendor name gives exit 1.
8. PENDING (needs commit and push): author of the last 2 commits, absence of trailers, `git status -sb` tracking origin/main. Currently there is one commit, authored by the configured sole author.

## Defects

1. HIGH (blocks commit under rule 7): diary.md lines 21 and 22 contain words whose substring matches a forbidden phrase (the verb "generate" in past tense followed by "with"). Reword both (for example "rebuilt using" and "produced using"), then re-run the grep.
2. LOW: the commit-msg hook does not check the standalone two-letter word required by rule 7 (a test message using it was accepted, exit 0). The hook covers only the trailer, the vendor names and the generated-with phrase. Not exercised by this commit, but the hook is weaker than the rule.
3. LOW: line-ending warnings (LF to CRLF) on commit; harmless. The CRLF/LF mix means any diff of the lock needs normalising.
4. INFO: environment.yml is not the executed route and nodefaults was never tested. The README correctly omits it.
