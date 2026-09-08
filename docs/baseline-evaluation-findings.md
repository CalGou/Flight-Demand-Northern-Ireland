# Baseline & Statistical Model Evaluation Findings

Covers Epic 3: the walk-forward evaluation harness, the naive / seasonal-naive baseline comparison, and the ETS statistical model comparison against those baselines.

## Methodology

`src/evaluation.py` implements walk-forward (rolling-origin) validation rather than a single random train/test split, which isn't valid for time series:

- Each fold trains on all data up to `train_end` and forecasts the next 6 months (`horizon=6`).
- The origin steps forward 6 months between folds (`step=6`), starting once at least 36 months of history are available (`min_train_months=36`).
- This produced 17 folds across the Jan 2015–Jun 2026 panel, evaluated independently per airport (BFS, BHD, LDY).
- Metrics: MAE, RMSE, and MAPE (MAPE excludes rows where actual pax = 0, i.e. BFS's genuine Apr/May 2020 lockdown zeros, to avoid division by zero).

Two baseline forecasters were compared:

- **Naive**: repeats the last known monthly value.
- **Seasonal-naive**: repeats the value from the same calendar month one year earlier (falls back to the last known value if that month isn't in the training window).

## Results: full data (all 17 folds, including COVID-disrupted folds)

**Naive**

| Airport | MAE | RMSE | MAPE |
|---|---|---|---|
| BFS | 102,801.64 | 122,688.07 | 67.82% |
| BHD | 26,070.65 | 29,482.08 | 127.33% |
| LDY | 2,846.08 | 3,245.67 | 166.67% |

**Seasonal-naive**: worse than naive across all three airports and all three metrics on the full data.

The worst-performing folds for both models were the same five: `train_end` = 201912, 202006, 202012, 202106, 202112 — i.e. every fold whose training or test window overlaps the COVID-19 disruption period. This confirmed the full-data comparison was being dominated by the pandemic shock rather than reflecting each model's normal-conditions behaviour, so both models were re-evaluated excluding those five folds.

## Results: COVID-excluded (12 folds, `train_end` not in {201912, 202006, 202012, 202106, 202112})

**Naive**

| Airport | MAE | RMSE | MAPE |
|---|---|---|---|
| BFS | 92,088.76 | 112,003.46 | 18.43% |
| BHD | 20,293.47 | 22,908.79 | 10.57% |
| LDY | 2,122.32 | 2,400.20 | 13.69% |

**Seasonal-naive**

| Airport | MAE | RMSE | MAPE |
|---|---|---|---|
| BFS | 52,751.72 | 58,713.08 | 10.35% |
| BHD | 20,441.81 | 21,748.30 | 11.31% |
| LDY | 2,845.85 | 3,251.97 | 17.74% |

## Analysis

The expectation going in was that seasonal-naive would beat plain naive across the board once the pandemic folds were set aside, on the strength of the seasonality confirmed in the Epic 2 EDA. That held for one of the three airports, not all three:

- **BFS**: seasonal-naive wins clearly (MAE down 43%, MAPE nearly halved — 18.43% → 10.35%). BFS is Northern Ireland's high-volume leisure/charter airport, with a strong, repeatable summer-peak/winter-trough pattern that recurs reliably year over year — exactly the condition "same month last year" needs to be a good predictor.
- **BHD**: essentially a wash. MAE is almost identical (20,293 vs 20,442); MAPE is marginally better for naive (10.57% vs 11.31%). BHD's smaller, more business/short-haul-route-driven traffic mix doesn't carry the same calendar-seasonality signal, so last year's figure isn't meaningfully more informative than last month's.
- **LDY**: naive is clearly better on every metric (MAPE 13.69% vs 17.74%). LDY is by far the lowest-volume of the three airports, so month-to-month figures are noisier in relative terms — small operational changes (a route pausing, a schedule change) swing the percentage error more than the extra 12-month lookback helps.

**Conclusion**: there isn't a single baseline that's "best" across all three airports — traffic mix (seasonal/leisure vs. business vs. low-volume/noisy) affects which naive variant wins, and that's worth stating explicitly in the write-up rather than picking one baseline for all three.

**Decision for Epic 3 going forward**: report per-airport baselines — seasonal-naive as the bar to beat at BFS, naive as the bar to beat at BHD and LDY — rather than a single blanket baseline. The ETS statistical model below is compared against each airport's own stronger baseline.

## Statistical model: ETS

`ExponentialSmoothing` (statsmodels), fit independently per fold per airport rather than looked up like the baselines — jointly models level, trend, and seasonal components, updated with exponential weighting so recent observations matter more.

- `trend="add"`, `seasonal_periods=12`.
- Seasonality is fit as `seasonal="mul"` where possible (BFS's swing is proportional to its current level, not a fixed amount — see the Epic 2 EDA calendar-month plots), falling back to `seasonal="add"` when the training window contains a zero value. This matters in practice: BFS's genuine zero-passenger months (Apr/May 2020) sit permanently in the cumulative training window for every fold from mid-2020 onward, since the harness trains on all history up to `train_end`. So most later folds use the additive fallback, not multiplicative — expected behaviour, not a bug.

### Results: full data (all 17 folds, including COVID-disrupted folds)

| Airport | MAE | RMSE | MAPE |
|---|---|---|---|
| BFS | 90,868.43 | 104,082.62 | 122.35% |
| BHD | 22,875.50 | 26,602.52 | 155.65% |
| LDY | 2,652.85 | 3,090.69 | 160.40% |

ETS beats naive on MAE/RMSE for all three airports here, but its MAPE is worse than naive's. That's not evidence ETS is a worse model — MAPE is an unweighted mean across folds, so the handful of COVID-trough folds (near-zero actuals produce enormous percentage errors, e.g. seasonal-naive's worst fold hit 2,490% MAPE at BHD for `train_end=201912`) dominate the average regardless of how good absolute-error performance is elsewhere. This is exactly why the COVID-excluded comparison below is the one that matters, not the full-data numbers.

### Results: COVID-excluded (12 folds)

| Airport | MAE | RMSE | MAPE |
|---|---|---|---|
| BFS | 32,946.65 | 38,495.99 | 6.89% |
| BHD | 11,436.26 | 13,762.91 | 6.13% |
| LDY | 1,784.05 | 2,145.52 | 12.09% |

### Analysis

ETS beats whichever baseline was strongest at each airport, on every metric, with no mixed result to explain away:

| Airport | Best baseline (MAE / MAPE) | ETS (MAE / MAPE) | MAE improvement |
|---|---|---|---|
| BFS | seasonal-naive: 52,751.72 / 10.35% | 32,946.65 / 6.89% | −37.5% |
| BHD | naive: 20,293.47 / 10.57% | 11,436.26 / 6.13% | −43.6% |
| LDY | naive: 2,122.32 / 13.69% | 1,784.05 / 12.09% | −16.0% |

The gain is largest at BFS and BHD and smaller at LDY, which is consistent with the Epic 2 EDA: ETS can only extract more signal than a naive lookup where there's trend/seasonal structure to model in the first place. LDY's calendar-month averages are nearly flat, so even a properly-fit model is mostly tracking noise there — real improvement, but a much smaller one.

**Conclusion**: ETS is the model to report as beating the per-airport baseline bar across all three airports. Satisfies Epic 3's "SARIMA/ETS (or Prophet) model per airport" and "compare baseline vs statistical models" tickets — SARIMA wasn't pursued separately since ETS already gave a clean, unambiguous win everywhere.

## Open items

- None outstanding — the duplicate-print fix and Epic 2 EDA plot review are both confirmed done (see `docs/backlog.md`).
