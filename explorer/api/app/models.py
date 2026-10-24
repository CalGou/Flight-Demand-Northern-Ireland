"""SQLAlchemy ORM models.

The schema is the source of truth in migrations/versions/0001_initial_schema.py;
these models mirror it so the API can query it. See explorer/docs/schema.md
for the reasoning behind each key and index.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Identity,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Airport(Base):
    __tablename__ = "airports"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)  # IATA
    icao_code: Mapped[str] = mapped_column(String(4), unique=True)
    name: Mapped[str] = mapped_column(Text)
    caa_name: Mapped[str] = mapped_column(Text, unique=True)  # name as it appears in CAA tables
    latitude: Mapped[Decimal] = mapped_column(Numeric(8, 5))
    longitude: Mapped[Decimal] = mapped_column(Numeric(8, 5))

    __table_args__ = (
        CheckConstraint("code ~ '^[A-Z]{3}$'", name="ck_airports_code_format"),
        CheckConstraint("icao_code ~ '^[A-Z]{4}$'", name="ck_airports_icao_format"),
    )


class MonthlyStat(Base):
    __tablename__ = "monthly_stats"

    airport_code: Mapped[str] = mapped_column(
        String(3), ForeignKey("airports.code", ondelete="RESTRICT"), primary_key=True
    )
    # Always the first day of the month; a DATE (not 'YYYYMM' text) so range
    # queries and date_trunc work natively.
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)
    total_pax: Mapped[int] = mapped_column(Integer)
    terminal_pax: Mapped[int] = mapped_column(Integer)
    transit_pax: Mapped[int] = mapped_column(Integer)
    atm_total: Mapped[int] = mapped_column(Integer)
    atm_domestic: Mapped[int] = mapped_column(Integer)
    atm_eu: Mapped[int] = mapped_column(Integer)
    atm_non_eu: Mapped[int] = mapped_column(Integer)
    is_covid_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)

    airport: Mapped[Airport] = relationship()

    __table_args__ = (
        CheckConstraint("extract(day from period_start) = 1", name="ck_monthly_stats_first_of_month"),
        CheckConstraint(
            "total_pax >= 0 AND terminal_pax >= 0 AND transit_pax >= 0", name="ck_monthly_stats_pax_non_negative"
        ),
        CheckConstraint(
            "atm_total >= 0 AND atm_domestic >= 0 AND atm_eu >= 0 AND atm_non_eu >= 0",
            name="ck_monthly_stats_atm_non_negative",
        ),
        # The PK (airport_code, period_start) already serves "one airport's
        # series over a date range". This one serves "every airport for a
        # date range" (cross-airport comparison, network totals), where the
        # leading column of the PK is no help.
        Index("ix_monthly_stats_period_start", "period_start"),
    )


class ForecastRun(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[int] = mapped_column(Integer, Identity(always=False), primary_key=True)
    model_name: Mapped[str] = mapped_column(Text)
    trained_through: Mapped[date] = mapped_column(Date)
    horizon_months: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    values: Mapped[list["ForecastValue"]] = relationship(back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("model_name", "trained_through", name="uq_forecast_runs_model_trained_through"),
        CheckConstraint("horizon_months BETWEEN 1 AND 36", name="ck_forecast_runs_horizon"),
        # No separate index for "latest run for model X": the unique
        # constraint above is backed by a (model_name, trained_through)
        # B-tree, which already answers it with a backward index scan.
    )


class ForecastValue(Base):
    __tablename__ = "forecast_values"

    run_id: Mapped[int] = mapped_column(ForeignKey("forecast_runs.id", ondelete="CASCADE"), primary_key=True)
    airport_code: Mapped[str] = mapped_column(String(3), ForeignKey("airports.code"), primary_key=True)
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)
    predicted_total_pax: Mapped[Decimal] = mapped_column(Numeric(12, 1))

    run: Mapped[ForecastRun] = relationship(back_populates="values")

    __table_args__ = (
        CheckConstraint("extract(day from period_start) = 1", name="ck_forecast_values_first_of_month"),
    )


class ModelEvaluation(Base):
    __tablename__ = "model_evaluations"

    airport_code: Mapped[str] = mapped_column(String(3), ForeignKey("airports.code"), primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, primary_key=True)
    covid_excluded: Mapped[bool] = mapped_column(Boolean, primary_key=True)
    mae: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    rmse: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    mape: Mapped[Decimal | None] = mapped_column(Numeric(7, 2), nullable=True)
    source: Mapped[str] = mapped_column(Text)  # which findings doc the figures come from
