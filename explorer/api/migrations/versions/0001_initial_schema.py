"""Initial schema: airports, monthly stats, forecasts, model evaluations.

Revision ID: 0001
Revises:
Create Date: 2026-10-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "airports",
        sa.Column("code", sa.String(3), primary_key=True),
        sa.Column("icao_code", sa.String(4), nullable=False, unique=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("caa_name", sa.Text, nullable=False, unique=True),
        sa.Column("latitude", sa.Numeric(8, 5), nullable=False),
        sa.Column("longitude", sa.Numeric(8, 5), nullable=False),
        sa.CheckConstraint("code ~ '^[A-Z]{3}$'", name="ck_airports_code_format"),
        sa.CheckConstraint("icao_code ~ '^[A-Z]{4}$'", name="ck_airports_icao_format"),
    )

    op.create_table(
        "monthly_stats",
        sa.Column("airport_code", sa.String(3), sa.ForeignKey("airports.code", ondelete="RESTRICT"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("total_pax", sa.Integer, nullable=False),
        sa.Column("terminal_pax", sa.Integer, nullable=False),
        sa.Column("transit_pax", sa.Integer, nullable=False),
        sa.Column("atm_total", sa.Integer, nullable=False),
        sa.Column("atm_domestic", sa.Integer, nullable=False),
        sa.Column("atm_eu", sa.Integer, nullable=False),
        sa.Column("atm_non_eu", sa.Integer, nullable=False),
        sa.Column("is_covid_anomaly", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.PrimaryKeyConstraint("airport_code", "period_start", name="pk_monthly_stats"),
        sa.CheckConstraint("extract(day from period_start) = 1", name="ck_monthly_stats_first_of_month"),
        sa.CheckConstraint(
            "total_pax >= 0 AND terminal_pax >= 0 AND transit_pax >= 0", name="ck_monthly_stats_pax_non_negative"
        ),
        sa.CheckConstraint(
            "atm_total >= 0 AND atm_domestic >= 0 AND atm_eu >= 0 AND atm_non_eu >= 0",
            name="ck_monthly_stats_atm_non_negative",
        ),
    )
    op.create_index("ix_monthly_stats_period_start", "monthly_stats", ["period_start"])

    op.create_table(
        "forecast_runs",
        sa.Column("id", sa.Integer, sa.Identity(always=False), primary_key=True),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("trained_through", sa.Date, nullable=False),
        sa.Column("horizon_months", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("model_name", "trained_through", name="uq_forecast_runs_model_trained_through"),
        sa.CheckConstraint("horizon_months BETWEEN 1 AND 36", name="ck_forecast_runs_horizon"),
    )

    op.create_table(
        "forecast_values",
        sa.Column("run_id", sa.Integer, sa.ForeignKey("forecast_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("airport_code", sa.String(3), sa.ForeignKey("airports.code"), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("predicted_total_pax", sa.Numeric(12, 1), nullable=False),
        sa.PrimaryKeyConstraint("run_id", "airport_code", "period_start", name="pk_forecast_values"),
        sa.CheckConstraint("extract(day from period_start) = 1", name="ck_forecast_values_first_of_month"),
    )

    op.create_table(
        "model_evaluations",
        sa.Column("airport_code", sa.String(3), sa.ForeignKey("airports.code"), nullable=False),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("covid_excluded", sa.Boolean, nullable=False),
        sa.Column("mae", sa.Numeric(12, 2), nullable=False),
        sa.Column("rmse", sa.Numeric(12, 2), nullable=True),
        sa.Column("mape", sa.Numeric(7, 2), nullable=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.PrimaryKeyConstraint("airport_code", "model_name", "covid_excluded", name="pk_model_evaluations"),
        sa.CheckConstraint("mae >= 0", name="ck_model_evaluations_mae_non_negative"),
    )


def downgrade() -> None:
    op.drop_table("model_evaluations")
    op.drop_table("forecast_values")
    op.drop_table("forecast_runs")
    op.drop_index("ix_monthly_stats_period_start", table_name="monthly_stats")
    op.drop_table("monthly_stats")
    op.drop_table("airports")
