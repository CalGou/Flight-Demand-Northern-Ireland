# Flight Demand Northern Ireland

Forecasting monthly passenger demand at Northern Ireland's three commercial airports — Belfast International (BFS), George Best Belfast City (BHD), and City of Derry (LDY) — using official UK CAA airport statistics. A self-directed portfolio project covering the full pipeline: data sourcing, cleaning, exploratory analysis, and time-series/ML forecasting, evaluated with walk-forward cross-validation rather than a single train/test split.

## Key findings

- Built a clean monthly panel from Jan 2015 to present (414 rows, zero missing data) from CAA's raw monthly releases, catching and fixing two real data-quality bugs along the way — one of which was silently dropping nearly all movements data since April 2016 (see `docs/data-audit-findings.md`).
- There's no single best naive baseline across the three airports: seasonal-naive (repeat the same month last year) beats plain naive at BFS, is roughly tied at BHD, and loses to plain naive at LDY — driven by how strongly seasonal each airport's traffic actually is (confirmed in the EDA).
- An ETS (exponential smoothing) model beats the strongest available baseline at **every airport**, once COVID-disrupted evaluation folds are excluded — a 37-44% reduction in mean absolute error at BFS and BHD, a smaller but real 16% at low-volume LDY.
- XGBoost, evaluated on the same features and folds, did **not** beat ETS anywhere, despite a targeted attempt to fix a diagnosed trend-extrapolation limitation. Documented as a genuine negative result rather than smoothed over (see `docs/ml-model-findings.md`) — with ~130 monthly observations per airport, a classical model that's structurally well-matched to the problem beat a more powerful but data-hungry general-purpose ML model.
- **Recommended model: ETS, fit independently per airport.** This satisfies the project's own success criterion (beat the naive baseline at 2+ of 3 airports) at all three.

## Methodology

1. **Data collection** — UK CAA's "UK Airport Data" publishes one page per calendar month with CSV downloads from January 2015 onward (earlier years are scanned PDFs, not machine-readable). `src/ingest_caa_data.py` walks every monthly page individually, since each release only contains that month's figures — there's no bulk historical file.
2. **Cleaning** — `src/build_panel.py` joins passenger and movement figures into one tidy panel; `src/clean_panel.py` normalises a mid-2016 CAA column-casing change and adds an evidence-based `covid_anomaly` flag (Mar 2020–May 2022).
3. **Exploratory analysis** (`notebooks/01_eda.ipynb`) — trend, calendar-month seasonality, airport-to-airport traffic share, and post-COVID recovery relative to each airport's 2019 baseline.
4. **Evaluation harness** (`src/evaluation.py`) — walk-forward (rolling-origin) validation: each fold trains on all data up to a cutoff and forecasts the next 6 months, sliding forward 6 months between folds. This is the time-series-appropriate alternative to a random train/test split. Metrics: MAE, RMSE, MAPE.
5. **Models compared**: naive, seasonal-naive, ETS (`statsmodels`), and XGBoost with lag/rolling/calendar features and a direct multi-step forecasting design (full detail and the reasoning behind each choice in `docs/baseline-evaluation-findings.md` and `docs/ml-model-findings.md`).

## Results

COVID-excluded walk-forward evaluation (mean absolute error, lower is better):

| Airport | Naive | Seasonal-naive | ETS | XGBoost |
|---|---|---|---|---|
| BFS | 92,089 | 52,752 | **32,947** | 66,949 |
| BHD | 20,293 | 20,442 | **11,436** | 15,940 |
| LDY | 2,122 | 2,846 | **1,784** | 3,030 |

Full write-ups, including the COVID-era full-data comparison, per-fold breakdowns, and the reasoning behind every modelling decision, are in `docs/`:

- `docs/data-audit-findings.md` — data source, the Jan 2015 start-date decision, and the real bugs found and fixed while building the ingestion pipeline
- `docs/baseline-evaluation-findings.md` — evaluation harness design, naive vs seasonal-naive baseline comparison, and the ETS results
- `docs/ml-model-findings.md` — feature engineering, the multi-step-leakage problem worked through before it caused one, and the XGBoost result (including the attempted fix that didn't close the gap)

## Repository structure

- `data/raw/` — untouched source files pulled from the CAA
- `data/processed/` — cleaned, tidy monthly panel and the feature-engineered version
- `notebooks/` — exploratory analysis
- `src/` — ingestion, cleaning, feature engineering, and evaluation code
- `docs/` — project parameters, backlog, and the findings documents above

## Running it

```
pip install -r requirements.txt

# 1. Pull raw CAA data (run from your own machine -- CAA isn't reachable
#    from every sandboxed environment)
python src/ingest_caa_data.py

# 2. Build the tidy monthly panel
python src/build_panel.py

# 3. Clean it (casing normalisation, COVID flag)
python src/clean_panel.py

# 4. Build lag/rolling/calendar features
python src/features.py

# 5. Run the full model comparison
python src/evaluation.py
```

## Status

Epics 1–4 complete (data audit, cleaning & EDA, baseline & statistical models, ML models) — see `docs/backlog.md` for the full ticket-level history. Remaining: final forecast outputs/charts, an optional Streamlit dashboard, and portfolio polish (licence, pinned dependencies).
