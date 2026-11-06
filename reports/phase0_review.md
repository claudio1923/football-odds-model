# Phase 0 review

Verdict: all checkable criteria PASS; push-dependent criteria PENDING. Outputs below are quoted from commands run in Git Bash.

## 1. Preflight tools: PASS
`git --version; conda --version; gh auth status`
```
git version 2.54.0.windows.1
conda 4.13.0
  ✓ Logged in to github.com account claudio1923 (keyring)
```

## 2. Env fbmodel and lock file: PASS
`conda env list`
```
fbmodel                  C:\Users\Claud\anaconda3\envs\fbmodel
```
`grep -n -i "fallback" diary.md` (line 13): "`conda env create -f environment.yml` (conda 4.13.0, classic solver) was still solving after more than 15 minutes. It was stopped and the documented fallback was used: `conda create -n fbmodel -c conda-forge python=3.11 pip -y`, then `python -m pip install` ..."

`grep -c "@ file" requirements.lock.txt` -> `0`; absolute-path grep -> no hits; `wc -l` -> `34 requirements.lock.txt`.

## 3. Tests: PASS
`conda run -n fbmodel python -m pytest -q`
```
..................                                                       [100%]
18 passed in 0.80s
```

## 4. Project tree (depth 3): PASS
`find . -maxdepth 3` with .git, <local-tool-dir>, __pycache__, .pytest_cache, *.egg-info excluded
```
./<rules-file>  ./README.md  ./diary.md  ./environment.yml  ./pyproject.toml  ./requirements.lock.txt
./config/config.yaml
./data/interim/.gitkeep  ./data/processed/.gitkeep  ./data/raw/.gitkeep
./notebooks/.gitkeep  ./reports/.gitkeep  ./scripts/.gitkeep
./src/fbmodel/__init__.py  ./src/fbmodel/config.py  ./src/fbmodel/io_guard.py
./tests/.gitkeep  ./tests/fixtures/.gitkeep  ./tests/test_config.py  ./tests/test_io_guard.py
```

## 5. Single commit and authorship: PASS
`git log --format="%an <%ae>%n%B"` and `git rev-list --count HEAD`
```
claudio1923 <claudioandreassi23@gmail.com>
Phase 0: project skeleton

1
```
No trailers.

## 6. commit-msg hook: PASS
File exists, executable. Run directly on temp files (no git commit):
```
[forbidden-term message] rc=1
[forbidden-term message] rc=1
[forbidden-term message] rc=1
[Phase 0: clean msg] rc=0
```
Hook regex: `(forbidden-term list, see hook)` (case-insensitive).

## 7. Forbidden-term grep: PASS
`git grep -i -n -E <forbidden-terms>` -> no output, `rc=1`.

## 8. Tracked files, excludes, remote: PASS
`git ls-files` shows no <rules-file>, no <local-tool-dir>/; under data/ only `data/{interim,processed,raw}/.gitkeep`.
`.git/info/exclude` ends with `<rules-file>` and `<local-tool-dir>/`. `git remote -v` -> empty (no remote yet). `git status --short` -> clean. `git check-ignore -v data/raw/x.csv` -> `.gitignore:1:data/**`; reports/a.md and diary.md not ignored.

## 9. Code vs spec: PASS (with minor notes)
- config.py: paths resolved via `(PROJECT_ROOT / Path(v)).resolve()`; required top-level keys (paths, random_seed, data_source) and path keys (raw, interim, processed, reports, manifest) raise KeyError; no default values. Tests cover absolute paths and missing keys.
- io_guard.py: `safe_write_path` resolves then rejects raw dir or children (test `test_safe_write_path_rejects_dotdot_into_raw` exists); `make_read_only` uses `os.chmod(path, stat.S_IREAD)`; `sha256_file` chunked; `verify_raw_manifest` raises FileNotFoundError / ValueError.
- .gitignore: `data/**`, `!data/**/`, `!data/**/.gitkeep`; reports/ and diary.md not ignored (verified).
- pyproject: setuptools, `where = ["src"]`, `testpaths = ["tests"]`.
- config.yaml: paths, `random_seed: 42`, `data_source:  # TODO_PHASE1`.
- README: no tool mention (grep in item 7 empty).
- <rules-file> (read from disk): Fixed rules 1-8 present, matching the spec text.

## 10. Push-dependent criteria: PENDING
Tracking of origin/main, nothing to push, report pushed: to be verified by the owner after push. Currently `git status -sb` -> `## main` (no upstream).

## Defects
- Low: `data_source:` is null in config.yaml; `load_config` only checks key presence, so a null value passes (expected until Phase 1).
- Low: `config.py` resolves paths against the package-derived PROJECT_ROOT, not the config file location, so a custom `path` argument still resolves relative to the project root. Acceptable per spec.
- Low: `make_read_only` on Windows only sets the read-only attribute, which does not block deletion; and on a directory it has limited effect.
- Info: README says `conda env create` while diary documents the fallback that was actually used.
- No high or medium defects found.
