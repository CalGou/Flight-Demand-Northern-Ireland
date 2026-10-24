"""FastAPI application entry point.

Local:   uvicorn app.main:app --reload
Docker:  see explorer/docker-compose.yml
"""
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app import schemas
from app.config import get_settings
from app.dependencies import SessionDep
from app.routers import airports, evaluations, network

API_PREFIX = "/api/v1"

app = FastAPI(
    title="NI Airports Explorer API",
    version="0.1.0",
    description=(
        "Monthly passenger and flight-movement statistics for Northern Ireland's three commercial "
        "airports (UK CAA data, Jan 2015 onward), plus ETS demand forecasts and model evaluation "
        "results from the Flight Demand Northern Ireland project. Contains public sector "
        "information licensed under the Open Government Licence v3.0."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["GET"],
    allow_headers=["*"],
)

api = APIRouter(prefix=API_PREFIX)
api.include_router(airports.router)
api.include_router(network.router)
api.include_router(evaluations.router)


@api.get("/health", response_model=schemas.Health, tags=["meta"], summary="Liveness and database check")
def health(session: SessionDep):
    try:
        session.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError:
        database = "unavailable"
    return schemas.Health(status="ok", database=database)


app.include_router(api)
