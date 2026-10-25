"""Access to this component's own PostgreSQL database."""

from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Base class for this service's tables."""


engine = create_engine(get_settings().database_url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one database session per request."""
    with SessionLocal() as session:
        yield session


def get_db() -> Iterator[Session]:
    """Compatibility dependency: one database session per request."""
    yield from get_session()


def init_models() -> None:
    """Create tables only for local development and isolated test databases.

    Production schema changes must go through Alembic migrations.
    """
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine, checkfirst=True)


def database_ok() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
