# Database schema

PostgreSQL 16. The schema is defined in `api/migrations/versions/0001_initial_schema.py` (Alembic) and mirrored by the ORM models in `api/app/models.py`; a test (`test_models_match_migrations`) fails the build if the two ever drift.

## Tables

| Table | Grain | Primary key |
|---|---|---|
| `airports` | one row per airport | `code` (IATA) |
| `monthly_stats` | one row per airport per month | `(airport_code, period_start)` |
| `forecast_runs` | one row per model per training cutoff | `id`, unique on `(model_name, trained_through)` |
| `forecast_values` | one predicted month per airport per run | `(run_id, airport_code, period_start)` |
| `model_evaluations` | one walk-forward result per airport, model and COVID treatment | `(airport_code, model_name, covid_excluded)` |

## Design decisions

**Natural composite keys rather than surrogate IDs on `monthly_stats`.** An airport can only report one figure per month, so `(airport_code, period_start)` *is* the identity of a row. Making it the primary key enforces that rule in the database (the data audit found real duplicate risk in CAA's re-published releases) and gives the most common query its index for free.

**Months stored as `DATE` (first of the month), not `'YYYYMM'` text.** Range filters, `date_trunc` and year grouping work natively, and a check constraint (`extract(day from period_start) = 1`) stops a mid-month date ever getting in. The API converts to `'YYYY-MM'` strings at the edge.

**Movements stored as four whole-number columns.** `atm_domestic`, `atm_eu` and `atm_non_eu` come from CAA's totals; `atm_total` is their sum, computed once at load time. The loader rejects any fractional movement count rather than silently rounding it, since the 2016 column-casing merge produces floats (`228.0`).

**Forecasts are versioned by run.** Re-running `src/forecast.py` on newer data creates a new `forecast_runs` row instead of overwriting history, so older forecasts can later be scored against what actually happened. Reloading the *same* forecast is idempotent: the loader upserts the run on `(model_name, trained_through)` and replaces its values.

**Check constraints for things that are never valid:** negative passenger or movement counts, airport codes that aren't three capital letters, forecast horizons outside 1–36 months.

## Indexes

Each index is there for a specific query, and `api/tests/test_schema.py` checks the planner can use it for that query.

| Index | Serves |
|---|---|
| `pk_monthly_stats (airport_code, period_start)` | One airport's series over a date range (`/airports/{code}/monthly`, `/annual`), and the latest-month lookup via `DISTINCT ON` |
| `ix_monthly_stats_period_start (period_start)` | Every airport for a date range (`/network/monthly`). The primary key can't help here because `period_start` isn't its leading column |
| `uq_forecast_runs_model_trained_through (model_name, trained_through)` | "Latest run for model X" (`ORDER BY trained_through DESC LIMIT 1`), via a backward index scan |
| `pk_forecast_values (run_id, airport_code, period_start)` | One airport's values for one run |

**One index deliberately left out.** The first draft added a separate `(model_name, trained_through)` index for the latest-run query. The unique constraint already creates exactly that B-tree, so the second index was pure write overhead and was removed.

At 414 rows Postgres will (correctly) prefer sequential scans, so the index tests disable that option to confirm which index is *available*. The design matters as the data grows: one more airport or a route-level table would push row counts into the tens of thousands.
