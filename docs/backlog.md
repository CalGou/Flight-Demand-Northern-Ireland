# Flight Demand Northern Ireland — Development Backlog

Derived from the project parameters doc's phased timeline (§9). Organised as epics (one per phase) with tickets underneath, sized to be individually demoable rather than done in one big batch.

## Epic 1: Data Audit ✅

- [x] Set up repo structure & environment (Python env, `requirements.txt`, README skeleton)
- [x] Pull CAA monthly airport data tables for BFS, BHD, LDY — full available history
- [x] Determine per-airport data format consistency and earliest usable month — **Jan 2015, consistent schema through present**
- [x] Document known anomalies/gaps — see `docs/data-audit-findings.md` (no bulk time-series file; 2001 methodology break is pre-2015 and moot; fortnightly publish lag)
- [x] Record the audit's finalised start date and findings back into the project parameters doc (§3/§12) — done

## Epic 2: Cleaning & EDA ✅

- [x] Build ingestion script: raw CAA files → tidy monthly panel (airport × month) — `ingest_caa_data.py` + `build_panel.py`. Fully clean as of 26 Aug 2026: 414 rows, 138 months × 3 airports, zero missing passenger/movement data, zero malformed periods (see `docs/data-audit-findings.md` for the two schema bugs that were fixed along the way)
- [x] Normalise the movement columns' casing across the Apr-2016 CAA schema change — `clean_panel.py`, merges `mov_total_EU_atm`/`mov_Total_EU_ATM` and the equivalent scheduled-ATM pair, asserts no overlap before merging
- [x] Handle missing/suppressed values — checked systematically: no negative values, no suppression markers anywhere in the panel; the only NaNs were the two casing-duplicate columns above (now merged). BFS Apr/May 2020 showing 0 total_pax is genuine (first COVID lockdown), not a data gap
- [x] Flag the COVID-era anomaly period as an explicit feature/exclusion flag — `covid_anomaly` boolean column, Mar 2020–May 2022 inclusive, window set from evidence (BFS doesn't return to the 2015–2019 monthly baseline of ~464k until Jun 2022)
- [x] EDA: seasonality, trend, and airport-to-airport comparison — `notebooks/01_eda.ipynb`: monthly trend, average-by-calendar-month (all data and pre-2020), and airport-share-of-traffic plots. Confirms BFS has the strongest seasonal amplitude (330k Jan → 585k Jul pre-2020), BHD a smaller but real seasonal swing, LDY essentially flat — the direct explanation for why seasonal-naive helps BFS most in the Epic 3 baseline comparison
- [x] EDA: pre/post-COVID recovery pattern — recovery-vs-2019-baseline plot shows all three airports back above 100 by 2022 and growing past pre-pandemic levels since (BFS peaking ~134-136%)
- [ ] (If pursued) Source and merge supplementary features — economic, tourism, or weather data

## Epic 3: Baseline & Statistical Models ✅

- [x] Build the evaluation harness: time-based train/test split + walk-forward (rolling-origin) validation — `src/evaluation.py`, `make_folds()`: expanding training window, 6-month horizon, 6-month step, 36-month minimum training window (17 folds over the full panel)
- [x] Naive and seasonal-naive baseline models — see `docs/baseline-evaluation-findings.md` for full results. No single winner: seasonal-naive clearly beats naive at BFS, they're roughly tied at BHD, naive wins at LDY — decision is to use per-airport baselines rather than one blanket choice
- [x] SARIMA/ETS (or Prophet) model per airport — ETS (`statsmodels.ExponentialSmoothing`), fit per fold per airport with trend + seasonal components; SARIMA not pursued separately since ETS gave a clean win everywhere
- [x] Compare baseline vs statistical models on MAE/RMSE/MAPE — ETS beats the strongest per-airport baseline on every metric, COVID folds excluded: BFS MAE -37.5%, BHD -43.6%, LDY -16.0% (see `docs/baseline-evaluation-findings.md`)

## Epic 4: ML Models ✅

- [x] Feature engineering: lag features, rolling windows, calendar/seasonal features — `src/features.py`, verified NaN counts match expected lookback windows exactly. Also uncovered that the row-relative lag/rolling columns aren't leak-safe across the harness's 6-month horizon (see `docs/ml-model-findings.md`), which shaped the XGBoost feature design
- [x] XGBoost/LightGBM model per airport — `xgb_forecast` in `src/evaluation.py`, direct multi-step (single model, horizon as a feature). Underperforms ETS at every airport; diagnosed as a trend-extrapolation limitation of tree-based models, attempted a growth-ratio retarget to fix it which didn't close the gap (see `docs/ml-model-findings.md`) — documented as an instructive negative result rather than pursued further given the data volume (~130 months/airport) likely favours a well-specified classical model over a general-purpose ML one here
- [x] Full model comparison table — baseline vs statistical vs ML — see `docs/ml-model-findings.md`: ETS beats naive/seasonal-naive/XGBoost at every airport on every metric (COVID-excluded); reported as this project's best per-airport forecaster
- [ ] (Stretch) LSTM/temporal model, if data volume justifies it — **not pursued**: LDY in particular has ~130 monthly observations, well short of what a deep model needs, and XGBoost's underperformance here (see above) is itself evidence more model capacity isn't the bottleneck for this dataset

## Epic 5: Write-up & Dashboard ✅

- [x] Write the README: methodology, findings, model comparison, in plain language — top-level `README.md` rewritten: key findings, methodology, results table, links into `docs/` for full detail, run instructions
- [x] Produce final forecast outputs and charts per airport — `src/forecast.py`: ETS refit on full history (not a backtest fold) per airport, 12-month-ahead forecast. `reports/{bfs,bhd,ldy}_forecast.{png,csv}`. Visually confirmed: seasonal shape and trend continue smoothly past the actual data with no flattening (unlike XGBoost's extrapolation ceiling), and the 2026-2027 winter trough / summer peak line up with each airport's historical calendar-month pattern
- [x] (Optional) Build a Streamlit dashboard over the historical + forecast data — `app.py`: KPI row, actual/forecast chart, model evaluation table. Built and pushed; not yet run locally to visually confirm (unlike the forecast charts, which were screenshot-checked) -- worth a quick `streamlit run app.py` when convenient

## Epic 6: Portfolio Polish

- [x] Clean up the repo for public visibility (licence, pinned dependencies, clear run instructions) — MIT `LICENSE` added (data separately noted as UK CAA OGL, not MIT); `requirements.txt` pinned to tested versions and trimmed of two unused packages (scikit-learn, openpyxl -- never actually imported); README run instructions cover the full pipeline through the dashboard. Also fixed a broken reference found during proofread: the EDA notebook was saved as `01_ada.ipynb` (typo) while every doc pointed at `01_eda.ipynb` -- renamed to match. Live dashboard deployed and linked: https://flight-demand-northern-ireland-tv8ptiozfgpj9mtqtnjspz.streamlit.app/
- [ ] Final proofread of the write-up
- [ ] Link the finished project from CV / portfolio site
