from dataclasses import dataclass
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

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

    for name, fn in [("naive", naive_forecast), ("seasonal_naive", seasonal_naive_forecast), ("ets", ets_forecast)]:
        scores = evaluate_forecaster(df, fn, make_folds(periods), ["BFS", "BHD", "LDY"])
        print(f"\n{name}:")
        print(scores.groupby("airport_code")[["mae", "rmse", "mape"]].mean().to_string())

    print("\nseasonal_naive worst 10 folds by MAPE:")
    scores_sn = evaluate_forecaster(df, seasonal_naive_forecast, make_folds(periods), ["BFS", "BHD", "LDY"])
    print(scores_sn.sort_values("mape", ascending=False).head(10).to_string())

    for name, fn in [("naive", naive_forecast), ("seasonal_naive", seasonal_naive_forecast), ("ets", ets_forecast)]:
        scores = evaluate_forecaster(df, fn, make_folds(periods), ["BFS", "BHD", "LDY"])
        clean = scores[~scores["train_end"].isin(covid_folds)]
        print(f"\n{name} (excluding COVID-overlapping folds):")
        print(clean.groupby("airport_code")[["mae", "rmse", "mape"]].mean().to_string())

# One implementation detail worth knowing for the write-up, 
# since you'll get asked about it if this goes in a portfolio: 
# for folds whose training window includes Apr/May 2020 
# (which is most folds from mid-2020 onward, 
# since your training window is cumulative from Jan 2015), 
# the multiplicative-seasonal fit fails on those zero values and silently falls back to additive seasonal,
# per the try/except in ets_forecast. That's expected, not a bug
# — but worth a one-line note in the findings doc so it's not a mystery later if someone inspects the model params per fold.