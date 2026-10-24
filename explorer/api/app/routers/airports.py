from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import Integer, cast, extract, func, select
from sqlalchemy.dialects.postgresql import distinct_on

from app import models, schemas
from app.dependencies import AirportDep, PeriodRangeDep, SessionDep
from app.periods import format_period, same_month_last_year

router = APIRouter(prefix="/airports", tags=["airports"])


def _airport(a: models.Airport) -> dict:
    return {
        "code": a.code,
        "icao_code": a.icao_code,
        "name": a.name,
        "latitude": float(a.latitude),
        "longitude": float(a.longitude),
    }


def _latest_months(session, codes: list[str]) -> dict[str, schemas.LatestMonth]:
    """Latest reported month per airport, with year-on-year change.

    DISTINCT ON picks each airport's newest row straight off the
    (airport_code, period_start) primary-key index; the prior-year figure is
    then a point lookup on the same index.
    """
    latest_rows = session.execute(
        select(models.MonthlyStat)
        .where(models.MonthlyStat.airport_code.in_(codes))
        .order_by(models.MonthlyStat.airport_code, models.MonthlyStat.period_start.desc())
        .ext(distinct_on(models.MonthlyStat.airport_code))
    ).scalars()

    result = {}
    for row in latest_rows:
        prior = session.get(models.MonthlyStat, (row.airport_code, same_month_last_year(row.period_start)))
        yoy = None
        if prior is not None and prior.total_pax:
            yoy = round((row.total_pax - prior.total_pax) / prior.total_pax * 100, 1)
        result[row.airport_code] = schemas.LatestMonth(
            period=format_period(row.period_start), total_pax=row.total_pax, yoy_change_pct=yoy
        )
    return result


@router.get("", response_model=list[schemas.AirportSummary], summary="List airports with their latest month")
def list_airports(session: SessionDep):
    airports = session.scalars(select(models.Airport).order_by(models.Airport.code)).all()
    latest = _latest_months(session, [a.code for a in airports])
    return [schemas.AirportSummary(**_airport(a), latest=latest.get(a.code)) for a in airports]


@router.get("/{code}", response_model=schemas.AirportSummary, summary="One airport with its latest month")
def get_airport(airport: AirportDep, session: SessionDep):
    latest = _latest_months(session, [airport.code])
    return schemas.AirportSummary(**_airport(airport), latest=latest.get(airport.code))


@router.get("/{code}/monthly", response_model=list[schemas.MonthlyStat], summary="Monthly passengers and movements")
def get_monthly(
    airport: AirportDep,
    session: SessionDep,
    period: PeriodRangeDep,
    exclude_covid: Annotated[bool, Query(description="Drop months flagged as the COVID-19 anomaly period")] = False,
):
    query = (
        select(models.MonthlyStat)
        .where(models.MonthlyStat.airport_code == airport.code)
        .order_by(models.MonthlyStat.period_start)
    )
    if period.start:
        query = query.where(models.MonthlyStat.period_start >= period.start)
    if period.end:
        query = query.where(models.MonthlyStat.period_start <= period.end)
    if exclude_covid:
        query = query.where(models.MonthlyStat.is_covid_anomaly.is_(False))

    return [
        schemas.MonthlyStat(
            period=format_period(r.period_start),
            total_pax=r.total_pax,
            terminal_pax=r.terminal_pax,
            transit_pax=r.transit_pax,
            atm_total=r.atm_total,
            atm_domestic=r.atm_domestic,
            atm_eu=r.atm_eu,
            atm_non_eu=r.atm_non_eu,
            is_covid_anomaly=r.is_covid_anomaly,
        )
        for r in session.scalars(query)
    ]


@router.get("/{code}/annual", response_model=list[schemas.AnnualStat], summary="Calendar-year totals")
def get_annual(airport: AirportDep, session: SessionDep):
    year = cast(extract("year", models.MonthlyStat.period_start), Integer).label("year")
    rows = session.execute(
        select(
            year,
            func.sum(models.MonthlyStat.total_pax).label("total_pax"),
            func.sum(models.MonthlyStat.atm_total).label("atm_total"),
            func.count().label("months_reported"),
        )
        .where(models.MonthlyStat.airport_code == airport.code)
        .group_by(year)
        .order_by(year)
    ).all()
    return [
        schemas.AnnualStat(
            year=r.year,
            total_pax=r.total_pax,
            atm_total=r.atm_total,
            months_reported=r.months_reported,
            is_complete=r.months_reported == 12,
        )
        for r in rows
    ]


@router.get("/{code}/forecast", response_model=schemas.Forecast, summary="Latest forecast for an airport")
def get_forecast(
    airport: AirportDep,
    session: SessionDep,
    model: Annotated[str, Query(description="Forecasting model name")] = "ETS",
):
    run = session.scalars(
        select(models.ForecastRun)
        .where(models.ForecastRun.model_name == model)
        .order_by(models.ForecastRun.trained_through.desc())
        .limit(1)
    ).first()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"No forecast available for model {model!r}")

    values = session.scalars(
        select(models.ForecastValue)
        .where(models.ForecastValue.run_id == run.id, models.ForecastValue.airport_code == airport.code)
        .order_by(models.ForecastValue.period_start)
    ).all()
    return schemas.Forecast(
        airport_code=airport.code,
        model_name=run.model_name,
        trained_through=format_period(run.trained_through),
        horizon_months=run.horizon_months,
        values=[
            schemas.ForecastPoint(period=format_period(v.period_start), predicted_total_pax=float(v.predicted_total_pax))
            for v in values
        ],
    )
