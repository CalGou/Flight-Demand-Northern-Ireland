# Flight Demand Northern Ireland

Forecasting monthly passenger and flight movement demand at Northern Ireland's
three commercial airports — Belfast International (BFS), George Best Belfast
City (BHD), and City of Derry (LDY) — using official UK CAA airport
statistics.

Project scope, methodology, and backlog live in `docs/` (mirrors the Claude
project used to plan this).

## Structure

- `data/raw/` — untouched source files pulled from the CAA
- `data/processed/` — cleaned, tidy monthly panel
- `notebooks/` — exploratory analysis
- `src/` — ingestion, cleaning, modelling code
- `reports/` — write-up and figures
- `docs/` — project parameters and backlog

## Status

Data audit in progress — see `docs/project-parameters.md` for the current
scope and open questions.
