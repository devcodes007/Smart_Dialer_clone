from app.db.database import Base, engine
from app.db.model import (  # noqa: F401
    AgentModel,
    BorrowerModel,
    CallModel,
    PendingEventModel,
    ReservationModel,
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables created successfully.")
