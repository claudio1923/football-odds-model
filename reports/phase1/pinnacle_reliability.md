# Pinnacle reliability (Phase 1A)

Thresholds (config pinnacle_checks, set before any betting analysis): {'min_coverage': 0.95, 'stale_share_min': 0.1, 'stale_share_multiple': 3, 'overround_range': [1.0, 1.08], 'divergence_p95_max': 0.05, 'min_valid_odds': 1.0, 'quantile_low': 0.05, 'quantile_high': 0.95}.

Full per league x month x market table with all statistics: pinnacle_reliability.csv. A month is suspect if any threshold is breached for a timing present in the file; USA/DNK/SWE files contain closing odds only, so only close is checked there. first_suspect_month and the retention tables use the 1X2 rows. Played matches only.

## Per league summary (1X2)

| league | months | suspect_months | first_suspect_month |
|---|---|---|---|
| D1 | 49 | 5 | 2026-01 |
| DNK | 49 | 6 | 2025-11 |
| E0 | 50 | 5 | 2026-01 |
| F1 | 51 | 5 | 2026-01 |
| I1 | 51 | 5 | 2026-01 |
| I2 | 50 | 8 | 2025-10 |
| N1 | 49 | 7 | 2025-10 |
| P1 | 50 | 5 | 2026-01 |
| SP1 | 51 | 5 | 2026-01 |
| SWE | 49 | 11 | 2025-08 |
| USA | 98 | 11 | 2025-08 |

## Suspect months by reason (1X2; a month can have several reasons)

| league | r | months |
|---|---|---|
| D1 | coverage_close | 5 |
| D1 | coverage_pre | 5 |
| D1 | stale | 1 |
| DNK | coverage_close | 6 |
| E0 | coverage_close | 5 |
| E0 | coverage_pre | 5 |
| F1 | coverage_close | 5 |
| F1 | coverage_pre | 5 |
| I1 | coverage_close | 5 |
| I1 | coverage_pre | 5 |
| I2 | coverage_close | 8 |
| I2 | coverage_pre | 8 |
| I2 | stale | 1 |
| N1 | coverage_close | 6 |
| N1 | coverage_pre | 6 |
| N1 | divergence_close | 1 |
| N1 | stale | 1 |
| P1 | coverage_close | 5 |
| P1 | coverage_pre | 5 |
| SP1 | coverage_close | 5 |
| SP1 | coverage_pre | 5 |
| SWE | coverage_close | 8 |
| SWE | divergence_close | 3 |
| USA | coverage_close | 10 |
| USA | divergence_close | 1 |

## Suspect months in other markets (count)

| league | market | suspect_months |
|---|---|---|
| D1 | ah | 6 |
| D1 | ou25 | 23 |
| E0 | ah | 8 |
| E0 | ou25 | 8 |
| F1 | ah | 6 |
| F1 | ou25 | 6 |
| I1 | ah | 6 |
| I1 | ou25 | 5 |
| I2 | ah | 8 |
| I2 | ou25 | 8 |
| N1 | ah | 8 |
| N1 | ou25 | 8 |
| P1 | ah | 8 |
| P1 | ou25 | 5 |
| SP1 | ah | 6 |
| SP1 | ou25 | 6 |

## Retention (1X2; matches kept, and share of played matches)
Note: (ii) is near 100% only because Avg fills the whole outage window; it is not Pinnacle retention (the adopted rule never substitutes Avg, see sample_retention.md). The first suspect month can come from a divergence breach in a fully covered month (USA, SWE 2025-08): a conservative cut, not the start of the outage.
(i)Pinnacle valid, only months before the first suspect month; (ii) Pinnacle valid in non-suspect months, Avg valid in suspect months; (iii) Pinnacle valid, suspect months excluded. 'pre' rows are empty where the file has no pre columns.

| league | timing | played_matches | first_suspect_month | kept_i_pin_before_first_suspect | kept_ii_pin_reliable_else_avg | kept_iii_pin_excl_suspect_months | share_i_pin_before_first_suspect | share_ii_pin_reliable_else_avg | share_iii_pin_excl_suspect_months |
|---|---|---|---|---|---|---|---|---|---|
| I1 | pre | 1900 | 2026-01 | 1685.0000 | 1899.0000 | 1685.0000 | 0.8868 | 0.9995 | 0.8868 |
| I1 | close | 1900 | 2026-01 | 1686.0000 | 1900.0000 | 1686.0000 | 0.8874 | 1.0000 | 0.8874 |
| I2 | pre | 1900 | 2025-10 | 1572.0000 | 1896.0000 | 1572.0000 | 0.8274 | 0.9979 | 0.8274 |
| I2 | close | 1900 | 2025-10 | 1576.0000 | 1900.0000 | 1576.0000 | 0.8295 | 1.0000 | 0.8295 |
| E0 | pre | 1900 | 2026-01 | 1706.0000 | 1900.0000 | 1706.0000 | 0.8979 | 1.0000 | 0.8979 |
| E0 | close | 1900 | 2026-01 | 1706.0000 | 1900.0000 | 1706.0000 | 0.8979 | 1.0000 | 0.8979 |
| SP1 | pre | 1900 | 2026-01 | 1690.0000 | 1899.0000 | 1690.0000 | 0.8895 | 0.9995 | 0.8895 |
| SP1 | close | 1900 | 2026-01 | 1690.0000 | 1899.0000 | 1690.0000 | 0.8895 | 0.9995 | 0.8895 |
| D1 | pre | 1530 | 2026-01 | 1359.0000 | 1530.0000 | 1359.0000 | 0.8882 | 1.0000 | 0.8882 |
| D1 | close | 1530 | 2026-01 | 1359.0000 | 1530.0000 | 1359.0000 | 0.8882 | 1.0000 | 0.8882 |
| F1 | pre | 1678 | 2026-01 | 1516.0000 | 1678.0000 | 1516.0000 | 0.9035 | 1.0000 | 0.9035 |
| F1 | close | 1678 | 2026-01 | 1516.0000 | 1678.0000 | 1516.0000 | 0.9035 | 1.0000 | 0.9035 |
| N1 | pre | 1530 | 2025-10 | 1287.0000 | 1530.0000 | 1314.0000 | 0.8412 | 1.0000 | 0.8588 |
| N1 | close | 1530 | 2025-10 | 1287.0000 | 1530.0000 | 1314.0000 | 0.8412 | 1.0000 | 0.8588 |
| P1 | pre | 1530 | 2026-01 | 1365.0000 | 1529.0000 | 1365.0000 | 0.8922 | 0.9993 | 0.8922 |
| P1 | close | 1530 | 2026-01 | 1366.0000 | 1530.0000 | 1366.0000 | 0.8928 | 1.0000 | 0.8928 |
| USA | pre | 4583 | 2025-08 |  |  |  |  |  |  |
| USA | close | 4583 | 2025-08 | 3911.0000 | 4580.0000 | 4012.0000 | 0.8534 | 0.9993 | 0.8754 |
| DNK | pre | 963 | 2025-11 |  |  |  |  |  |  |
| DNK | close | 963 | 2025-11 | 849.0000 | 963.0000 | 849.0000 | 0.8816 | 1.0000 | 0.8816 |
| SWE | pre | 1422 | 2025-08 |  |  |  |  |  |  |
| SWE | close | 1422 | 2025-08 | 1104.0000 | 1422.0000 | 1104.0000 | 0.7764 | 1.0000 | 0.7764 |

## All suspect months (1X2)

| league | month | n_matches | pin_pre_coverage | pin_close_coverage | stale_share | overround_pre_median | overround_close_median | divergence_pre_p95 | divergence_close_p95 | suspect_reasons |
|---|---|---|---|---|---|---|---|---|---|---|
| I1 | 2026-01 | 58 | 0.5862 | 0.5517 | 0.0625 | 1.0348 | 1.0300 | 0.0181 | 0.0163 | coverage_pre;coverage_close |
| I1 | 2026-02 | 40 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I1 | 2026-03 | 36 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I1 | 2026-04 | 40 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I1 | 2026-05 | 40 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2025-10 | 43 | 0.7907 | 0.7907 | 0.2941 | 1.0498 | 1.0347 | 0.0240 | 0.0391 | coverage_pre;coverage_close;stale |
| I2 | 2025-11 | 40 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2025-12 | 41 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2026-01 | 38 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2026-02 | 49 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2026-03 | 52 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2026-04 | 41 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| I2 | 2026-05 | 20 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| E0 | 2026-01 | 49 | 0.4898 | 0.4898 | 0.0000 | 1.0350 | 1.0287 | 0.0135 | 0.0116 | coverage_pre;coverage_close |
| E0 | 2026-02 | 42 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| E0 | 2026-03 | 32 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| E0 | 2026-04 | 30 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| E0 | 2026-05 | 41 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| SP1 | 2026-01 | 43 | 0.4186 | 0.4186 | 0.0000 | 1.0344 | 1.0290 | 0.0143 | 0.0158 | coverage_pre;coverage_close |
| SP1 | 2026-02 | 40 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| SP1 | 2026-03 | 36 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| SP1 | 2026-04 | 40 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| SP1 | 2026-05 | 50 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| D1 | 2026-01 | 42 | 0.3571 | 0.3333 | 0.5000 | 1.0352 | 1.0337 | 0.0255 | 0.0372 | coverage_pre;coverage_close;stale |
| D1 | 2026-02 | 35 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| D1 | 2026-03 | 31 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| D1 | 2026-04 | 36 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| D1 | 2026-05 | 27 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| F1 | 2026-01 | 31 | 0.2903 | 0.2903 | 0.0000 | 1.0350 | 1.0286 | 0.0162 | 0.0161 | coverage_pre;coverage_close |
| F1 | 2026-02 | 36 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| F1 | 2026-03 | 31 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| F1 | 2026-04 | 35 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| F1 | 2026-05 | 29 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| N1 | 2025-10 | 28 | 0.9643 | 0.9643 | 0.3333 | 1.0524 | 1.0388 | 0.0191 | 0.0646 | divergence_close;stale |
| N1 | 2025-11 | 34 | 0.5000 | 0.5000 | 0.0000 | 1.0526 | 1.0347 | 0.0151 | 0.0129 | coverage_pre;coverage_close |
| N1 | 2026-01 | 30 | 0.2667 | 0.2667 | 0.0000 | 1.0540 | 1.0359 | 0.0179 | 0.0192 | coverage_pre;coverage_close |
| N1 | 2026-02 | 38 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| N1 | 2026-03 | 32 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| N1 | 2026-04 | 27 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| N1 | 2026-05 | 27 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| P1 | 2026-01 | 33 | 0.3333 | 0.3333 | 0.0000 | 1.0498 | 1.0344 | 0.0111 | 0.0158 | coverage_pre;coverage_close |
| P1 | 2026-02 | 37 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| P1 | 2026-03 | 29 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| P1 | 2026-04 | 38 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| P1 | 2026-05 | 27 | 0.0000 | 0.0000 |  |  |  |  |  | coverage_pre;coverage_close |
| USA | 2025-08 | 54 |  | 1.0000 |  |  | 1.0345 |  | 0.0550 | divergence_close |
| USA | 2025-11 | 19 |  | 0.3158 |  |  | 1.0341 |  | 0.0172 | coverage_close |
| USA | 2026-02 | 19 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-03 | 55 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-04 | 70 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-05 | 74 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-07 | 35 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-08 | 76 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-09 | 73 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-10 | 86 |  | 0.0000 |  |  |  |  |  | coverage_close |
| USA | 2026-11 | 7 |  | 0.0000 |  |  |  |  |  | coverage_close |
| DNK | 2025-11 | 23 |  | 0.0000 |  |  |  |  |  | coverage_close |
| DNK | 2025-12 | 7 |  | 0.0000 |  |  |  |  |  | coverage_close |
| DNK | 2026-02 | 18 |  | 0.0000 |  |  |  |  |  | coverage_close |
| DNK | 2026-03 | 18 |  | 0.0000 |  |  |  |  |  | coverage_close |
| DNK | 2026-04 | 30 |  | 0.0000 |  |  |  |  |  | coverage_close |
| DNK | 2026-05 | 18 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2025-08 | 38 |  | 1.0000 |  |  | 1.0441 |  | 0.0505 | divergence_close |
| SWE | 2025-09 | 24 |  | 1.0000 |  |  | 1.0447 |  | 0.0606 | divergence_close |
| SWE | 2025-10 | 24 |  | 1.0000 |  |  | 1.0456 |  | 0.0727 | divergence_close |
| SWE | 2025-11 | 16 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-04 | 40 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-05 | 41 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-07 | 32 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-08 | 37 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-09 | 26 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-10 | 32 |  | 0.0000 |  |  |  |  |  | coverage_close |
| SWE | 2026-11 | 8 |  | 0.0000 |  |  |  |  |  | coverage_close |
