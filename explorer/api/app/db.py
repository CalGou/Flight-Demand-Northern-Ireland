from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache
def get_engine() -> Engine:
    # pool_pre_ping guards against connections dropped by RDS/Lambda idling.
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed."""
    session = sessionmaker(bind=get_engine(), expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
