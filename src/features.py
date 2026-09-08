"""
Feature engineering for the ML models stage (Epic 4): builds lag, rolling,
and calendar features on top of src/clean_panel.py's output.

Usage:
    python src/features.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
IN_PATH = PROCESSED_DIR / "monthly_panel_clean.csv"
OUT_PATH = PROCESSED_DIR / "monthly_panel_features.csv"

LAG_MONTHS = [1, 3, 6, 12]
ROLLING_WINDOWS = [3, 6]


def add_lag_features(df, target_col="total_pax"):
    for lag in LAG_MONTHS:
        df[f"{target_col}_lag{lag}"] = df.groupby("airport_code")[target_col].shift(lag)
    return df


def add_rolling_features(df, target_col="total_pax"):
    for window in ROLLING_WINDOWS:
        # shift(1) before rolling so each row's rolling mean/std only ever
        # looks at months strictly before it -- otherwise the row's own
        # value would leak into its own "recent average", which a real
        # forecast standing at that point in time could never see.
        df[f"{target_col}_roll{window}_mean"] = df.groupby("airport_code")[target_col].transform(
            lambda s: s.shift(1).rolling(window).mean()
        )
        df[f"{target_col}_roll{window}_std"] = df.groupby("airport_code")[target_col].transform(
            lambda s: s.shift(1).rolling(window).std()
        )
    return df


def add_calendar_features(df):
    month = df["period"].str[4:6].astype(int)
    # sin/cos encoding rather than raw month number, so December (12) and
    # January (1) read as adjacent to the model instead of 11 apart.
    df["month_sin"] = np.sin(2 * np.pi * month / 12)
    df["month_cos"] = np.cos(2 * np.pi * month / 12)
    df["year"] = df["period"].str[:4].astype(int)
    return df


def main():
    if not IN_PATH.exists():
        raise SystemExit(f"Expected {IN_PATH} -- run clean_panel.py first.")

    df = pd.read_csv(IN_PATH, dtype={"period": str})
    df = df.sort_values(["airport_code", "period"]).reset_index(drop=True)

    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = add_calendar_features(df)

    new_cols = [
        c for c in df.columns
        if c.startswith("total_pax_lag") or c.startswith("total_pax_roll") or c in ("month_sin", "month_cos", "year")
    ]
    print(f"Added feature columns: {new_cols}")
    print("\nMissing values per new feature (expected at the start of each airport's series, before enough history exists):")
    print(df[new_cols].isna().sum().to_string())

    df.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(df)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()