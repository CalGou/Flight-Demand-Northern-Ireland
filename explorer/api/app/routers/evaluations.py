from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app import models, schemas
from app.dependencies import SessionDep

router = APIRouter(prefix="/evaluations", tags=["models"])


@router.get(
    "",
    response_model=list[schemas.ModelEvaluation],
    summary="Walk-forward evaluation results per airport and model",
)
def list_evaluations(
    session: SessionDep,
    airport: Annotated[str | None, Query(min_length=3, max_length=3, description="Filter to one airport")] = None,
    covid_excluded: Annotated[
        bool, Query(description="True for the COVID-excluded folds (the headline comparison)")
    ] = True,
):
    query = (
        select(models.ModelEvaluation)
        .where(models.ModelEvaluation.covid_excluded.is_(covid_excluded))
        .order_by(models.ModelEvaluation.airport_code, models.ModelEvaluation.mae)
    )
    if airport:
        query = query.where(models.ModelEvaluation.airport_code == airport.upper())

    return [
        schemas.ModelEvaluation(
            airport_code=e.airport_code,
            model_name=e.model_name,
            covid_excluded=e.covid_excluded,
            mae=float(e.mae),
            rmse=float(e.rmse) if e.rmse is not None else None,
            mape=float(e.mape) if e.mape is not None else None,
            source=e.source,
        )
        for e in session.scalars(query)
    ]
