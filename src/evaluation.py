from dataclasses import dataclass
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from xgboost import XGBRegressor

@dataclass
class Fold:
    train_end: str       # last period (YYYYMM) included in training
    test_periods: list   # the periods to predict and score against


def make_folds(all_periods, min_train_months=36, horizon=6, step=6):
    """
    Walk-forward folds over a sorted list of YYYYMM period strings.

    min_train_months: don't start testing until the model has at least this
        much history to train on (36 = 3 years, enough to see a few
        seasonal cycles before being judged).
    horizon: how many months ahead each fold predicts (6, matching the
        project's stated 6-12 month forecast target).
    step: how far to slide the training cutoff forward between folds (6 =
        non-overlapping folds; a smaller step gives more folds but each
        one shares more data with its neighbours).
    """
    folds = []
    start_idx = min_train_months
    while start_idx + horizon <= len(all_periods):
        train_end = all_periods[start_idx - 1]
        test_periods = all_periods[start_idx: start_idx + horizon]
        folds.append(Fold(train_end, test_periods))
        start_idx += step
    return folds

def mae(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    return np.mean(np.abs(actual - predicted))


def rmse(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    return np.sqrt(np.mean((actual - predicted) ** 2))


def mape(actual, predicted):
    actual, predicted = np.array(actual), np.array(predicted)
    return np.mean(np.abs((actual - predicted) / actual)) * 100

def ets_forecast(train_df, test_periods):
    values = train_df.sort_values("period")["total_pax"].values

    try:
        model = ExponentialSmoothing(
            values,
            trend="add",
            seasonal="mul",
            seasonal_periods=12,
        ).fit()
    except ValueError:
        # Multiplicative seasonality requires every training value to be
        # strictly positive -- BFS has genuine zero-passenger months (Apr/May
        # 2020, first COVID lockdown), which breaks it for any fold whose
        # training window reaches that far. Additive seasonality tolerates
        # zeros fine; it just models the seasonal swing as a fixed amount
        # rather than a proportion of the current level.
        model = ExponentialSmoothing(
            values,
            trend="add",
            seasonal="add",
            seasonal_periods=12,
        ).fit()

    return model.forecast(len(test_periods))

def evaluate_forecaster(df, forecast_fn, folds, airport_codes, target_col="total_pax"):
    """
    df: the full panel (must have airport_code, period, and target_col)
    forecast_fn(train_df, test_periods) -> list of predictions, one per
        test period, in the same order as test_periods. train_df is
        already filtered to a single airport's rows up to the fold's
        training cutoff.
    folds: list of Fold objects from make_folds()
    airport_codes: e.g. ["BFS", "BHD", "LDY"]
    """
    rows = []
    for fold in folds:
        for code in airport_codes:
            airport_df = df[df["airport_code"] == code].sort_values("period")
            train_df = airport_df[airport_df["period"] <= fold.train_end]
            test_df = airport_df[airport_df["period"].isin(fold.test_periods)].sort_values("period")

            actual = test_df[target_col].values
            predicted = forecast_fn(train_df, fold.test_periods)

            nonzero = actual != 0
            rows.append({
                "train_end": fold.train_end,
                "airport_code": code,
                "mae": mae(actual, predicted),
                "rmse": rmse(actual, predicted),
                "mape": mape(actual[nonzero], np.array(predicted)[nonzero]) if nonzero.any() else float("nan"),
            })
    return pd.DataFrame(rows)

FEATURE_COLS = ["level", "roll3_mean", "roll6_mean", "same_month_last_year", "horizon", "month_sin", "month_cos"]


def _make_feature_row(lookup, values, origin_idx, target_period, horizon_step):
    """Build one feature row for forecasting `target_period`, which is
    `horizon_step` months ahead of `origin_idx`. Every input here comes
    from `values` at or before origin_idx, or from the target month's own
    calendar position -- never from the target's actual passenger count."""
    year, month = int(target_period[:4]), int(target_period[4:6])
    same_month_last_year_period = f"{year - 1}{target_period[4:6]}"
    same_month_last_year = lookup.get(same_month_last_year_period)
    if same_month_last_year is None:
        return None

    return {
        "level": values[origin_idx],
        "roll3_mean": values[max(0, origin_idx - 2): origin_idx + 1].mean(),
        "roll6_mean": values[max(0, origin_idx - 5): origin_idx + 1].mean(),
        "same_month_last_year": same_month_last_year,
        "horizon": horizon_step,
        "month_sin": np.sin(2 * np.pi * month / 12),
        "month_cos": np.cos(2 * np.pi * month / 12),
    }


def xgb_forecast(train_df, test_periods):
    train_df = train_df.sort_values("period").reset_index(drop=True)
    periods = train_df["period"].tolist()
    values = train_df["total_pax"].values
    lookup = dict(zip(periods, values))

    X_train, y_train = [], []
    for origin_idx in range(len(values)):
        for horizon_step in range(1, 7):
            target_idx = origin_idx + horizon_step
            if target_idx >= len(values):
                break
            row = _make_feature_row(lookup, values, origin_idx, periods[target_idx], horizon_step)
            if row is None or row["same_month_last_year"] == 0:
                # A zero base (BFS Apr/May 2020) makes the growth ratio
                # undefined -- skip rather than divide by zero.
                continue
            # Predict growth relative to the same month last year, not the
            # raw passenger count. A tree-based model can't extrapolate
            # past the range of values it was trained on, and BFS in
            # particular keeps setting new all-time highs post-COVID. A
            # year-over-year growth ratio stays in a roughly stable range
            # even while the underlying level keeps climbing, so the model
            # only ever has to learn "stronger or weaker than a year ago"
            # -- something it can express regardless of the absolute level.
            growth = (values[target_idx] - row["same_month_last_year"]) / row["same_month_last_year"]
            X_train.append(row)
            y_train.append(growth)

    X_train = pd.DataFrame(X_train, columns=FEATURE_COLS)
    model = XGBRegressor(n_estimators=200, max_depth=3, learning_rate=0.05)
    model.fit(X_train, y_train)

    origin_idx = len(values) - 1
    X_test, baselines = [], []
    for horizon_step, target_period in enumerate(test_periods, start=1):
        row = _make_feature_row(lookup, values, origin_idx, target_period, horizon_step)
        if row is None:
            X_test.append({c: np.nan for c in FEATURE_COLS})
            baselines.append(values[origin_idx])
        else:
            X_test.append(row)
            baselines.append(row["same_month_last_year"])
    X_test = pd.DataFrame(X_test, columns=FEATURE_COLS)

    predicted_growth = model.predict(X_test)
    baselines = np.array(baselines)
    reconstructed = baselines * (1 + predicted_growth)
    # Zero-baseline fold (test period one year after BFS's Apr/May 2020
    # zeros): baseline * anything is degenerate, fall back to the last
    # known level instead.
    return np.where(baselines != 0, reconstructed, values[origin_idx])

if __name__ == "__main__":
    def naive_forecast(train_df, test_periods):
        last_value = train_df["total_pax"].iloc[-1]
        return [last_value] * len(test_periods)

    def seasonal_naive_forecast(train_df, test_periods):
        lookup = train_df.set_index("period")["total_pax"]
        predictions = []
        for period in test_periods:
            year, month = int(period[:4]), period[4:]
            lookback_period = f"{year - 1}{month}"
            predictions.append(lookup.get(lookback_period, train_df["total_pax"].iloc[-1]))
        return predictions

    df = pd.read_csv("../data/processed/monthly_panel_clean.csv", dtype={"period": str})
    periods = sorted(df["period"].unique())
    covid_folds = {"201912", "202006", "202012", "202106", "202112"}

    for name, fn in [("naive", naive_forecast), ("seasonal_naive", seasonal_naive_forecast), ("ets", ets_forecast), ("xgb", xgb_forecast)]:
        scores = evaluate_forecaster(df, fn, make_folds(periods), ["BFS", "BHD", "LDY"])
        print(f"\n{name}:")
        print(scores.groupby("airport_code")[["mae", "rmse", "mape"]].mean().to_string())

    print("\nseasonal_naive worst 10 folds by MAPE:")
    scores_sn = evaluate_forecaster(df, seasonal_naive_forecast, make_folds(periods), ["BFS", "BHD", "LDY"])
    print(scores_sn.sort_values("mape", ascending=False).head(10).to_string())

    for name, fn in [("naive", naive_forecast), ("seasonal_naive", seasonal_naive_forecast), ("ets", ets_forecast), ("xgb", xgb_forecast)]:
        scores = evaluate_forecaster(df, fn, make_folds(periods), ["BFS", "BHD", "LDY"])
        clean = scores[~scores["train_end"].isin(covid_folds)]
        print(f"\n{name} (excluding COVID-overlapping folds):")
        print(clean.groupby("airport_code")[["mae", "rmse", "mape"]].mean().to_string())