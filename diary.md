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
