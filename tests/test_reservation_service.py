from app.allocation.service import AgentReservationService
from app.db.model import AgentModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.call import CallState


def test_allocate_reserves_agent_and_call(db_session):

    db_session.add(
        AgentModel(
            id=100,
            state=AgentState.AVAILABLE,
        )
    )
    db_session.add(
        CallModel(
            id=500,
            borrower_id=500,
            state=CallState.QUEUED,
        )
    )
    db_session.flush()

    service = AgentReservationService(db_session)

    reservation_id = service.allocate(
        agent_id=100,
        call_id=500,
        worker_id="worker-1",
    )

    saved_agent = db_session.get(AgentModel, 100)
    saved_call = db_session.get(CallModel, 500)
    saved_reservation = db_session.get(
        ReservationModel,
        str(reservation_id),
    )

    assert saved_agent.state == AgentState.RESERVED
    assert saved_call.state == CallState.RESERVED

    assert saved_reservation.agent_id == 100
    assert saved_reservation.call_id == 500
    assert saved_reservation.worker_id == "worker-1"
