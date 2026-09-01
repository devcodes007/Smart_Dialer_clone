from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.model import AgentModel, BorrowerModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState


class ReservationRecovery:
    """
    Worker crash / stale reservation recovery.

    If a reservation is past expires_at and the call is still in setup,
    release the agent, fail the call, and make the borrower eligible.
    """

    def __init__(self, session: Session):
        self.session = session

    def recover_expired(self, now: datetime | None = None) -> int:
        if now is None:
            now = datetime.now(timezone.utc)

        rows = self.session.execute(
            select(ReservationModel).where(
                ReservationModel.expires_at <= now
            )
        ).scalars().all()

        recovered = 0

        for reservation in rows:
            call = self.session.get(CallModel, reservation.call_id)

            if call is None:
                continue

            if call.state not in (
                CallState.QUEUED,
                CallState.RESERVED,
                CallState.INITIATED,
                CallState.RINGING,
            ):
                continue

            self.session.execute(
                update(CallModel)
                .where(CallModel.id == call.id)
                .values(state=CallState.FAILED)
            )
            self.session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == reservation.agent_id,
                    AgentModel.state.in_(
                        (AgentState.RESERVED, AgentState.DIALING)
                    ),
                )
                .values(state=AgentState.AVAILABLE)
            )
            self.session.execute(
                update(BorrowerModel)
                .where(
                    BorrowerModel.id == call.borrower_id,
                    BorrowerModel.state == BorrowerState.IN_CALL,
                )
                .values(state=BorrowerState.ELIGIBLE)
            )
            recovered += 1

        self.session.flush()
        self.session.expire_all()
        return recovered


def release_wrap_up(session: Session) -> int:
    result = session.execute(
        update(AgentModel)
        .where(AgentModel.state == AgentState.WRAP_UP)
        .values(state=AgentState.AVAILABLE)
    )
    session.flush()
    return result.rowcount or 0
