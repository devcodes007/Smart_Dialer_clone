from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.model import AgentModel, BorrowerModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState
from app.recovery.service import ReservationRecovery


def test_expired_reservation_releases_agent_and_borrower(db_reset, session_factory):

    now = datetime.now(timezone.utc)

    with session_factory() as session:
        session.add(AgentModel(id=1, state=AgentState.DIALING))
        session.add(
            BorrowerModel(
                id=10,
                phone_number="5550000010",
                state=BorrowerState.IN_CALL,
            )
        )
        session.add(
            CallModel(
                id=100,
                borrower_id=10,
                state=CallState.INITIATED,
            )
        )
        session.add(
            ReservationModel(
                reservation_id=str(uuid4()),
                agent_id=1,
                call_id=100,
                worker_id="worker-1",
                created_at=now - timedelta(seconds=60),
                expires_at=now - timedelta(seconds=10),
            )
        )
        session.commit()

    with session_factory() as session:
        recovered = ReservationRecovery(session).recover_expired(now=now)
        session.commit()
        assert recovered == 1

    with session_factory() as session:
        assert session.get(AgentModel, 1).state == AgentState.AVAILABLE
        assert session.get(CallModel, 100).state == CallState.FAILED
        assert session.get(BorrowerModel, 10).state == BorrowerState.ELIGIBLE
