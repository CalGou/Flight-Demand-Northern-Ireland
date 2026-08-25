# Flight Demand Northern Ireland — Project Parameters

**Type:** Self-directed portfolio project
**Owner:** Callum Gourley
**Last updated:** 25 August 2026 (revised)

## 1. Purpose

A self-directed data science project to demonstrate end-to-end analytical and forecasting skills — data sourcing, cleaning, exploratory analysis, time-series/ML modelling, and presentation of results — using a real, regionally-specific dataset. Intended as a portfolio piece to accompany graduate developer/analyst job applications, showing applied statistics and software engineering practice rather than a toy dataset.

## 2. Objectives

- Build a reproducible forecasting model that predicts monthly passenger numbers and flight movements at Northern Ireland's three commercial airports.
- Identify the key drivers of demand (seasonality, route mix, economic conditions, one-off shocks) through exploratory analysis.
- Produce a clean, documented codebase and write-up suitable for a GitHub portfolio and technical interview discussion.

## 3. Scope

**In scope:**

- Airports: Belfast International (BFS), George Best Belfast City (BHD), City of Derry (LDY)
- Metrics: monthly terminal passengers and air transport movements (ATMs) per airport; route/destination breakdown where available
- Time horizon: **January 2015 through the most recent available month**, forecasting 6–12 months ahead. Confirmed by the data audit (see `docs/data-audit-findings.md`): CAA's Table 09/Table 05 CSVs are machine-readable from Jan 2015 onward with a consistent schema; 1990–2014 and earlier exist only as scanned PDFs, not worth transcribing for this project.
- Forecasting approaches: statistical time-series methods and tree-based ML models

**Out of scope (for v1):**

- Airports outside Northern Ireland (e.g. Dublin) — may be added later as a benchmark/comparator, not a primary target
- Cargo-only traffic and general aviation
- Real-time/live prediction serving — this is a batch, retrospective modelling exercise

## 4. Data Sources

**Primary:**

- **UK CAA "UK Airport Data"** — official monthly and annual airport statistics tables published by the Civil Aviation Authority, covering individual UK airports including all three NI airports, from the 1990s through 2026. Published under the Open Government Licence. This should be the backbone dataset for passenger numbers and movements. ([caa.co.uk](https://www.caa.co.uk/data-and-analysis/uk-aviation-market/airports/uk-airport-data/))

**Candidate supplementary sources (to confirm availability/granularity once data pull starts):**

- NISRA/ONS economic indicators (NI GDP, employment, tourism spend) as demand-driver features
- Tourism NI visitor statistics
- Route-level schedule data (OAG, Flightradar24, or airline-published schedules) if route-level modelling is pursued
- Met Office historical weather data, if weather-related disruption is tested as a feature
- Known shock/event calendar (COVID-19 travel restrictions, fuel price spikes, airline entries/exits e.g. Wizz Air, Ryanair route changes) as categorical/dummy features

Data audit complete — see `docs/data-audit-findings.md` for the full write-up. Each monthly CAA release only contains that month plus the prior month (no bulk time series file), so the ingestion script (`src/ingest_caa_data.py`) walks every monthly page from Jan 2015 to present individually.

## 5. Target Variable & Granularity

- Primary target: monthly total passengers per airport (arrivals + departures)
- Secondary target: monthly air transport movements per airport
- Stretch target: route-level passenger volumes, if data quality supports it

## 6. Methodology

1. **Data collection & cleaning** — pull CAA tables, reshape into a tidy monthly panel (airport × month), handle missing/suppressed values, flag anomaly periods (COVID-19).
2. **Exploratory analysis** — seasonality, trend, airport-to-airport comparison, pre/post-COVID recovery pattern, correlation with any economic features gathered.
3. **Baseline models** — naive and seasonal-naive forecasts as the benchmark to beat.
4. **Statistical models** — SARIMA/ETS (or Prophet) per airport series.
5. **ML models** — gradient-boosted trees (XGBoost/LightGBM) with lag, rolling-window, and calendar features; compare against the statistical baselines.
6. **Evaluation** — time-based train/test split with walk-forward (rolling-origin) validation; metrics: MAE, RMSE, MAPE, compared against the naive baseline.
7. **(Stretch) Deep learning** — an LSTM/temporal model, only if time allows and it's justified by the data volume.

## 7. Deliverables

- A public GitHub repository with a reproducible pipeline (data ingestion → cleaning → modelling → evaluation)
- A written report/README covering methodology, findings, and model comparison, in plain language a non-technical reviewer (e.g. a hiring manager) can follow
- Forecast outputs and evaluation metrics for each airport
- Optional: a lightweight dashboard (e.g. Streamlit) visualising historical trends and forecasts, if time allows

## 8. Tech Stack

Python (pandas, numpy), statsmodels / Prophet, scikit-learn, XGBoost or LightGBM, Jupyter for exploration, matplotlib/plotly for visualisation, GitHub for version control and portfolio hosting. Streamlit (optional) for a dashboard layer.

## 9. Timeline (self-paced)

Since this runs alongside job applications, timeline is loose and phase-based rather than date-bound:

1. Data audit & collection
2. Cleaning & EDA
3. Baseline + statistical models
4. ML models & evaluation
5. Write-up, README, and (optional) dashboard
6. Polish for portfolio presentation

## 10. Success Criteria

- Forecast models beat the naive seasonal baseline on held-out data for at least two of the three airports
- Codebase is clean, documented, and runnable by someone else from a fresh clone
- The write-up clearly explains *why* the chosen approach was used, not just the results — this is what portfolio reviewers look for

## 11. Risks & Assumptions

- NI airport data is a small, low-volume series relative to major UK hubs — more prone to noise from single events (a route cancelled, an airline exiting)
- COVID-19 creates a structural break in the historical series that needs explicit handling (exclude, dummy-flag, or model separately pre/post)
- External driver data (economic, tourism) may be at a coarser granularity (quarterly/annual) than the monthly target, requiring interpolation or a mixed-frequency approach
- Data licensing: CAA data is Open Government Licence — safe to use and publish; confirm licensing terms of any supplementary source before including it in a public repo

## 12. Open Questions

- ~~Exact historical start date~~ — resolved: January 2015 (see `docs/data-audit-findings.md`)
- Whether route-level modelling is worth pursuing given likely data availability
- Whether to include Dublin Airport as a cross-border comparator (out of scope for v1, candidate for v2)
