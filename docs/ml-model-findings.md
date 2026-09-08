# ML Model Findings

Covers Epic 4: feature engineering, and the design decisions behind the XGBoost model (results to be added once run).

## Feature engineering (`src/features.py`)

Built on top of `clean_panel.py`'s output, adds per-airport lag, rolling, and calendar features to `data/processed/monthly_panel_features.csv`:

- **Lags**: `total_pax` shifted 1, 3, 6, and 12 months (12 in particular mirrors the "same month last year" signal seasonal-naive uses, but as a model input rather than the whole prediction).
- **Rolling**: 3- and 6-month rolling mean/std of `total_pax`, computed with `shift(1)` applied *before* the rolling window so a row's own value never leaks into its own "recent average."
- **Calendar**: `month_sin`/`month_cos` (sin/cos-encoded month, so December and January read as adjacent rather than 11 apart) and `year`.

Verified against expected NaN counts (missing values only where there isn't yet enough history, 3 airports × N months of required lookback per feature): `lag1`→3, `lag3`→9, `lag6`→18, `lag12`→36, `roll3_mean`/`roll3_std`→9 each, `roll6_mean`/`roll6_std`→18 each, `month_sin`/`month_cos`/`year`→0. All matched exactly — confirms no off-by-one or leakage in the shift/rolling logic.

## Multi-step forecasting: a leakage problem, found before it caused one

`monthly_panel_features.csv`'s lag/rolling columns are each computed **relative to their own row** (e.g. `lag1` on the March 2020 row is February 2020's value). That's safe for a model trained to predict one month ahead. It is **not** safe as-is for the evaluation harness's 6-month horizon: for a fold forecasting months `origin+1` through `origin+6`, `lag1` on the `origin+3` row would be `origin+2`'s actual value — a real number that hasn't "happened yet" from the forecast origin's point of view. Using it directly would let the model see the answer to an earlier part of its own test before predicting a later part, inflating the evaluation score in a way that wouldn't hold up on genuinely unseen future months.

Worked out which features are actually safe across a 6-month horizon: a feature is only leak-free if the most recent data point it depends on is at or before the forecast origin, for every step of the horizon. That ruled out `lag1`, `lag3`, `roll3_*`, and `roll6_*` as computed in `features.py` (each depends on data too close to the target to be safe at longer horizons) and left the always-safe set: `lag6` and `lag12` (their lookback reaches further back than the horizon), plus the calendar features (known in advance for any future month regardless of data).

## Decision: direct forecasting, single model with horizon as a feature

Two standard ways to produce a 6-month-ahead forecast from a model that treats each row independently:

- **Recursive**: predict month 1, feed that prediction back in as an input for predicting month 2, and so on. Realistic (mirrors production use) but errors compound across the horizon.
- **Direct**: predict each horizon step directly from features anchored at the forecast origin, without feeding forecasts back in.

Went with direct. Rather than training six separate per-step models, `xgb_forecast` trains **one model with the horizon step (1–6) included as a feature**, on a stacked training set built by sliding a synthetic origin across the airport's own training history and generating one example per (origin, horizon step) pair. Features per example, all computed from data at or before that example's origin only: last known value, 3- and 6-month rolling means (of history up to the origin, not the target), same-calendar-month-last-year value, the horizon step itself, and the target month's `month_sin`/`month_cos`. This shares statistical strength across all six horizon steps in one model while keeping every training example leak-free by construction — the same slide-and-check logic used to build the training set is reused unchanged to build the real fold's test features at the end.

Trade-off worth being upfront about: this sacrifices the shorter, more-recent-history features (`lag1`, `lag3`, `roll3`) that `features.py` computed, since those aren't valid across the full horizon. The model has less to work with for near-term steps than a genuinely one-step-ahead model would.

## Results: v1 (raw passenger count as the target)

COVID-excluded, alongside the Epic 3 baselines and ETS for comparison:

| Airport | naive MAE | seasonal_naive MAE | ets MAE | xgb v1 MAE |
|---|---|---|---|---|
| BFS | 92,088.76 | 52,751.72 | **32,946.65** | 65,655.08 |
| BHD | 20,293.47 | 20,441.81 | **11,436.26** | 14,718.48 |
| LDY | 2,122.32 | 2,845.85 | **1,784.05** | 2,966.12 |

Not a clean win, unlike ETS. At BHD, xgb clearly beats both baselines (just not ETS). At BFS it beats naive but loses to the simpler seasonal-naive baseline. At LDY it's the worst of all four models, including naive.

**Diagnosis**: gradient-boosted trees predict a constant value per leaf, learned from the training targets they saw — they structurally cannot predict a value outside the range of `total_pax` seen during training. BFS's recovery has pushed traffic 20-36% above its 2019 baseline by 2024-2026 (see the Epic 2 recovery-vs-baseline plot), meaning later folds' test periods are new all-time highs the model was never trained on a value that large — it can't extrapolate up to meet them, so it systematically undershoots. This lines up with the per-airport pattern: BFS has the strongest trend (worst penalty), BHD's is milder (smaller penalty, so the model's other features still add value over the baselines), and LDY has next to no trend or seasonality — there the model's extra complexity is mostly overfitting to noise rather than hitting an extrapolation ceiling.

## Results: v2 (year-over-year growth ratio as the target)

Fix: instead of training the model to predict the raw passenger count, train it to predict growth relative to the same calendar month last year — `(actual - same_month_last_year) / same_month_last_year` — then reconstruct the forecast as `same_month_last_year × (1 + predicted_growth)`. A growth ratio stays in a roughly stable range even while the underlying level keeps climbing (unlike the raw count), so the tree no longer needs to extrapolate past its training range to produce a new all-time high — it just needs "stronger or weaker than a year ago," which it can express regardless of what absolute levels it saw in training.

_Results to be added once the updated `xgb_forecast` has been re-run through the evaluation harness._
