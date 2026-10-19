"""Tests for the walk-forward evaluation harness in src/evaluation.py."""

import math

import numpy as np
import pandas as pd
import pytest

from evaluation import evaluate_forecaster, make_folds, mae, mape, rmse


def monthly_periods(start_year, n):
    return [f"{start_year + i // 12}{i % 12 + 1:02d}" for i in range(n)]


# --- make_folds ------------------------------------------------------------

def test_make_folds_layout():
    periods = monthly_periods(2015, 48)

    folds = make_folds(periods, min_train_months=36, horizon=6, step=6)

    assert len(folds) == 2
    assert folds[0].train_end == "201712"
    assert folds[0].test_periods == monthly_periods(2018, 6)
    assert folds[1].train_end == "201806"
    assert folds[1].test_periods == periods[42:48]


def test_make_folds_never_tests_on_training_months():
    periods = monthly_periods(2015, 138)  # Jan 2015 - Jun 2026, as in the panel

    for fold in make_folds(periods):
        assert all(p > fold.train_end for p in fold.test_periods)


def test_make_folds_returns_nothing_without_enough_history():
    assert make_folds(monthly_periods(2015, 40), min_train_months=36, horizon=6) == []


# --- metrics ---------------------------------------------------------------

def test_error_metrics_against_hand_computed_values():
    actual = [100, 200, 400]
    predicted = [110, 180, 400]  # errors: 10, 20, 0

    assert mae(actual, predicted) == pytest.approx(10.0)
    assert rmse(actual, predicted) == pytest.approx(math.sqrt((100 + 400 + 0) / 3))
    assert mape(actual, predicted) == pytest.approx((10 + 10 + 0) / 3)


def test_perfect_forecast_scores_zero():
    actual = [5, 10, 15]

    assert mae(actual, actual) == 0
    assert rmse(actual, actual) == 0
    assert mape(actual, actual) == 0


# --- evaluate_forecaster ---------------------------------------------------

@pytest.fixture
def panel():
    periods = monthly_periods(2015, 48)
    rows = []
    for code, scale in [("BFS", 1000), ("LDY", 10)]:
        for i, p in enumerate(periods):
            rows.append({"airport_code": code, "period": p, "total_pax": scale * (i + 1)})
    return pd.DataFrame(rows), periods


def test_forecaster_only_sees_one_airports_history_up_to_cutoff(panel):
    df, periods = panel
    folds = make_folds(periods)
    seen = []

    def spy(train_df, test_periods):
        seen.append((train_df["airport_code"].unique().tolist(), train_df["period"].max(), test_periods))
        return [0] * len(test_periods)

    evaluate_forecaster(df, spy, folds, ["BFS", "LDY"])

    assert len(seen) == len(folds) * 2
    for airports, latest_period, test_periods in seen:
        assert len(airports) == 1
        assert latest_period < min(test_periods)  # no look-ahead leakage


def test_evaluate_forecaster_scores_each_fold_and_airport(panel):
    df, periods = panel
    folds = make_folds(periods)

    def off_by_ten(train_df, test_periods):
        actual = df[(df["airport_code"] == train_df["airport_code"].iloc[0])
                    & df["period"].isin(test_periods)].sort_values("period")["total_pax"]
        return (actual + 10).tolist()

    scores = evaluate_forecaster(df, off_by_ten, folds, ["BFS", "LDY"])

    assert len(scores) == len(folds) * 2
    assert set(scores["airport_code"]) == {"BFS", "LDY"}
    assert np.allclose(scores["mae"], 10)
    assert np.allclose(scores["rmse"], 10)


def test_mape_skips_zero_passenger_months(panel):
    # BFS Apr/May 2020 were genuinely zero -- MAPE would divide by zero there.
    df, periods = panel
    folds = make_folds(periods)[:1]
    df.loc[(df["airport_code"] == "BFS") & (df["period"] == folds[0].test_periods[0]), "total_pax"] = 0

    def predict_100(train_df, test_periods):
        return [100] * len(test_periods)

    scores = evaluate_forecaster(df, predict_100, folds, ["BFS"])

    assert np.isfinite(scores["mape"].iloc[0])
