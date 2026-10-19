"""Tests for src/clean_panel.py: the casing merge and the COVID flag."""

import numpy as np
import pandas as pd
import pytest

from clean_panel import flag_covid, merge_casing_duplicates


def test_casing_duplicates_merge_into_one_column():
    # Old-schema rows (pre-Apr 2016) use one casing, new-schema rows the other.
    df = pd.DataFrame({
        "period": ["201603", "201604"],
        "mov_total_EU_atm": [100.0, np.nan],
        "mov_Total_EU_ATM": [np.nan, 200.0],
        "mov_scheduled_all_EU_international_atm": [10.0, np.nan],
        "mov_Scheduled_All_EU_International_ATM": [np.nan, 20.0],
    })

    out = merge_casing_duplicates(df)

    assert out["mov_total_EU_atm"].tolist() == [100.0, 200.0]
    assert out["mov_scheduled_all_EU_international_atm"].tolist() == [10.0, 20.0]
    assert "mov_Total_EU_ATM" not in out.columns
    assert "mov_Scheduled_All_EU_International_ATM" not in out.columns


def test_casing_merge_refuses_overlapping_values():
    # Both casings populated on the same row means the eras aren't mutually
    # exclusive after all -- the function should stop rather than pick one.
    df = pd.DataFrame({
        "mov_total_EU_atm": [100.0],
        "mov_Total_EU_ATM": [999.0],
    })

    with pytest.raises(ValueError, match="both have values"):
        merge_casing_duplicates(df)


def test_casing_merge_is_a_no_op_when_duplicate_column_absent():
    df = pd.DataFrame({"mov_total_EU_atm": [1.0, 2.0]})

    out = merge_casing_duplicates(df.copy())

    pd.testing.assert_frame_equal(out, df)


# Dates pinned here rather than imported from clean_panel, so an accidental
# change to the evidence-based window (see docs/data-audit-findings.md) fails.
@pytest.mark.parametrize("period, expected", [
    ("202002", False),        # month before the window
    ("202003", True),         # first month, inclusive
    ("202104", True),         # middle
    ("202205", True),         # last month, inclusive
    ("202206", False),        # month after the window
])
def test_covid_flag_window_boundaries(period, expected):
    df = pd.DataFrame({"period": [period]})

    assert bool(flag_covid(df)["covid_anomaly"].iloc[0]) is expected
