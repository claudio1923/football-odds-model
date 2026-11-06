# football-odds-model

Local Python project for pre-match football betting models (markets: 1X2, Asian handicap, goal totals). Historical data comes from football-data.co.uk CSV files. The project covers market math, historical odds analysis, a time-decayed Dixon-Coles Poisson model, evaluation and a betting backtest, built phase by phase. All configuration lives in `config/config.yaml`; raw data under `data/raw` is read-only and protected by a SHA-256 manifest.

## Environment

```
conda env create -f environment.yml
conda run -n fbmodel python -m pip install -e .
```

## Tests

```
conda run -n fbmodel python -m pytest -q
```
