"""
Join the two raw CAA extracts (passengers, movements) from
src/ingest_caa_data.py into a single tidy monthly panel, one row per
airport x period.

Usage:
    python src/build_panel.py
"""

import re
from pathlib import Path

import pandas as pd

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
PAX_PATH = PROCESSED_DIR / "passengers_monthly_raw.csv"
MOV_PATH = PROCESSED_DIR / "movements_monthly_raw.csv"
OUT_PATH = PROCESSED_DIR / "monthly_panel.csv"

EXPECTED_AIRPORTS = {"BFS", "BHD", "LDY"}


def load_dedup(path, label):
    df = pd.read_csv(path, dtype={"period": str})
    before = len(df)
    # Safety net: keep the last-seen row per (airport, period), in case a
    # period was pulled twice or CAA republished a corrected figure.
    df = df.drop_duplicates(subset=["airport_code", "period"], keep="last")
    dropped = before - len(df)
    if dropped:
        print(f"{label}: dropped {dropped} duplicate (airport, period) rows")
    return df


PERIOD_RE = re.compile(r"^\d{6}$")  # the one true format: YYYYMM, e.g. 201501


def completeness_report(panel):
    period_values = panel["period"].astype(str).unique()
    all_periods = sorted(p for p in period_values if PERIOD_RE.match(p))
    malformed = sorted(p for p in period_values if not PERIOD_RE.match(p))

    if malformed:
        # These are real anomalies worth looking at directly -- surfaced
        # separately rather than folded into the missing-data check below,
        # where they'd otherwise show up as bogus "missing" entries for
        # every airport (every airport is "missing" data under a period
        # value that was never real in the first place).
        print(f"\n{len(malformed)} malformed period value(s) found in the data (not YYYYMM) -- ignored for the completeness check below, but worth checking data/raw/ for the release that produced them:")
        for p in malformed:
            rows = panel[panel["period"].astype(str) == p]
            print(f"  {p!r} -- airports: {sorted(rows['airport_code'].unique())}")

    if not all_periods:
        print("\nNo well-formed periods found -- nothing to check.")
        return

    print(f"\nPeriod range: {all_periods[0]} to {all_periods[-1]} ({len(all_periods)} months)")

    expected = {(a, p) for a in EXPECTED_AIRPORTS for p in all_periods}
    have_pax = {(r.airport_code, r.period) for r in panel.itertuples() if pd.notna(r.total_pax)}
    have_mov = {
        (r.airport_code, r.period)
        for r in panel.itertuples()
        if any(pd.notna(getattr(r, c)) for c in panel.columns if c.startswith("mov_"))
    }

    missing_pax = sorted(expected - have_pax)
    missing_mov = sorted(expected - have_mov)

    if missing_pax:
        print(f"\nMissing passenger data for {len(missing_pax)} (airport, period) combos:")
        for a, p in missing_pax:
            print(f"  {a} {p}")
    else:
        print("\nNo missing passenger data across the full period range.")

    if missing_mov:
        print(f"\nMissing movement data for {len(missing_mov)} (airport, period) combos:")
        for a, p in missing_mov:
            print(f"  {a} {p}")
    else:
        print("No missing movement data across the full period range.")

    print(
        "\nIf anything's listed above, it's almost certainly one of the "
        "download links that failed even after retries when you ran "
        "ingest_caa_data.py -- just re-run it (already-downloaded files are "
        "cached, so it'll only retry what's missing), then re-run this script."
    )


def main():
    if not PAX_PATH.exists() or not MOV_PATH.exists():
        raise SystemExit(f"Expected {PAX_PATH.name} and {MOV_PATH.name} in {PROCESSED_DIR} -- run ingest_caa_data.py first.")

    pax = load_dedup(PAX_PATH, "passengers")
    mov = load_dedup(MOV_PATH, "movements")

    # Movement table's non-key columns vary by CAA release; keep them all,
    # prefixed so they're clearly distinct from the passenger columns.
    mov_value_cols = [c for c in mov.columns if c not in ("airport_code", "airport_name", "period")]
    mov = mov.rename(columns={c: f"mov_{c}" for c in mov_value_cols})

    panel = pd.merge(
        pax,
        mov,
        on=["airport_code", "airport_name", "period"],
        how="outer",
    ).sort_values(["airport_code", "period"])

    panel.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(panel)} rows to {OUT_PATH}")

    completeness_report(panel)


if __name__ == "__main__":
    main()
