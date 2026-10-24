"""Test fixtures.

Tests run against a real PostgreSQL database (not SQLite): the schema relies on
Postgres check constraints, ON CONFLICT upserts and DISTINCT ON, and the index
tests read Postgres query plans. CI provides one as a service container;
locally, `docker compose up db` from explorer/ is enough.
"""
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session
from app.loader import load_all
from app.main import app

API_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = API_DIR.parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/explorer_test"
)
TABLES = ["forecast_values", "forecast_runs", "model_evaluations", "monthly_stats", "airports"]


def alembic_config() -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(API_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    """A freshly migrated test database: rebuilt from nothing on every run."""
    config = alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "head")
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def empty_db(engine: Engine) -> Engine:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    return engine


@pytest.fixture
def loaded_db(empty_db: Engine) -> Engine:
    """The real project data: 414 monthly rows, the ETS forecast, evaluation results."""
    load_all(empty_db, REPO_ROOT)
    return empty_db


@pytest.fixture
def client(loaded_db: Engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=loaded_db, expire_on_commit=False)

    def override_session() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
