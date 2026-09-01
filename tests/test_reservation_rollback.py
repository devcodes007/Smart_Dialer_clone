from sqlalchemy import select

from app.allocation.service import AgentReservationService
from app.db.model import AgentModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.call import CallState


def test_agent_and_call_roll_back_when_transaction_fails(
    db_reset,
    session_factory,
):
    """
    allocate() flushes but does not commit.

    BEGIN → insert AVAILABLE agent and QUEUED call → COMMIT
    BEGIN → allocate (flush) → simulated failure → ROLLBACK
    BEGIN → agent AVAILABLE, call QUEUED, reservation gone
    """

    with session_factory() as session:
        session.add(
            AgentModel(
                id=2000,
                state=AgentState.AVAILABLE,
            )
        )
        session.add(
            CallModel(
                id=600,
                borrower_id=600,
                state=CallState.QUEUED,
            )
        )
        session.commit()

    with session_factory() as session:
        service = AgentReservationService(session)

        try:
            service.allocate(
                agent_id=2000,
                call_id=600,
                worker_id="worker-rollback-test",
            )

            raise RuntimeError("Simulated failure after allocation")

        except RuntimeError:
            session.rollback()

    with session_factory() as session:
        saved_agent = session.get(AgentModel, 2000)
        saved_call = session.get(CallModel, 600)
        saved_reservation = session.execute(
            select(ReservationModel).where(
                ReservationModel.agent_id == 2000
            )
        ).scalar_one_or_none()

        assert saved_agent.state == AgentState.AVAILABLE
        assert saved_call.state == CallState.QUEUED
        assert saved_reservation is None


def test_failed_call_claim_does_not_keep_agent(
    db_reset,
    session_factory,
):
    """
    If the agent UPDATE succeeds and the call UPDATE fails, the
    caller must roll back. Otherwise the agent would sit RESERVED
    with no reservation row.
    """

    with session_factory() as session:
        session.add(
            AgentModel(
                id=2001,
                state=AgentState.AVAILABLE,
            )
        )
        session.add(
            CallModel(
                id=601,
                borrower_id=601,
                state=CallState.RESERVED,
            )
        )
        session.commit()

    with session_factory() as session:
        service = AgentReservationService(session)

        try:
            service.allocate(
                agent_id=2001,
                call_id=601,
                worker_id="worker-partial-fail",
            )
        except RuntimeError:
            session.rollback()

    with session_factory() as session:
        saved_agent = session.get(AgentModel, 2001)
        saved_call = session.get(CallModel, 601)

        assert saved_agent.state == AgentState.AVAILABLE
        assert saved_call.state == CallState.RESERVED
