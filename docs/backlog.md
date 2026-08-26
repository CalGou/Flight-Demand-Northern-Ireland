# Flight Demand Northern Ireland — Development Backlog

Derived from the project parameters doc's phased timeline (§9). Organised as epics (one per phase) with tickets underneath, sized to be individually demoable rather than done in one big batch.

## Epic 1: Data Audit ✅

- [x] Set up repo structure & environment (Python env, `requirements.txt`, README skeleton)
- [x] Pull CAA monthly airport data tables for BFS, BHD, LDY — full available history
- [x] Determine per-airport data format consistency and earliest usable month — **Jan 2015, consistent schema through present**
- [x] Document known anomalies/gaps — see `docs/data-audit-findings.md` (no bulk time-series file; 2001 methodology break is pre-2015 and moot; fortnightly publish lag)
- [x] Record the audit's finalised start date and findings back into the project parameters doc (§3/§12) — done

## Epic 2: Cleaning & EDA

- [x] Build ingestion script: raw CAA files → tidy monthly panel (airport × month) — `ingest_caa_data.py` + `build_panel.py`. Fully clean as of 26 Aug 2026: 414 rows, 138 months × 3 airports, zero missing passenger/movement data, zero malformed periods (see `docs/data-audit-findings.md` for the two schema bugs that were fixed along the way)
- [ ] Normalise the movement columns' casing across the Apr-2016 CAA schema change (e.g. `mov_total_EU_atm` / `mov_Total_EU_ATM` are the same metric)
- [ ] Handle missing/suppressed values, with the treatment documented
- [ ] Flag the COVID-era anomaly period as an explicit feature/exclusion flag
- [ ] EDA: seasonality, trend, and airport-to-airport comparison
- [ ] EDA: pre/post-COVID recovery pattern
- [ ] (If pursued) Source and merge supplementary features — economic, tourism, or weather data

## Epic 3: Baseline & Statistical Models

- [ ] Build the evaluation harness: time-based train/test split + walk-forward (rolling-origin) validation
- [ ] Naive and seasonal-naive baseline models
- [ ] SARIMA/ETS (or Prophet) model per airport
- [ ] Compare baseline vs statistical models on MAE/RMSE/MAPE

## Epic 4: ML Models

- [ ] Feature engineering: lag features, rolling windows, calendar/seasonal features
- [ ] XGBoost/LightGBM model per airport
- [ ] Full model comparison table — baseline vs statistical vs ML
- [ ] (Stretch) LSTM/temporal model, if data volume justifies it

## Epic 5: Write-up & Dashboard

- [ ] Write the README: methodology, findings, model comparison, in plain language
- [ ] Produce final forecast outputs and charts per airport
- [ ] (Optional) Build a Streamlit dashboard over the historical + forecast data

## Epic 6: Portfolio Polish

- [ ] Clean up the repo for public visibility (licence, pinned dependencies, clear run instructions)
- [ ] Final proofread of the write-up
- [ ] Link the finished project from CV / portfolio site
