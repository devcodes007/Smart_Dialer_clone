from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.model import AgentModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.call import CallState


class AgentReservationService:

    def __init__(self, session: Session):
        self.session = session

    def allocate(
        self,
        agent_id: int,
        call_id: int,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> UUID:
        """
        Atomically claim one agent and one call, then create a reservation.

        Lock order is always agent, then call. Every worker must use the
        same order so two-resource allocation cannot deadlock.

        This method flushes. It does not commit.
        """

        reservation_id = uuid4()

        now = datetime.now(timezone.utc)

        expires_at = now + timedelta(
            seconds=lease_seconds
        )

        agent_result = self.session.execute(
            update(AgentModel)
            .where(
                AgentModel.id == agent_id,
                AgentModel.state == AgentState.AVAILABLE,
            )
            .values(
                state=AgentState.RESERVED,
            )
        )

        if agent_result.rowcount != 1:
            raise RuntimeError(
                f"Agent {agent_id} is not available"
            )

        call_result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.QUEUED,
            )
            .values(
                state=CallState.RESERVED,
            )
        )

        if call_result.rowcount != 1:
            raise RuntimeError(
                f"Call {call_id} is not available"
            )

        reservation = ReservationModel(
            reservation_id=str(reservation_id),
            agent_id=agent_id,
            call_id=call_id,
            worker_id=worker_id,
            created_at=now,
            expires_at=expires_at,
        )

        self.session.add(reservation)

        self.session.flush()

        return reservation_id
