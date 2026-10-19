"""Tests for src/features.py: lag and rolling features must not leak."""

import numpy as np
import pandas as pd
import pytest

from features import add_calendar_features, add_lag_features, add_rolling_features


@pytest.fixture
def two_airports():
    return pd.DataFrame({
        "airport_code": ["BFS"] * 4 + ["LDY"] * 4,
        "period": ["202401", "202402", "202403", "202404"] * 2,
        "total_pax": [10, 20, 30, 40, 1, 2, 3, 4],
    })


def test_lags_do_not_bleed_across_airports(two_airports):
    out = add_lag_features(two_airports)

    # LDY's first month has no history of its own, so its lag-1 must be
    # missing rather than BFS's last value.
    assert np.isnan(out.loc[4, "total_pax_lag1"])
    assert out.loc[5, "total_pax_lag1"] == 1


def test_rolling_mean_excludes_the_current_month(two_airports):
    out = add_rolling_features(two_airports)

    # BFS Apr's 3-month mean is Jan-Mar (10, 20, 30), not Feb-Apr.
    assert out.loc[3, "total_pax_roll3_mean"] == pytest.approx(20)
    assert np.isnan(out.loc[2, "total_pax_roll3_mean"])


def test_december_and_january_are_neighbours_in_calendar_encoding():
    df = pd.DataFrame({"period": ["202412", "202501", "202506"]})

    out = add_calendar_features(df)
    coords = out[["month_sin", "month_cos"]].to_numpy()

    dec_to_jan = np.linalg.norm(coords[0] - coords[1])
    dec_to_jun = np.linalg.norm(coords[0] - coords[2])
    assert dec_to_jan < dec_to_jun
    assert out["year"].tolist() == [2024, 2025, 2025]
