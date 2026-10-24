from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app import models
from app.db import get_session
from app.periods import PERIOD_PATTERN, parse_period

SessionDep = Annotated[Session, Depends(get_session)]


@dataclass(frozen=True)
class PeriodRange:
    start: date | None
    end: date | None


def period_range(
    start: Annotated[str | None, Query(pattern=PERIOD_PATTERN, description="First month, inclusive (YYYY-MM)")] = None,
    end: Annotated[str | None, Query(pattern=PERIOD_PATTERN, description="Last month, inclusive (YYYY-MM)")] = None,
) -> PeriodRange:
    range_ = PeriodRange(parse_period(start) if start else None, parse_period(end) if end else None)
    if range_.start and range_.end and range_.start > range_.end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail="start must not be after end")
    return range_


PeriodRangeDep = Annotated[PeriodRange, Depends(period_range)]


def existing_airport(
    code: Annotated[str, Path(description="IATA code, e.g. BFS", min_length=3, max_length=3)],
    session: SessionDep,
) -> models.Airport:
    airport = session.get(models.Airport, code.upper())
    if airport is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Unknown airport {code!r}")
    return airport


AirportDep = Annotated[models.Airport, Depends(existing_airport)]
