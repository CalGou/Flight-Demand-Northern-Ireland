from datetime import date

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError

from app.loader import load_airports, load_all, load_forecasts, parse_panel_row, period_to_date
from app.models import ForecastRun, ForecastValue, MonthlyStat
from tests.conftest import REPO_ROOT


def panel_row(**overrides):
    row = {
        "airport_code": "BFS",
        "period": "201501",
        "total_pax": "237948",
        "terminal_pax": "237819",
        "transit_pax": "129",
        "mov_total_EU_atm": "264.0",  # float, as produced by the 2016 casing merge
        "mov_total_domestic_atm": "2061",
        "mov_total_non_EU_international_atm": "79",
        "covid_anomaly": "False",
    }
    return {**row, **overrides}


# --- parsing ------------------------------------------------------------------

def test_parse_panel_row_sums_movements_and_converts_period():
    parsed = parse_panel_row(panel_row())
    assert parsed["period_start"] == date(2015, 1, 1)
    assert parsed["atm_eu"] == 264
    assert parsed["atm_total"] == 264 + 2061 + 79
    assert parsed["is_covid_anomaly"] is False


def test_parse_panel_row_reads_covid_flag():
    assert parse_panel_row(panel_row(covid_anomaly="True"))["is_covid_anomaly"] is True


def test_parse_panel_row_rejects_fractional_counts():
    with pytest.raises(ValueError, match="whole number"):
        parse_panel_row(panel_row(mov_total_EU_atm="264.5"))


@pytest.mark.parametrize("bad", ["2016005", "2016-05", "20165"])
def test_period_to_date_rejects_malformed_caa_periods(bad):
    # 2016005 is the real malformed value CAA published (data-audit-findings.md).
    with pytest.raises(ValueError):
        period_to_date(bad)


# --- loading the real project data ------------------------------------------

def test_loads_full_project_dataset(empty_db):
    summary = load_all(empty_db, REPO_ROOT)
    assert summary.airports == 3
    assert summary.monthly_stats == 414  # 138 months x 3 airports
    assert summary.forecast_values == 36  # 12 months x 3 airports
    assert summary.model_evaluations == 18


def test_spot_check_matches_data_audit(loaded_db):
    with loaded_db.connect() as conn:
        pax = conn.scalar(
            select(MonthlyStat.total_pax).where(
                MonthlyStat.airport_code == "BFS", MonthlyStat.period_start == date(2026, 3, 1)
            )
        )
    assert pax == 532_799  # independently confirmed figure in docs/data-audit-findings.md


def test_covid_window_is_27_months_per_airport(loaded_db):
    with loaded_db.connect() as conn:
        count = conn.scalar(select(func.count()).where(MonthlyStat.is_covid_anomaly))
    assert count == 27 * 3  # Mar 2020 - May 2022 inclusive


def test_reloading_is_idempotent(loaded_db):
    load_all(loaded_db, REPO_ROOT)
    with loaded_db.connect() as conn:
        assert conn.scalar(select(func.count()).select_from(MonthlyStat)) == 414
        assert conn.scalar(select(func.count()).select_from(ForecastRun)) == 1
        assert conn.scalar(select(func.count()).select_from(ForecastValue)) == 36


def test_forecast_run_trained_through_month_before_first_forecast(loaded_db):
    with loaded_db.connect() as conn:
        run = conn.execute(select(ForecastRun)).one()
    assert run.model_name == "ETS"
    assert run.trained_through == date(2026, 6, 1)
    assert run.horizon_months == 12


def test_forecast_files_with_different_horizons_are_rejected(empty_db, tmp_path):
    (tmp_path / "bfs_forecast.csv").write_text("period,airport_code,forecast_total_pax\n202607,BFS,1\n202608,BFS,2\n")
    (tmp_path / "bhd_forecast.csv").write_text("period,airport_code,forecast_total_pax\n202607,BHD,1\n")
    with empty_db.begin() as conn:
        load_airports(conn)
        with pytest.raises(ValueError, match="disagree on horizon"):
            load_forecasts(conn, tmp_path, ["BFS", "BHD"])


# --- database constraints ------------------------------------------------------

def _insert_month(conn, **overrides):
    values = dict(
        airport_code="BFS", period_start="2030-01-01", total_pax=1, terminal_pax=1, transit_pax=0,
        atm_total=1, atm_domestic=1, atm_eu=0, atm_non_eu=0, is_covid_anomaly=False,
    )
    values.update(overrides)
    columns = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    conn.execute(text(f"INSERT INTO monthly_stats ({columns}) VALUES ({params})"), values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"period_start": "2030-01-15"},  # not first of month
        {"total_pax": -1},
        {"atm_eu": -5},
        {"airport_code": "DUB"},  # not a known airport
    ],
)
def test_schema_rejects_invalid_rows(loaded_db, overrides):
    with pytest.raises(IntegrityError), loaded_db.begin() as conn:
        _insert_month(conn, **overrides)


def test_schema_rejects_duplicate_airport_month(loaded_db):
    with pytest.raises(IntegrityError), loaded_db.begin() as conn:
        _insert_month(conn, period_start="2015-01-01")
