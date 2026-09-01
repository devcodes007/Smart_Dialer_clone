from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.allocation.service import AgentReservationService
from app.db.model import AgentModel, CallModel
from app.domain.agent import AgentState
from app.domain.call import CallState


def _try_allocate(session_factory, agent_id, call_id, worker_id):

    with session_factory() as session:

        service = AgentReservationService(session)

        try:
            reservation_id = service.allocate(
                agent_id=agent_id,
                call_id=call_id,
                worker_id=worker_id,
            )

            session.commit()

            return {
                "success": True,
                "reservation_id": reservation_id,
            }

        except RuntimeError:
            session.rollback()

            return {
                "success": False,
                "reservation_id": None,
            }


def test_only_one_worker_can_allocate_same_agent(db_reset, session_factory):

    with session_factory() as session:
        session.add(
            AgentModel(
                id=500,
                state=AgentState.AVAILABLE,
            )
        )

        for call_id in range(1, 11):
            session.add(
                CallModel(
                    id=call_id,
                    borrower_id=call_id,
                    state=CallState.QUEUED,
                )
            )

        session.commit()

    with ThreadPoolExecutor(max_workers=10) as executor:

        results = list(
            executor.map(
                lambda worker_number: _try_allocate(
                    session_factory,
                    agent_id=500,
                    call_id=worker_number,
                    worker_id=f"worker-{worker_number}",
                ),
                range(1, 11),
            )
        )

    successful = [result for result in results if result["success"]]
    failed = [result for result in results if not result["success"]]

    assert len(successful) == 1
    assert len(failed) == 9

    with session_factory() as session:

        agent = session.get(AgentModel, 500)
        reserved_calls = session.execute(
            select(CallModel).where(CallModel.state == CallState.RESERVED)
        ).scalars().all()
        queued_calls = session.execute(
            select(CallModel).where(CallModel.state == CallState.QUEUED)
        ).scalars().all()

        assert agent.state == AgentState.RESERVED
        assert len(reserved_calls) == 1
        assert len(queued_calls) == 9


def test_only_one_worker_can_allocate_same_call(db_reset, session_factory):

    with session_factory() as session:
        session.add(
            CallModel(
                id=900,
                borrower_id=900,
                state=CallState.QUEUED,
            )
        )

        for agent_id in range(1, 11):
            session.add(
                AgentModel(
                    id=agent_id,
                    state=AgentState.AVAILABLE,
                )
            )

        session.commit()

    with ThreadPoolExecutor(max_workers=10) as executor:

        results = list(
            executor.map(
                lambda worker_number: _try_allocate(
                    session_factory,
                    agent_id=worker_number,
                    call_id=900,
                    worker_id=f"worker-{worker_number}",
                ),
                range(1, 11),
            )
        )

    successful = [result for result in results if result["success"]]
    failed = [result for result in results if not result["success"]]

    assert len(successful) == 1
    assert len(failed) == 9

    with session_factory() as session:

        call = session.get(CallModel, 900)
        reserved_agents = session.execute(
            select(AgentModel).where(
                AgentModel.state == AgentState.RESERVED
            )
        ).scalars().all()
        available_agents = session.execute(
            select(AgentModel).where(
                AgentModel.state == AgentState.AVAILABLE
            )
        ).scalars().all()

        assert call.state == CallState.RESERVED
        assert len(reserved_agents) == 1
        assert len(available_agents) == 9
