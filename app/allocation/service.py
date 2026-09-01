from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.db.model import AgentModel, BorrowerModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState


class AgentNotAvailable(RuntimeError):
    pass


class CallNotAvailable(RuntimeError):
    pass


class BorrowerNotEligible(RuntimeError):
    pass


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
            raise AgentNotAvailable(
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
            raise CallNotAvailable(
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

    def bind_agent_to_answered_call(
        self,
        agent_id: int,
        call_id: int,
        worker_id: str,
        lease_seconds: int = 30,
    ) -> UUID:
        reservation_id = uuid4()
        now = datetime.now(timezone.utc)

        agent_result = self.session.execute(
            update(AgentModel)
            .where(
                AgentModel.id == agent_id,
                AgentModel.state == AgentState.AVAILABLE,
            )
            .values(
                state=AgentState.CONNECTED,
            )
        )

        if agent_result.rowcount != 1:
            raise AgentNotAvailable(
                f"Agent {agent_id} is not available"
            )

        call_result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.ANSWERED,
            )
            .values(
                state=CallState.CONNECTED,
            )
        )

        if call_result.rowcount != 1:
            raise CallNotAvailable(
                f"Call {call_id} is not answered"
            )

        self.session.add(
            ReservationModel(
                reservation_id=str(reservation_id),
                agent_id=agent_id,
                call_id=call_id,
                worker_id=worker_id,
                created_at=now,
                expires_at=now + timedelta(seconds=lease_seconds),
            )
        )
        self.session.flush()
        return reservation_id

    def claim_borrower(self, borrower_id: int) -> None:
        result = self.session.execute(
            update(BorrowerModel)
            .where(
                BorrowerModel.id == borrower_id,
                BorrowerModel.state == BorrowerState.ELIGIBLE,
            )
            .values(
                state=BorrowerState.IN_CALL,
            )
        )

        if result.rowcount != 1:
            raise BorrowerNotEligible(
                f"Borrower {borrower_id} is not eligible"
            )
