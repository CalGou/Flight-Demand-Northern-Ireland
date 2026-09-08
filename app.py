"""
Streamlit dashboard for Flight Demand Northern Ireland (Epic 5, optional).

Usage:
    streamlit run app.py
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "processed" / "monthly_panel_clean.csv"
REPORTS_DIR = BASE_DIR / "reports"

AIRPORT_NAMES = {
    "BFS": "Belfast International",
    "BHD": "George Best Belfast City",
    "LDY": "City of Derry",
}
# Matches the matplotlib default cycle already used in notebooks/01_eda.ipynb,
# so colors read the same way across the whole project.
AIRPORT_COLORS = {"BFS": "#1f77b4", "BHD": "#ff7f0e", "LDY": "#2ca02c"}

# COVID-excluded walk-forward MAE, from docs/baseline-evaluation-findings.md
# and docs/ml-model-findings.md -- this is a summary of offline evaluation
# results, not something the dashboard recomputes live.
MODEL_COMPARISON = pd.DataFrame([
    {"airport_code": "BFS", "model": "Naive", "mae": 92089},
    {"airport_code": "BFS", "model": "Seasonal-naive", "mae": 52752},
    {"airport_code": "BFS", "model": "ETS", "mae": 32947},
    {"airport_code": "BFS", "model": "XGBoost", "mae": 66949},
    {"airport_code": "BHD", "model": "Naive", "mae": 20293},
    {"airport_code": "BHD", "model": "Seasonal-naive", "mae": 20442},
    {"airport_code": "BHD", "model": "ETS", "mae": 11436},
    {"airport_code": "BHD", "model": "XGBoost", "mae": 15940},
    {"airport_code": "LDY", "model": "Naive", "mae": 2122},
    {"airport_code": "LDY", "model": "Seasonal-naive", "mae": 2846},
    {"airport_code": "LDY", "model": "ETS", "mae": 1784},
    {"airport_code": "LDY", "model": "XGBoost", "mae": 3030},
])

st.set_page_config(page_title="Flight Demand Northern Ireland", layout="wide")


@st.cache_data
def load_actuals():
    df = pd.read_csv(DATA_PATH, dtype={"period": str})
    df["date"] = pd.PeriodIndex(df["period"], freq="M").to_timestamp()
    return df


@st.cache_data
def load_forecast(code):
    df = pd.read_csv(REPORTS_DIR / f"{code.lower()}_forecast.csv", dtype={"period": str})
    df["date"] = pd.PeriodIndex(df["period"], freq="M").to_timestamp()
    return df


actuals = load_actuals()

st.title("Flight Demand Northern Ireland")
st.caption(
    "Monthly passenger demand at Northern Ireland's three commercial airports -- "
    "historical data (UK CAA) plus a 12-month ETS forecast."
)

airports = st.multiselect(
    "Airports",
    options=list(AIRPORT_NAMES),
    default=list(AIRPORT_NAMES),
    format_func=lambda code: f"{AIRPORT_NAMES[code]} ({code})",
)
show_forecast = st.checkbox("Show forecast", value=True)
show_covid = st.checkbox("Shade COVID-19 anomaly period", value=True)

if not airports:
    st.info("Select at least one airport.")
    st.stop()

# --- KPI row --------------------------------------------------------------
kpi_cols = st.columns(len(airports))
for col, code in zip(kpi_cols, airports):
    airport_actuals = actuals[actuals.airport_code == code].sort_values("period")
    latest = airport_actuals.iloc[-1]
    prior_year_period = f"{int(latest.period[:4]) - 1}{latest.period[4:]}"
    prior_year = airport_actuals[airport_actuals.period == prior_year_period]

    yoy = None
    if not prior_year.empty and prior_year.iloc[0].total_pax:
        yoy = (latest.total_pax - prior_year.iloc[0].total_pax) / prior_year.iloc[0].total_pax * 100

    col.metric(
        f"{code} — {latest.period[:4]}-{latest.period[4:]}",
        f"{latest.total_pax:,.0f} pax",
        f"{yoy:+.1f}% YoY" if yoy is not None else None,
    )

# --- Main chart -------------------------------------------------------------
fig = go.Figure()
for code in airports:
    color = AIRPORT_COLORS[code]
    airport_actuals = actuals[actuals.airport_code == code].sort_values("period")
    fig.add_trace(go.Scatter(
        x=airport_actuals["date"], y=airport_actuals["total_pax"],
        name=f"{code} actual", mode="lines",
        line=dict(color=color, width=2),
        legendgroup=code,
    ))
    if show_forecast:
        forecast_df = load_forecast(code)
        fig.add_trace(go.Scatter(
            x=forecast_df["date"], y=forecast_df["forecast_total_pax"],
            name=f"{code} forecast", mode="lines",
            line=dict(color=color, width=2, dash="dash"),
            legendgroup=code,
        ))

if show_covid:
    fig.add_vrect(
        x0="2020-03-01", x1="2022-05-31",
        fillcolor="grey", opacity=0.15, line_width=0,
        annotation_text="COVID-19", annotation_position="top left",
    )

fig.update_layout(
    height=520,
    yaxis_title="Total passengers",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    margin=dict(t=60),
)
st.plotly_chart(fig, use_container_width=True)

# --- Model comparison -------------------------------------------------------
st.subheader("Model evaluation (walk-forward, COVID-excluded)")
st.caption(
    "Mean absolute error, lower is better. Full detail in "
    "docs/baseline-evaluation-findings.md and docs/ml-model-findings.md."
)
comparison_view = MODEL_COMPARISON[MODEL_COMPARISON.airport_code.isin(airports)]
pivot = comparison_view.pivot(index="model", columns="airport_code", values="mae").reindex(
    ["Naive", "Seasonal-naive", "ETS", "XGBoost"]
)
st.dataframe(pivot.style.format("{:,.0f}").highlight_min(axis=0, color="#d4edda"), use_container_width=True)
st.caption("ETS (highlighted) is the recommended model at every airport.")
