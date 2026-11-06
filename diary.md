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
