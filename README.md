# Flight Demand Northern Ireland

This project uses historical flight data to predict future demand for flights to and from the three commercial airports in Northern Ireland — Belfast International (BFS), George Best Belfast City (BHD), and City of Derry (LDY) — using official UK CAA airport statistics.

Project scope, methodology, and backlog live in `docs/` (mirrors the Claude project used to plan this).

## Structure

- `data/raw/` — untouched source files pulled from the CAA
- `data/processed/` — cleaned, tidy monthly panel
- `notebooks/` — exploratory analysis
- `src/` — ingestion, cleaning, modelling code
- `reports/` — write-up and figures
- `docs/` — project parameters, backlog, and data audit findings

## Status

Data audit and ingestion pipeline complete — see `docs/data-audit-findings.md`. `data/processed/monthly_panel.csv` has clean monthly passenger and movement figures for all three airports, January 2015 to present, with zero missing data. Next up: cleaning/EDA (Epic 2 in `docs/backlog.md`).
