import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.model import (  # noqa: F401
    AgentModel,
    BorrowerModel,
    CallModel,
    PendingEventModel,
    ReservationModel,
)
from app.simulation.runner import run_scenario


def main() -> None:
    load_dotenv()
    url = os.getenv("TEST_DATABASE_URL")

    if not url:
        raise RuntimeError(
            "TEST_DATABASE_URL is not set. Simulation runs only against "
            "smart_dialer_test so it cannot pollute the development database."
        )

    engine = create_engine(url, echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    scenarios = (
        ("A", 0.20, 120, 0),
        ("B", 0.50, 90, 100),
        ("C", 0.70, 180, 200),
        ("D-low", 0.15, 60, 300),
        ("D-high", 0.80, 150, 400),
    )

    with Session() as session:
        for name, rate, talk, offset in scenarios:
            row = run_scenario(
                session,
                name,
                rate,
                talk,
                id_offset=offset,
            )
            session.commit()
            print(row)

    engine.dispose()


if __name__ == "__main__":
    main()
