from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.db.model import AgentModel, BorrowerModel, CallModel, ReservationModel
from app.dialer.progressive import ProgressiveDialer
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState
from app.provider.provider_a import MockProviderA


def _add_agents(session, agent_ids):
    for agent_id in agent_ids:
        session.add(
            AgentModel(
                id=agent_id,
                state=AgentState.AVAILABLE,
            )
        )


def _add_borrowers(session, borrower_ids):
    for borrower_id in borrower_ids:
        session.add(
            BorrowerModel(
                id=borrower_id,
                phone_number=f"555000{borrower_id:04d}",
                state=BorrowerState.ELIGIBLE,
            )
        )


def _dialer(session):
    return ProgressiveDialer(session, MockProviderA(failure_rate=0.0))


def test_one_agent_one_borrower_places_one_call(db_session):

    _add_agents(db_session, [1])
    _add_borrowers(db_session, [10])
    db_session.flush()

    placed = _dialer(db_session).dial(worker_id="worker-1")

    assert len(placed) == 1
    assert placed[0].agent_id == 1
    assert placed[0].borrower_id == 10

    agent = db_session.get(AgentModel, 1)
    borrower = db_session.get(BorrowerModel, 10)
    call = db_session.get(CallModel, placed[0].call_id)

    assert agent.state == AgentState.DIALING
    assert borrower.state == BorrowerState.IN_CALL
    assert call.state == CallState.INITIATED
    assert call.borrower_id == 10


def test_does_not_dial_more_calls_than_available_agents(db_session):

    _add_agents(db_session, [1, 2])
    _add_borrowers(db_session, [10, 11, 12, 13, 14])
    db_session.flush()

    placed = _dialer(db_session).dial(worker_id="worker-1")

    assert len(placed) == 2

    still_eligible = db_session.execute(
        select(BorrowerModel).where(
            BorrowerModel.state == BorrowerState.ELIGIBLE
        )
    ).scalars().all()

    still_available = db_session.execute(
        select(AgentModel).where(
            AgentModel.state == AgentState.AVAILABLE
        )
    ).scalars().all()

    assert len(still_eligible) == 3
    assert len(still_available) == 0


def test_does_not_dial_more_calls_than_eligible_borrowers(db_session):

    _add_agents(db_session, [1, 2, 3, 4, 5])
    _add_borrowers(db_session, [10])
    db_session.flush()

    placed = _dialer(db_session).dial(worker_id="worker-1")

    assert len(placed) == 1

    still_available = db_session.execute(
        select(AgentModel).where(
            AgentModel.state == AgentState.AVAILABLE
        )
    ).scalars().all()

    assert len(still_available) == 4


def test_no_agents_places_no_calls(db_session):

    _add_borrowers(db_session, [10])
    db_session.flush()

    placed = _dialer(db_session).dial(worker_id="worker-1")

    assert placed == []

    borrower = db_session.get(BorrowerModel, 10)
    assert borrower.state == BorrowerState.ELIGIBLE


def test_provider_failure_does_not_keep_reservation(db_session):

    _add_agents(db_session, [1])
    _add_borrowers(db_session, [10])
    db_session.flush()

    dialer = ProgressiveDialer(
        db_session,
        MockProviderA(failure_rate=1.0),
    )
    placed = dialer.dial(worker_id="worker-1")

    assert placed == []
    assert db_session.get(AgentModel, 1).state == AgentState.AVAILABLE
    assert db_session.get(BorrowerModel, 10).state == BorrowerState.ELIGIBLE


def test_call_failure_during_setup_releases_agent_and_borrower(db_session):

    _add_agents(db_session, [1])
    _add_borrowers(db_session, [10])
    db_session.flush()

    dialer = _dialer(db_session)
    placed = dialer.dial(worker_id="worker-1")
    attempt = placed[0]

    dialer.handle_call_failed_during_setup(
        agent_id=attempt.agent_id,
        call_id=attempt.call_id,
        borrower_id=attempt.borrower_id,
    )

    agent = db_session.get(AgentModel, 1)
    borrower = db_session.get(BorrowerModel, 10)
    call = db_session.get(CallModel, attempt.call_id)

    assert agent.state == AgentState.AVAILABLE
    assert borrower.state == BorrowerState.ELIGIBLE
    assert call.state == CallState.FAILED


def test_agent_disappearing_during_setup_cancels_call(db_session):

    _add_agents(db_session, [1])
    _add_borrowers(db_session, [10])
    db_session.flush()

    dialer = _dialer(db_session)
    placed = dialer.dial(worker_id="worker-1")
    attempt = placed[0]

    dialer.handle_agent_disappeared_during_setup(
        agent_id=attempt.agent_id,
        call_id=attempt.call_id,
        borrower_id=attempt.borrower_id,
    )

    agent = db_session.get(AgentModel, 1)
    borrower = db_session.get(BorrowerModel, 10)
    call = db_session.get(CallModel, attempt.call_id)

    assert agent.state == AgentState.OFFLINE
    assert borrower.state == BorrowerState.ELIGIBLE
    assert call.state == CallState.CANCELLED


def test_two_workers_do_not_double_dial_the_same_borrower(
    db_reset,
    session_factory,
):

    with session_factory() as session:
        _add_agents(session, [1])
        _add_borrowers(session, [10])
        session.commit()

    def worker(worker_number: int):

        with session_factory() as session:

            placed = _dialer(session).dial(
                worker_id=f"worker-{worker_number}",
            )
            session.commit()
            return len(placed)

    with ThreadPoolExecutor(max_workers=10) as executor:
        placed_counts = list(executor.map(worker, range(1, 11)))

    assert sum(placed_counts) == 1

    with session_factory() as session:
        agent = session.get(AgentModel, 1)
        borrower = session.get(BorrowerModel, 10)
        initiated_calls = session.execute(
            select(CallModel).where(CallModel.state == CallState.INITIATED)
        ).scalars().all()
        reservations = session.execute(select(ReservationModel)).scalars().all()

        assert agent.state == AgentState.DIALING
        assert borrower.state == BorrowerState.IN_CALL
        assert len(initiated_calls) == 1
        assert len(reservations) == 1
