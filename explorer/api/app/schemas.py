"""Response models. Periods go over the wire as 'YYYY-MM' strings: unambiguous,
sortable, and what both the front end and a human reading JSON expect."""
from pydantic import BaseModel, ConfigDict, Field


class LatestMonth(BaseModel):
    period: str = Field(examples=["2026-06"])
    total_pax: int
    yoy_change_pct: float | None = Field(
        description="Change vs the same month a year earlier; null if that month is missing or zero."
    )


class Airport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str = Field(examples=["BFS"])
    icao_code: str = Field(examples=["EGAA"])
    name: str = Field(examples=["Belfast International"])
    latitude: float
    longitude: float


class AirportSummary(Airport):
    latest: LatestMonth | None


class MonthlyStat(BaseModel):
    period: str
    total_pax: int
    terminal_pax: int
    transit_pax: int
    atm_total: int
    atm_domestic: int
    atm_eu: int
    atm_non_eu: int
    is_covid_anomaly: bool


class AnnualStat(BaseModel):
    year: int
    total_pax: int
    atm_total: int
    months_reported: int
    is_complete: bool = Field(description="False for a year with fewer than 12 months of data so far.")


class ForecastPoint(BaseModel):
    period: str
    predicted_total_pax: float


class Forecast(BaseModel):
    airport_code: str
    model_name: str
    trained_through: str
    horizon_months: int
    values: list[ForecastPoint]


class NetworkMonth(BaseModel):
    period: str
    total_pax: int
    by_airport: dict[str, int]


class ModelEvaluation(BaseModel):
    airport_code: str
    model_name: str
    covid_excluded: bool
    mae: float
    rmse: float | None
    mape: float | None
    source: str


class Health(BaseModel):
    status: str
    database: str
