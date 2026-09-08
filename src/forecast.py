"""
Produce final forecast outputs and charts per airport (Epic 5): fits ETS
on the full available history (not a walk-forward fold -- this is the
real forecast, not a backtest) and projects forward FORECAST_HORIZON
months.

Usage:
    python src/forecast.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
IN_PATH = PROCESSED_DIR / "monthly_panel_clean.csv"
FORECAST_HORIZON = 12
AIRPORTS = ["BFS", "BHD", "LDY"]


def fit_ets(values):
    # Same multiplicative-with-additive-fallback logic as evaluation.py's
    # ets_forecast -- BFS's Apr/May 2020 zeros break multiplicative
    # seasonality, since it's fit on the full history here too.
    try:
        return ExponentialSmoothing(values, trend="add", seasonal="mul", seasonal_periods=12).fit()
    except ValueError:
        return ExponentialSmoothing(values, trend="add", seasonal="add", seasonal_periods=12).fit()


def future_periods(last_period, horizon):
    year, month = int(last_period[:4]), int(last_period[4:6])
    periods = []
    for _ in range(horizon):
        month += 1
        if month > 12:
            month, year = 1, year + 1
        periods.append(f"{year}{month:02d}")
    return periods


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_PATH, dtype={"period": str})

    for code in AIRPORTS:
        airport_df = df[df["airport_code"] == code].sort_values("period")
        values = airport_df["total_pax"].values
        periods = airport_df["period"].tolist()

        model = fit_ets(values)
        forecast_values = model.forecast(FORECAST_HORIZON)
        forecast_periods = future_periods(periods[-1], FORECAST_HORIZON)

        history_dates = pd.PeriodIndex(periods, freq="M").to_timestamp()
        forecast_dates = pd.PeriodIndex(forecast_periods, freq="M").to_timestamp()

        plt.figure(figsize=(10, 5))
        plt.plot(history_dates, values, label="Actual")
        plt.plot(forecast_dates, forecast_values, label=f"ETS forecast ({FORECAST_HORIZON}mo)", linestyle="--")
        plt.axvline(history_dates[-1], color="grey", linestyle=":", linewidth=1)
        plt.title(f"{code}: monthly passengers -- actual + {FORECAST_HORIZON}-month forecast")
        plt.ylabel("Total passengers")
        plt.legend()
        plt.tight_layout()
        out_path = REPORTS_DIR / f"{code.lower()}_forecast.png"
        plt.savefig(out_path, dpi=150)
        plt.close()
        print(f"Wrote {out_path}")

        pd.DataFrame({
            "period": forecast_periods,
            "airport_code": code,
            "forecast_total_pax": forecast_values,
        }).to_csv(REPORTS_DIR / f"{code.lower()}_forecast.csv", index=False)


if __name__ == "__main__":
    main()