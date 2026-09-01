import os
import re
from urllib.parse import urlparse, urlunparse

import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import Base
from app.db.model import AgentModel, BorrowerModel, CallModel, PendingEventModel, ReservationModel  # noqa: F401


load_dotenv()


def _test_database_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("TEST_DATABASE_URL is not set")
    return url


def _database_name(url: str) -> str:
    name = urlparse(url).path.lstrip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise RuntimeError(
            "TEST_DATABASE_URL database name must be a simple identifier"
        )
    return name


def _ensure_database_exists(url: str) -> None:
    parsed = urlparse(url)
    db_name = _database_name(url)
    admin_url = urlunparse(parsed._replace(path="/postgres"))
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": db_name},
            ).scalar()
            if not exists:
                connection.execute(text(f"CREATE DATABASE {db_name}"))
    finally:
        admin_engine.dispose()


def _truncate_all(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE pending_events, reservations, calls, agents, borrowers "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture(scope="session")
def test_engine():
    url = _test_database_url()
    _ensure_database_exists(url)

    engine = create_engine(url, echo=False)
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "ALTER TABLE calls "
                "ADD COLUMN IF NOT EXISTS borrower_id "
                "INTEGER NOT NULL DEFAULT 0"
            )
        )

    yield engine

    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(test_engine):
    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )


@pytest.fixture
def db_session(test_engine):
    """
    Isolated session for tests that should not commit.

    The session joins an outer transaction through a SAVEPOINT.
    session.rollback() only undoes the savepoint.
    Fixture teardown rolls back the outer transaction, so nothing
    is left in smart_dialer_test.
    """
    _truncate_all(test_engine)

    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_reset(test_engine):
    """
    For tests that MUST commit, such as concurrency.

    Real commits are required when multiple sessions have to
    compete. Truncate before and after so committed rows cannot
    leak into the next test.
    """
    _truncate_all(test_engine)
    yield
    _truncate_all(test_engine)
