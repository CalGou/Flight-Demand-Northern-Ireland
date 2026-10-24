"""Load the Flight Demand pipeline's outputs into PostgreSQL.

Reads the files the existing analysis pipeline already produces, so the
database is a published view of that work, not a second copy of the logic:

- data/processed/monthly_panel_clean.csv  (src/clean_panel.py)
- reports/<code>_forecast.csv              (src/forecast.py)
- explorer/api/seed/*.csv                  (airport reference data, evaluation results)

Every write is an upsert inside one transaction, so the loader is safe to
re-run after the pipeline refreshes: it either fully applies or changes nothing.

Usage (from explorer/api):
    python -m app.loader --repo-root ../..
"""
import argparse
import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Connection, Engine, delete, select
from sqlalchemy.dialects.postgresql import insert

from app.db import get_engine
from app.models import Airport, ForecastRun, ForecastValue, ModelEvaluation, MonthlyStat

SEED_DIR = Path(__file__).resolve().parent.parent / "seed"
FORECAST_MODEL_NAME = "ETS"


@dataclass(frozen=True)
class LoadSummary:
    airports: int
    monthly_stats: int
    forecast_values: int
    model_evaluations: int


def period_to_date(period: str) -> date:
    """'201501' -> date(2015, 1, 1). Rejects anything that isn't YYYYMM."""
    if len(period) != 6 or not period.isdigit():
        raise ValueError(f"Expected a YYYYMM period, got {period!r}")
    year, month = int(period[:4]), int(period[4:])
    return date(year, month, 1)


def previous_month(d: date) -> date:
    return date(d.year - 1, 12, 1) if d.month == 1 else date(d.year, d.month - 1, 1)


def _int(value: str) -> int:
    # Movement columns merged across CAA's 2016 schema change come out of
    # pandas as floats ("228.0"); they are whole counts, so fail loudly if not.
    number = float(value)
    if not number.is_integer():
        raise ValueError(f"Expected a whole number, got {value!r}")
    return int(number)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def parse_panel_row(row: dict[str, str]) -> dict:
    atm_eu = _int(row["mov_total_EU_atm"])
    atm_domestic = _int(row["mov_total_domestic_atm"])
    atm_non_eu = _int(row["mov_total_non_EU_international_atm"])
    return {
        "airport_code": row["airport_code"],
        "period_start": period_to_date(row["period"]),
        "total_pax": _int(row["total_pax"]),
        "terminal_pax": _int(row["terminal_pax"]),
        "transit_pax": _int(row["transit_pax"]),
        "atm_total": atm_eu + atm_domestic + atm_non_eu,
        "atm_domestic": atm_domestic,
        "atm_eu": atm_eu,
        "atm_non_eu": atm_non_eu,
        "is_covid_anomaly": row["covid_anomaly"].strip().lower() == "true",
    }


def _upsert(conn: Connection, model, rows: list[dict], key: list[str]) -> int:
    if not rows:
        return 0
    stmt = insert(model).values(rows)
    updatable = {c: stmt.excluded[c] for c in rows[0] if c not in key}
    conn.execute(stmt.on_conflict_do_update(index_elements=key, set_=updatable))
    return len(rows)


def load_airports(conn: Connection, seed_dir: Path = SEED_DIR) -> int:
    rows = [
        {**row, "latitude": Decimal(row["latitude"]), "longitude": Decimal(row["longitude"])}
        for row in _read_csv(seed_dir / "airports.csv")
    ]
    return _upsert(conn, Airport, rows, ["code"])


def load_monthly_stats(conn: Connection, panel_path: Path) -> int:
    rows = [parse_panel_row(row) for row in _read_csv(panel_path)]
    return _upsert(conn, MonthlyStat, rows, ["airport_code", "period_start"])


def load_forecasts(conn: Connection, reports_dir: Path, airport_codes: list[str]) -> int:
    """Load each airport's ETS forecast CSV under a single forecast run.

    The run is keyed on (model, trained_through), so re-loading the same
    forecast replaces its values rather than creating a duplicate run, while
    a forecast refreshed on newer data becomes a new run alongside the old.
    """
    values = []
    for code in airport_codes:
        path = reports_dir / f"{code.lower()}_forecast.csv"
        for row in _read_csv(path):
            values.append({
                "airport_code": row["airport_code"],
                "period_start": period_to_date(row["period"]),
                "predicted_total_pax": round(Decimal(row["forecast_total_pax"]), 1),
            })
    if not values:
        return 0

    first_forecast = min(v["period_start"] for v in values)
    horizons = {
        code: sum(1 for v in values if v["airport_code"] == code) for code in airport_codes
    }
    if len(set(horizons.values())) != 1:
        raise ValueError(f"Forecast files disagree on horizon: {horizons}")

    run_stmt = insert(ForecastRun).values(
        model_name=FORECAST_MODEL_NAME,
        trained_through=previous_month(first_forecast),
        horizon_months=next(iter(horizons.values())),
    )
    run_id = conn.execute(
        run_stmt.on_conflict_do_update(
            constraint="uq_forecast_runs_model_trained_through",
            set_={"horizon_months": run_stmt.excluded.horizon_months},
        ).returning(ForecastRun.id)
    ).scalar_one()

    conn.execute(delete(ForecastValue).where(ForecastValue.run_id == run_id))
    conn.execute(insert(ForecastValue), [{**v, "run_id": run_id} for v in values])
    return len(values)


def load_model_evaluations(conn: Connection, seed_dir: Path = SEED_DIR) -> int:
    rows = []
    for row in _read_csv(seed_dir / "model_evaluations.csv"):
        rows.append({
            "airport_code": row["airport_code"],
            "model_name": row["model_name"],
            "covid_excluded": row["covid_excluded"] == "true",
            "mae": Decimal(row["mae"]),
            "rmse": Decimal(row["rmse"]) if row["rmse"] else None,
            "mape": Decimal(row["mape"]) if row["mape"] else None,
            "source": row["source"],
        })
    return _upsert(conn, ModelEvaluation, rows, ["airport_code", "model_name", "covid_excluded"])


def load_all(engine: Engine, repo_root: Path, seed_dir: Path = SEED_DIR) -> LoadSummary:
    with engine.begin() as conn:
        airports = load_airports(conn, seed_dir)
        codes = list(conn.scalars(select(Airport.code).order_by(Airport.code)))
        summary = LoadSummary(
            airports=airports,
            monthly_stats=load_monthly_stats(conn, repo_root / "data" / "processed" / "monthly_panel_clean.csv"),
            forecast_values=load_forecasts(conn, repo_root / "reports", codes),
            model_evaluations=load_model_evaluations(conn, seed_dir),
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Root of the Flight-Demand-Northern-Ireland repo (contains data/ and reports/)",
    )
    args = parser.parse_args()
    summary = load_all(get_engine(), args.repo_root)
    print(
        f"Loaded {summary.airports} airports, {summary.monthly_stats} monthly rows, "
        f"{summary.forecast_values} forecast values, {summary.model_evaluations} evaluation rows."
    )


if __name__ == "__main__":
    main()
