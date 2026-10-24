from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import select

from app import models, schemas
from app.dependencies import PeriodRangeDep, SessionDep
from app.periods import format_period

router = APIRouter(prefix="/network", tags=["network"])


@router.get(
    "/monthly",
    response_model=list[schemas.NetworkMonth],
    summary="All-airport monthly passengers, with each airport's share",
)
def get_network_monthly(session: SessionDep, period: PeriodRangeDep):
    # Filters on period_start alone, which is what ix_monthly_stats_period_start is for.
    query = select(
        models.MonthlyStat.period_start, models.MonthlyStat.airport_code, models.MonthlyStat.total_pax
    ).order_by(models.MonthlyStat.period_start, models.MonthlyStat.airport_code)
    if period.start:
        query = query.where(models.MonthlyStat.period_start >= period.start)
    if period.end:
        query = query.where(models.MonthlyStat.period_start <= period.end)

    by_month: dict = defaultdict(dict)
    for period_start, code, pax in session.execute(query):
        by_month[period_start][code] = pax

    return [
        schemas.NetworkMonth(period=format_period(month), total_pax=sum(airports.values()), by_airport=airports)
        for month, airports in by_month.items()
    ]
