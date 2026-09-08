# Baseline Evaluation Findings

Covers Epic 3 tickets: the walk-forward evaluation harness and the naive / seasonal-naive baseline comparison.

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

**Decision for Epic 3 going forward**: report per-airport baselines — seasonal-naive as the bar to beat at BFS, naive as the bar to beat at BHD and LDY — rather than a single blanket baseline. The upcoming SARIMA/ETS models should be compared against each airport's own stronger baseline.

## Open items

- Confirm the duplicate-print indentation fix in `src/evaluation.py` (the `scores = evaluate_forecaster(...)` / print block was originally inside the `for name, fn in [...]` loop, printing the same worst-10-folds table twice).
- Epic 2's EDA plots (trend, seasonality, airport share, COVID recovery) were reported done but not yet reviewed together — worth a quick look to visually confirm the "BFS is more seasonal than BHD/LDY" explanation above before treating Epic 2 as fully closed.
