# NI Airports Explorer

A full-stack web application over the [Flight Demand Northern Ireland](../README.md) analysis: passenger and flight-movement history for Belfast International, George Best Belfast City and City of Derry airports, with the project's ETS forecasts and model evaluation results.

The analysis pipeline in `../src` stays the source of truth. This application publishes its outputs (`data/processed/monthly_panel_clean.csv`, `reports/*_forecast.csv`) through a PostgreSQL database and a REST API.

## Status

| Layer | Stack | Status |
|---|---|---|
| Database | PostgreSQL 16, Alembic migrations | Done |
| API | Python, FastAPI, SQLAlchemy 2, pytest | Done |
| Containers & CI | Docker, docker-compose, GitHub Actions | Done |
| Front end | React, TypeScript, Material UI, Jest/React Testing Library | Next |
| Cloud | AWS (S3 + CloudFront, Lambda + API Gateway, RDS), Terraform | Planned |

## Architecture

```
src/ pipeline ──► CSV outputs ──► loader ──► PostgreSQL ──► FastAPI ──► React front end
                                  (upserts)   (schema +     (REST,
                                              indexes)      OpenAPI)
```

## API

All endpoints are `GET` under `/api/v1`. Interactive documentation is generated at `/docs` when the API is running.

| Endpoint | Returns |
|---|---|
| `/health` | Liveness and database check |
| `/airports` | All airports, each with its latest month and year-on-year change |
| `/airports/{code}` | One airport (code is case-insensitive) |
| `/airports/{code}/monthly?start=YYYY-MM&end=YYYY-MM&exclude_covid=false` | Monthly passengers and air transport movements |
| `/airports/{code}/annual` | Calendar-year totals, with partial years flagged |
| `/airports/{code}/forecast?model=ETS` | The latest forecast run for that airport |
| `/network/monthly?start=&end=` | All-airport monthly totals with each airport's share |
| `/evaluations?airport=&covid_excluded=true` | Walk-forward MAE/RMSE/MAPE per model, best first |

Unknown airports return `404`; malformed months or a `start` after `end` return `422`.

## Running it

### With Docker

```
cd explorer
docker compose up --build
```

This starts PostgreSQL, applies migrations, loads the data, and serves the API at http://localhost:8000/docs.

### Without Docker

Requires Python 3.13 and a PostgreSQL database.

```
cd explorer/api
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/explorer
alembic upgrade head
python -m app.loader          # reads ../../data and ../../reports
uvicorn app.main:app --reload
```

### Tests

The tests run against a real PostgreSQL database, because the schema relies on Postgres check constraints, `ON CONFLICT` upserts and `DISTINCT ON`, and the index tests read Postgres query plans.

```
cd explorer
docker compose up -d db       # creates the explorer_test database on first start
cd api
pytest
```

Set `TEST_DATABASE_URL` to point at a different database. The suite rebuilds that database from migrations on every run, so never point it at one you want to keep.

The 49 tests cover: loading the real project data (including the BFS March 2026 spot-check from the data audit), loader idempotency, every database constraint, every endpoint and its error cases, the migration round trip, models-vs-migration drift, and that each index is usable by the query it was designed for.

## Database design

See [`docs/schema.md`](docs/schema.md) for the tables, keys, constraints and the reasoning behind each index.

## Data licence

Contains public sector information from the UK Civil Aviation Authority, licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/).
