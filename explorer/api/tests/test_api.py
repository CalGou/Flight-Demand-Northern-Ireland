from datetime import date

from sqlalchemy import delete, insert

from app.models import ForecastRun, ForecastValue, MonthlyStat


def test_health(client):
    assert client.get("/api/v1/health").json() == {"status": "ok", "database": "ok"}


# --- airports -----------------------------------------------------------------

def test_list_airports_includes_latest_month(client):
    body = client.get("/api/v1/airports").json()
    assert [a["code"] for a in body] == ["BFS", "BHD", "LDY"]
    bfs = body[0]
    assert bfs["icao_code"] == "EGAA"
    assert bfs["latest"]["period"] == "2026-06"
    assert isinstance(bfs["latest"]["yoy_change_pct"], float)


def test_airport_code_is_case_insensitive(client):
    assert client.get("/api/v1/airports/bhd").json()["name"] == "George Best Belfast City"


def test_unknown_airport_is_404(client):
    response = client.get("/api/v1/airports/DUB")
    assert response.status_code == 404
    assert "DUB" in response.json()["detail"]


def test_yoy_is_null_when_prior_year_month_is_zero(client, loaded_db):
    # BFS genuinely reported 0 passengers in April 2020. Truncate its history
    # at April 2021 so that becomes the "latest" month: a YoY against zero is
    # undefined, so the API must return null rather than divide by zero.
    with loaded_db.begin() as conn:
        conn.execute(delete(MonthlyStat).where(
            MonthlyStat.airport_code == "BFS", MonthlyStat.period_start > date(2021, 4, 1)
        ))
    latest = client.get("/api/v1/airports/BFS").json()["latest"]
    assert latest["period"] == "2021-04"
    assert latest["yoy_change_pct"] is None


# --- monthly series -------------------------------------------------------------

def test_monthly_full_history(client):
    body = client.get("/api/v1/airports/LDY/monthly").json()
    assert len(body) == 138
    assert body[0]["period"] == "2015-01"
    assert body[-1]["period"] == "2026-06"
    assert [m["period"] for m in body] == sorted(m["period"] for m in body)


def test_monthly_range_is_inclusive(client):
    body = client.get("/api/v1/airports/BFS/monthly", params={"start": "2019-01", "end": "2019-12"}).json()
    assert len(body) == 12
    assert {m["period"][:4] for m in body} == {"2019"}


def test_monthly_exclude_covid(client):
    body = client.get("/api/v1/airports/BHD/monthly", params={"exclude_covid": True}).json()
    assert len(body) == 138 - 27
    assert not any(m["is_covid_anomaly"] for m in body)


def test_monthly_atm_total_is_sum_of_parts(client):
    for month in client.get("/api/v1/airports/BHD/monthly", params={"start": "2016-01", "end": "2016-12"}).json():
        assert month["atm_total"] == month["atm_domestic"] + month["atm_eu"] + month["atm_non_eu"]


def test_start_after_end_is_422(client):
    response = client.get("/api/v1/airports/BFS/monthly", params={"start": "2020-06", "end": "2020-01"})
    assert response.status_code == 422


def test_malformed_period_is_422(client):
    assert client.get("/api/v1/airports/BFS/monthly", params={"start": "2020-13"}).status_code == 422
    assert client.get("/api/v1/airports/BFS/monthly", params={"start": "202001"}).status_code == 422


# --- annual -------------------------------------------------------------------

def test_annual_totals_and_partial_year(client):
    years = {y["year"]: y for y in client.get("/api/v1/airports/BFS/annual").json()}
    assert sorted(years) == list(range(2015, 2027))
    assert years[2019]["is_complete"] is True
    assert years[2026] == {**years[2026], "months_reported": 6, "is_complete": False}

    monthly_2019 = client.get("/api/v1/airports/BFS/monthly", params={"start": "2019-01", "end": "2019-12"}).json()
    assert years[2019]["total_pax"] == sum(m["total_pax"] for m in monthly_2019)


# --- forecast -------------------------------------------------------------------

def test_forecast_follows_last_actual_month(client):
    body = client.get("/api/v1/airports/BFS/forecast").json()
    assert body["model_name"] == "ETS"
    assert body["trained_through"] == "2026-06"
    assert len(body["values"]) == body["horizon_months"] == 12
    assert body["values"][0]["period"] == "2026-07"
    assert body["values"][-1]["period"] == "2027-06"


def test_forecast_returns_newest_run(client, loaded_db):
    with loaded_db.begin() as conn:
        run_id = conn.execute(
            insert(ForecastRun)
            .values(model_name="ETS", trained_through=date(2026, 7, 1), horizon_months=1)
            .returning(ForecastRun.id)
        ).scalar_one()
        conn.execute(
            insert(ForecastValue).values(
                run_id=run_id, airport_code="BFS", period_start=date(2026, 8, 1), predicted_total_pax=1
            )
        )
    body = client.get("/api/v1/airports/BFS/forecast").json()
    assert body["trained_through"] == "2026-07"
    assert body["values"] == [{"period": "2026-08", "predicted_total_pax": 1.0}]


def test_unknown_forecast_model_is_404(client):
    assert client.get("/api/v1/airports/BFS/forecast", params={"model": "LSTM"}).status_code == 404


# --- network ----------------------------------------------------------------------

def test_network_totals_are_sum_of_airports(client):
    body = client.get("/api/v1/network/monthly", params={"start": "2026-01"}).json()
    assert [m["period"] for m in body] == [f"2026-0{i}" for i in range(1, 7)]
    for month in body:
        assert set(month["by_airport"]) == {"BFS", "BHD", "LDY"}
        assert month["total_pax"] == sum(month["by_airport"].values())


# --- evaluations ------------------------------------------------------------------

def test_ets_is_best_model_at_every_airport(client):
    # The project's headline finding, served straight from the database.
    body = client.get("/api/v1/evaluations").json()
    best = {}
    for row in body:  # ordered by airport, then MAE ascending
        best.setdefault(row["airport_code"], row["model_name"])
    assert best == {"BFS": "ETS", "BHD": "ETS", "LDY": "ETS"}


def test_evaluations_filters(client):
    ldy = client.get("/api/v1/evaluations", params={"airport": "ldy"}).json()
    assert {r["airport_code"] for r in ldy} == {"LDY"}
    assert len(ldy) == 4

    full = client.get("/api/v1/evaluations", params={"covid_excluded": False}).json()
    assert {r["model_name"] for r in full} == {"Naive", "ETS"}
    assert all(not r["covid_excluded"] for r in full)


def test_openapi_schema_is_published(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/airports/{code}/monthly" in paths
