"""
Clean src/build_panel.py's output into the final analysis-ready panel:

  1. Normalise the two movement columns that CAA re-cased partway through
     the schema change (see docs/data-audit-findings.md) into one column
     each, instead of two mutually-exclusive-by-era columns.
  2. Flag the COVID-19 disruption period as an explicit boolean column,
     rather than leaving models to treat it as ordinary seasonal variation.

Usage:
    python src/clean_panel.py
"""

from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
IN_PATH = PROCESSED_DIR / "monthly_panel.csv"
OUT_PATH = PROCESSED_DIR / "monthly_panel_clean.csv"

# CAA re-cased exactly two Table 05 columns when it changed the airport-name
# column in Apr 2016 (see docs/data-audit-findings.md) -- every other
# movement column kept the same casing across both eras. Confirmed against
# the actual raw files, not assumed: everything else lines up already.
CASING_MERGES = {
    "mov_total_EU_atm": "mov_Total_EU_ATM",
    "mov_scheduled_all_EU_international_atm": "mov_Scheduled_All_EU_International_ATM",
}

# COVID-19 disruption window, set from evidence in the data rather than a
# guessed date range: BFS monthly passengers don't return to anything close
# to the 2015-2019 baseline (~464k/month) until June 2022 (478k) -- Dec
# 2021 (287k) and Jan 2022 (221k, likely compounded by the Omicron wave)
# are both still well below it. April/May 2020 are genuinely zero (the
# first lockdown), not a data gap.
COVID_START, COVID_END = "202003", "202205"  # inclusive


def merge_casing_duplicates(df):
    for canonical, duplicate in CASING_MERGES.items():
        if duplicate not in df.columns:
            continue
        overlap = df[canonical].notna() & df[duplicate].notna()
        if overlap.any():
            raise ValueError(
                f"{canonical} and {duplicate} both have values for the same row(s) -- "
                "that shouldn't happen (they're meant to be mutually exclusive by era). "
                "Check the raw data before merging blindly."
            )
        df[canonical] = df[canonical].fillna(df[duplicate])
        df = df.drop(columns=[duplicate])
    return df


def flag_covid(df):
    df["covid_anomaly"] = df["period"].between(COVID_START, COVID_END)
    return df


def main():
    if not IN_PATH.exists():
        raise SystemExit(f"Expected {IN_PATH} -- run build_panel.py first.")

    df = pd.read_csv(IN_PATH, dtype={"period": str})
    before_cols = set(df.columns)

    df = merge_casing_duplicates(df)
    df = flag_covid(df)

    dropped = before_cols - set(df.columns)
    added = set(df.columns) - before_cols
    print(f"Dropped columns: {sorted(dropped)}")
    print(f"Added columns: {sorted(added)}")
    print(f"covid_anomaly=True for {df['covid_anomaly'].sum()} rows ({COVID_START}-{COVID_END} inclusive)")

    df = df.sort_values(["airport_code", "period"])
    df.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {len(df)} rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
