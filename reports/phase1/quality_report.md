# Quality report (Phase 1B)

Rows in matches.parquet: 20836; columns: 98. Rows without a final result excluded (counted below). Unparsed dates: 0 (parse_dates raises otherwise). Nothing is fixed: flags only.

## Flag summary

| flag | rows_flagged |
|---|---|
| qa_exact_duplicate | 0 |
| qa_duplicate_key | 0 |
| qa_team_twice_same_date | 0 |
| qa_result_goals_mismatch | 0 |
| qa_odds_out_of_range | 4 |
| qa_overround_out_of_range | 1 |

## Rows excluded (no final result)

| league | season | n_raw | n_excluded_no_result | n_kept |
|---|---|---|---|---|
| I1 | 2122 | 380 | 0 | 380 |
| I1 | 2223 | 380 | 0 | 380 |
| I1 | 2324 | 380 | 0 | 380 |
| I1 | 2425 | 380 | 0 | 380 |
| I1 | 2526 | 380 | 0 | 380 |
| I2 | 2122 | 380 | 0 | 380 |
| I2 | 2223 | 380 | 0 | 380 |
| I2 | 2324 | 380 | 0 | 380 |
| I2 | 2425 | 380 | 0 | 380 |
| I2 | 2526 | 380 | 0 | 380 |
| E0 | 2122 | 380 | 0 | 380 |
| E0 | 2223 | 380 | 0 | 380 |
| E0 | 2324 | 380 | 0 | 380 |
| E0 | 2425 | 380 | 0 | 380 |
| E0 | 2526 | 380 | 0 | 380 |
| SP1 | 2122 | 380 | 0 | 380 |
| SP1 | 2223 | 380 | 0 | 380 |
| SP1 | 2324 | 380 | 0 | 380 |
| SP1 | 2425 | 380 | 0 | 380 |
| SP1 | 2526 | 380 | 0 | 380 |
| D1 | 2122 | 306 | 0 | 306 |
| D1 | 2223 | 306 | 0 | 306 |
| D1 | 2324 | 306 | 0 | 306 |
| D1 | 2425 | 306 | 0 | 306 |
| D1 | 2526 | 306 | 0 | 306 |
| F1 | 2122 | 380 | 0 | 380 |
| F1 | 2223 | 380 | 0 | 380 |
| F1 | 2324 | 306 | 0 | 306 |
| F1 | 2425 | 306 | 0 | 306 |
| F1 | 2526 | 306 | 0 | 306 |
| N1 | 2122 | 306 | 0 | 306 |
| N1 | 2223 | 306 | 0 | 306 |
| N1 | 2324 | 306 | 0 | 306 |
| N1 | 2425 | 306 | 0 | 306 |
| N1 | 2526 | 306 | 0 | 306 |
| P1 | 2122 | 306 | 0 | 306 |
| P1 | 2223 | 306 | 0 | 306 |
| P1 | 2324 | 306 | 0 | 306 |
| P1 | 2425 | 306 | 0 | 306 |
| P1 | 2526 | 306 | 0 | 306 |
| USA | 2017 | 391 | 0 | 391 |
| USA | 2018 | 408 | 0 | 408 |
| USA | 2019 | 421 | 0 | 421 |
| USA | 2020 | 324 | 0 | 324 |
| USA | 2021 | 472 | 0 | 472 |
| USA | 2022 | 489 | 0 | 489 |
| USA | 2023 | 521 | 0 | 521 |
| USA | 2024 | 522 | 0 | 522 |
| USA | 2025 | 540 | 0 | 540 |
| USA | 2026 | 495 | 0 | 495 |
| DNK | 2021/2022 | 193 | 0 | 193 |
| DNK | 2022/2023 | 193 | 0 | 193 |
| DNK | 2023/2024 | 193 | 0 | 193 |
| DNK | 2024/2025 | 192 | 0 | 192 |
| DNK | 2025/2026 | 192 | 0 | 192 |
| SWE | 2021 | 242 | 0 | 242 |
| SWE | 2022 | 242 | 0 | 242 |
| SWE | 2023 | 240 | 0 | 240 |
| SWE | 2024 | 242 | 0 | 242 |
| SWE | 2025 | 240 | 0 | 240 |
| SWE | 2026 | 216 | 0 | 216 |

## Exact duplicates / same league+date+home+away (qa_duplicates.csv)

_(empty)_

## Team playing twice on one date (qa_team_twice_same_date.csv)

_(empty)_

## Result inconsistent with goals (qa_result_goals_mismatch.csv)

_(empty)_

## Teams and matches per league x season (n*(n-1) shown for all; double round robin applies to leagues without playoffs/split phases; split-phase leagues: ['USA', 'DNK'], report only)

| league | season | teams | matches | min_per_team | median_per_team | max_per_team | n_times_n_minus_1 | matches_minus_n_times_n_minus_1 | playoff_or_split |
|---|---|---|---|---|---|---|---|---|---|
| D1 | 2122 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| D1 | 2223 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| D1 | 2324 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| D1 | 2425 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| D1 | 2526 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| DNK | 2021/2022 | 12 | 193 | 32 | 32 | 33 | 132 | 61 | True |
| DNK | 2022/2023 | 12 | 193 | 32 | 32 | 33 | 132 | 61 | True |
| DNK | 2023/2024 | 12 | 193 | 32 | 32 | 33 | 132 | 61 | True |
| DNK | 2024/2025 | 12 | 192 | 32 | 32 | 32 | 132 | 60 | True |
| DNK | 2025/2026 | 12 | 192 | 32 | 32 | 32 | 132 | 60 | True |
| E0 | 2122 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| E0 | 2223 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| E0 | 2324 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| E0 | 2425 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| E0 | 2526 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| F1 | 2122 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| F1 | 2223 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| F1 | 2324 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| F1 | 2425 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| F1 | 2526 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| I1 | 2122 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I1 | 2223 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I1 | 2324 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I1 | 2425 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I1 | 2526 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I2 | 2122 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I2 | 2223 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I2 | 2324 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I2 | 2425 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| I2 | 2526 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| N1 | 2122 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| N1 | 2223 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| N1 | 2324 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| N1 | 2425 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| N1 | 2526 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| P1 | 2122 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| P1 | 2223 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| P1 | 2324 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| P1 | 2425 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| P1 | 2526 | 18 | 306 | 34 | 34 | 34 | 306 | 0 | False |
| SP1 | 2122 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| SP1 | 2223 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| SP1 | 2324 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| SP1 | 2425 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| SP1 | 2526 | 20 | 380 | 38 | 38 | 38 | 380 | 0 | False |
| SWE | 2021 | 17 | 242 | 2 | 30 | 32 | 272 | -30 | False |
| SWE | 2022 | 17 | 242 | 2 | 30 | 32 | 272 | -30 | False |
| SWE | 2023 | 16 | 240 | 30 | 30 | 30 | 240 | 0 | False |
| SWE | 2024 | 17 | 242 | 2 | 30 | 32 | 272 | -30 | False |
| SWE | 2025 | 16 | 240 | 30 | 30 | 30 | 240 | 0 | False |
| SWE | 2026 | 16 | 216 | 27 | 27 | 27 | 240 | -24 | False |
| USA | 2017 | 22 | 391 | 34 | 35 | 39 | 462 | -71 | True |
| USA | 2018 | 23 | 408 | 34 | 35 | 40 | 506 | -98 | True |
| USA | 2019 | 24 | 421 | 34 | 35 | 38 | 552 | -131 | True |
| USA | 2020 | 26 | 324 | 19 | 25 | 29 | 650 | -326 | True |
| USA | 2021 | 27 | 472 | 34 | 35 | 38 | 702 | -230 | True |
| USA | 2022 | 28 | 489 | 34 | 34 | 37 | 756 | -267 | True |
| USA | 2023 | 29 | 521 | 34 | 36 | 40 | 812 | -291 | True |
| USA | 2024 | 29 | 522 | 34 | 36 | 39 | 812 | -290 | True |
| USA | 2025 | 30 | 540 | 34 | 36 | 40 | 870 | -330 | True |
| USA | 2026 | 30 | 495 | 33 | 33 | 33 | 870 | -375 | True |

## Stage counts per league

| league | stage | matches |
|---|---|---|
| D1 | regular | 1530 |
| DNK | unknown | 963 |
| E0 | regular | 1900 |
| F1 | regular | 1678 |
| I1 | regular | 1900 |
| I2 | regular | 1900 |
| N1 | regular | 1530 |
| P1 | regular | 1530 |
| SP1 | regular | 1900 |
| SWE | regular | 1422 |
| USA | playoff | 160 |
| USA | regular | 4393 |
| USA | unknown | 30 |

## USA stage evidence per season

| season | matches | teams | modal_matches_per_team | expected_regular_matches | regular | playoff | unknown | first_playoff_date | last_date |
|---|---|---|---|---|---|---|---|---|---|
| 2017 | 391 | 22 | 34 | 374.0000 | 374 | 17 | 0 | 2017-10-26 | 2017-12-09 |
| 2018 | 408 | 23 | 34 | 391.0000 | 391 | 17 | 0 | 2018-10-31 | 2018-12-09 |
| 2019 | 421 | 24 | 34 | 408.0000 | 408 | 13 | 0 | 2019-10-19 | 2019-11-10 |
| 2020 | 324 | 26 | 23,24 |  | 294 | 0 | 30 |  | 2020-12-13 |
| 2021 | 472 | 27 | 34 | 459.0000 | 459 | 13 | 0 | 2021-11-20 | 2021-12-11 |
| 2022 | 489 | 28 | 34 | 476.0000 | 476 | 13 | 0 | 2022-10-15 | 2022-11-05 |
| 2023 | 521 | 29 | 34 | 493.0000 | 493 | 28 | 0 | 2023-10-26 | 2023-12-09 |
| 2024 | 522 | 29 | 34 | 493.0000 | 493 | 29 | 0 | 2024-10-23 | 2024-12-07 |
| 2025 | 540 | 30 | 34 | 510.0000 | 510 | 30 | 0 | 2025-10-23 | 2025-12-06 |
| 2026 | 495 | 30 | 33 | 495.0000 | 495 | 0 | 0 |  | 2026-11-02 |

## Odds <= min valid or > odds_max_sane (odds_out_of_range.csv)

Rows flagged: 4.

| league | season | date | home | away | columns |
|---|---|---|---|---|---|
| E0 | 2122 | 2021-12-19 00:00:00 | Newcastle | Man City | odds_ou25_b365_close_over,odds_ou25_b365_close_under |
| F1 | 2425 | 2025-04-19 00:00:00 | Paris SG | Le Havre | odds_ou25_pin_close_over,odds_ou25_pin_close_under,odds_ou25_pin_pre_over,odds_ou25_pin_pre_under |
| D1 | 2425 | 2025-05-10 00:00:00 | Bayern Munich | M'gladbach | odds_ou25_pin_close_over,odds_ou25_pin_close_under,odds_ou25_pin_pre_over,odds_ou25_pin_pre_under |
| SP1 | 2526 | 2025-10-18 00:00:00 | Barcelona | Girona | odds_ou25_pin_close_over,odds_ou25_pin_close_under |

## Overround per source / timing / market per league x season (overround_summary.csv)
Bounds for single-bookmaker rows (pin, b365): [1.0, 1.25] (flag). Max: share below 1.0 reported only. Aggregate by source:

| source | timing | market | n | outside | worst_min | worst_max |
|---|---|---|---|---|---|---|
| avg | close | 1x2 | 20835 | 0.0000 | 0.9287 | 1.4714 |
| avg | close | ah | 13868 | 0.0000 | 1.0257 | 1.1268 |
| avg | close | ou25 | 13868 | 0.0000 | 1.0227 | 1.0869 |
| avg | pre | 1x2 | 13866 | 0.0000 | 0.9939 | 1.0977 |
| avg | pre | ah | 13866 | 0.0000 | 0.6904 | 1.1058 |
| avg | pre | ou25 | 13866 | 0.0000 | 1.0373 | 1.0871 |
| b365 | close | 1x2 | 14996 | 0.0000 | 1.0054 | 1.1456 |
| b365 | close | ah | 13866 | 0.0000 | 1.0128 | 1.1084 |
| b365 | close | ou25 | 13867 | 0.0000 | 1.0179 | 1.0929 |
| b365 | pre | 1x2 | 13862 | 0.0000 | 1.0276 | 1.1667 |
| b365 | pre | ah | 13847 | 0.0000 | 1.0132 | 1.1120 |
| b365 | pre | ou25 | 13862 | 0.0000 | 1.0178 | 1.0846 |
| max | close | 1x2 | 20836 | 0.0000 | 0.4187 | 1.1182 |
| max | close | ah | 13867 | 0.0000 | 0.8182 | 1.0665 |
| max | close | ou25 | 13868 | 0.0000 | 0.8815 | 1.0869 |
| max | pre | 1x2 | 13866 | 0.0000 | 0.5452 | 1.0632 |
| max | pre | ah | 13865 | 0.0000 | 0.5216 | 1.0644 |
| max | pre | ou25 | 13866 | 0.0000 | 0.8609 | 1.0667 |
| pin | close | 1x2 | 18518 | 0.0000 | 1.0005 | 1.0719 |
| pin | close | ah | 12406 | 1.0000 | 0.9998 | 1.0755 |
| pin | close | ou25 | 12342 | 0.0000 | 1.0019 | 1.0792 |
| pin | pre | 1x2 | 12404 | 0.0000 | 1.0203 | 1.0906 |
| pin | pre | ah | 12400 | 0.0000 | 1.0137 | 1.0746 |
| pin | pre | ou25 | 12328 | 0.0000 | 1.0221 | 1.0881 |

## Max rows with overround below 1.0 (report only)

| league | timing | market | n | share_below_1 |
|---|---|---|---|---|
| D1 | close | 1x2 | 1530.0000 | 0.5294 |
| D1 | close | ah | 1530.0000 | 0.4033 |
| D1 | close | ou25 | 1530.0000 | 0.3235 |
| D1 | pre | 1x2 | 1530.0000 | 0.2542 |
| D1 | pre | ah | 1529.0000 | 0.0582 |
| D1 | pre | ou25 | 1530.0000 | 0.0235 |
| DNK | close | 1x2 | 963.0000 | 0.2617 |
| E0 | close | 1x2 | 1900.0000 | 0.5805 |
| E0 | close | ah | 1899.0000 | 0.4044 |
| E0 | close | ou25 | 1900.0000 | 0.3653 |
| E0 | pre | 1x2 | 1900.0000 | 0.2863 |
| E0 | pre | ah | 1900.0000 | 0.0779 |
| E0 | pre | ou25 | 1900.0000 | 0.0495 |
| F1 | close | 1x2 | 1678.0000 | 0.5101 |
| F1 | close | ah | 1678.0000 | 0.3766 |
| F1 | close | ou25 | 1678.0000 | 0.3611 |
| F1 | pre | 1x2 | 1678.0000 | 0.2378 |
| F1 | pre | ah | 1678.0000 | 0.0530 |
| F1 | pre | ou25 | 1678.0000 | 0.0513 |
| I1 | close | 1x2 | 1900.0000 | 0.5084 |
| I1 | close | ah | 1900.0000 | 0.4268 |
| I1 | close | ou25 | 1900.0000 | 0.3753 |
| I1 | pre | 1x2 | 1899.0000 | 0.2643 |
| I1 | pre | ah | 1899.0000 | 0.0527 |
| I1 | pre | ou25 | 1899.0000 | 0.0495 |
| I2 | close | 1x2 | 1900.0000 | 0.2542 |
| I2 | close | ah | 1900.0000 | 0.2068 |
| I2 | close | ou25 | 1900.0000 | 0.1258 |
| I2 | pre | 1x2 | 1899.0000 | 0.0506 |
| I2 | pre | ah | 1899.0000 | 0.0353 |
| I2 | pre | ou25 | 1899.0000 | 0.0142 |
| N1 | close | 1x2 | 1530.0000 | 0.3111 |
| N1 | close | ah | 1530.0000 | 0.2915 |
| N1 | close | ou25 | 1530.0000 | 0.2373 |
| N1 | pre | 1x2 | 1530.0000 | 0.0562 |
| N1 | pre | ah | 1530.0000 | 0.0477 |
| N1 | pre | ou25 | 1530.0000 | 0.0320 |
| P1 | close | 1x2 | 1530.0000 | 0.3425 |
| P1 | close | ah | 1530.0000 | 0.3503 |
| P1 | close | ou25 | 1530.0000 | 0.2699 |
| P1 | pre | 1x2 | 1530.0000 | 0.0536 |
| P1 | pre | ah | 1530.0000 | 0.0490 |
| P1 | pre | ou25 | 1530.0000 | 0.0301 |
| SP1 | close | 1x2 | 1900.0000 | 0.5158 |
| SP1 | close | ah | 1900.0000 | 0.3832 |
| SP1 | close | ou25 | 1900.0000 | 0.3426 |
| SP1 | pre | 1x2 | 1900.0000 | 0.2568 |
| SP1 | pre | ah | 1900.0000 | 0.0574 |
| SP1 | pre | ou25 | 1900.0000 | 0.0437 |
| SWE | close | 1x2 | 1422.0000 | 0.2159 |
| USA | close | 1x2 | 4583.0000 | 0.3026 |

## Missing values per canonical column x league x season
Full table: missing_values.csv. Columns with missing values in at least one league-season (count of league-seasons affected):

| column | league_seasons | missing_total |
|---|---|---|
| ah_line_close | 21 | 6968 |
| ah_line_pre | 26 | 6977 |
| corners_a | 22 | 6969 |
| corners_h | 22 | 6969 |
| fouls_a | 22 | 6969 |
| fouls_h | 22 | 6969 |
| ht_away_goals | 22 | 6969 |
| ht_home_goals | 22 | 6969 |
| ht_result | 22 | 6969 |
| odds_1x2_avg_close_h | 1 | 1 |
| odds_1x2_avg_pre_a | 23 | 6970 |
| odds_1x2_avg_pre_d | 23 | 6970 |
| odds_1x2_avg_pre_h | 23 | 6970 |
| odds_1x2_b365_close_a | 19 | 5839 |
| odds_1x2_b365_close_d | 19 | 5839 |
| odds_1x2_b365_close_h | 20 | 5840 |
| odds_1x2_b365_pre_a | 26 | 6974 |
| odds_1x2_b365_pre_d | 26 | 6974 |
| odds_1x2_b365_pre_h | 26 | 6974 |
| odds_1x2_max_pre_a | 23 | 6970 |
| odds_1x2_max_pre_d | 23 | 6970 |
| odds_1x2_max_pre_h | 23 | 6970 |
| odds_1x2_pin_close_a | 14 | 2318 |
| odds_1x2_pin_close_d | 14 | 2318 |
| odds_1x2_pin_close_h | 14 | 2318 |
| odds_1x2_pin_pre_a | 34 | 8432 |
| odds_1x2_pin_pre_d | 34 | 8432 |
| odds_1x2_pin_pre_h | 34 | 8432 |
| odds_ah_avg_close_away | 21 | 6968 |
| odds_ah_avg_close_home | 21 | 6968 |
| odds_ah_avg_pre_away | 23 | 6970 |
| odds_ah_avg_pre_home | 23 | 6970 |
| odds_ah_b365_close_away | 23 | 6970 |
| odds_ah_b365_close_home | 23 | 6970 |
| odds_ah_b365_pre_away | 28 | 6989 |
| odds_ah_b365_pre_home | 28 | 6989 |
| odds_ah_max_close_away | 22 | 6969 |
| odds_ah_max_close_home | 22 | 6969 |
| odds_ah_max_pre_away | 24 | 6971 |
| odds_ah_max_pre_home | 24 | 6971 |
| odds_ah_pin_close_away | 31 | 8430 |
| odds_ah_pin_close_home | 31 | 8430 |
| odds_ah_pin_pre_away | 37 | 8436 |
| odds_ah_pin_pre_home | 37 | 8436 |
| odds_ou25_avg_close_over | 21 | 6968 |
| odds_ou25_avg_close_under | 21 | 6968 |
| odds_ou25_avg_pre_over | 23 | 6970 |
| odds_ou25_avg_pre_under | 23 | 6970 |
| odds_ou25_b365_close_over | 21 | 6968 |
| odds_ou25_b365_close_under | 21 | 6968 |
| odds_ou25_b365_pre_over | 26 | 6974 |
| odds_ou25_b365_pre_under | 26 | 6974 |
| odds_ou25_max_close_over | 21 | 6968 |
| odds_ou25_max_close_under | 21 | 6968 |
| odds_ou25_max_pre_over | 23 | 6970 |
| odds_ou25_max_pre_under | 23 | 6970 |
| odds_ou25_pin_close_over | 39 | 8491 |
| odds_ou25_pin_close_under | 39 | 8491 |
| odds_ou25_pin_pre_over | 46 | 8506 |
| odds_ou25_pin_pre_under | 46 | 8506 |
| red_a | 22 | 6969 |
| red_h | 22 | 6969 |
| referee | 56 | 18936 |
| season_note | 60 | 20512 |
| shots_a | 22 | 6969 |
| shots_h | 22 | 6969 |
| sot_a | 22 | 6969 |
| sot_h | 22 | 6969 |
| yellow_a | 22 | 6969 |
| yellow_h | 22 | 6969 |

## Near-duplicate team names (for your decision; team_aliases.yaml is empty)

| league | name_a | name_b | ratio |
|---|---|---|---|
| I2 | Reggiana | Reggina | 0.9330 |
