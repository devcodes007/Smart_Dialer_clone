from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.db.model import AgentModel, BorrowerModel, CallModel, ReservationModel
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallEvent, CallState
from app.events.processor import ProviderEventProcessor


def _seed_live_call(session):
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
    now = datetime.now(timezone.utc)
    session.add(
        ReservationModel(
            reservation_id=str(uuid4()),
            agent_id=1,
            call_id=100,
            worker_id="worker-1",
            created_at=now,
            expires_at=now + timedelta(seconds=30),
        )
    )
    session.flush()


def test_ringing_then_answered_connects_waiting_agent(db_session):

    _seed_live_call(db_session)
    processor = ProviderEventProcessor(db_session)

    processor.handle(100, CallEvent.RINGING)
    processor.handle(100, CallEvent.ANSWERED)

    assert db_session.get(CallModel, 100).state == CallState.CONNECTED
    assert db_session.get(AgentModel, 1).state == AgentState.CONNECTED


def test_completed_ends_call_and_sends_agent_to_wrap_up(db_session):

    _seed_live_call(db_session)
    processor = ProviderEventProcessor(db_session)

    processor.handle(100, CallEvent.ANSWERED)
    processor.handle(100, CallEvent.COMPLETED)

    assert db_session.get(CallModel, 100).state == CallState.COMPLETED
    assert db_session.get(AgentModel, 1).state == AgentState.WRAP_UP
    assert db_session.get(BorrowerModel, 10).state == BorrowerState.COMPLETED


def test_fail_during_setup_releases_agent_and_borrower(db_session):

    _seed_live_call(db_session)
    processor = ProviderEventProcessor(db_session)

    processor.handle(100, CallEvent.FAIL)

    assert db_session.get(CallModel, 100).state == CallState.FAILED
    assert db_session.get(AgentModel, 1).state == AgentState.AVAILABLE
    assert db_session.get(BorrowerModel, 10).state == BorrowerState.ELIGIBLE


def test_out_of_order_completed_is_applied_after_answer(db_session):

    _seed_live_call(db_session)
    processor = ProviderEventProcessor(db_session)

    processor.handle(100, CallEvent.COMPLETED)
    processor.handle(100, CallEvent.ANSWERED)
    processor.handle(100, CallEvent.RINGING)

    assert db_session.get(CallModel, 100).state == CallState.COMPLETED
    assert db_session.get(AgentModel, 1).state == AgentState.WRAP_UP


def test_duplicate_answered_events_do_not_reapply(db_session):

    _seed_live_call(db_session)
    processor = ProviderEventProcessor(db_session)

    processor.handle(100, CallEvent.ANSWERED)
    processor.handle(100, CallEvent.ANSWERED)
    processor.handle(100, CallEvent.ANSWERED)
    processor.handle(100, CallEvent.COMPLETED)

    assert db_session.get(CallModel, 100).state == CallState.COMPLETED
    assert db_session.get(AgentModel, 1).state == AgentState.WRAP_UP


def test_duplicate_fail_is_ignored(db_session):

    _seed_live_call(db_session)
    processor = ProviderEventProcessor(db_session)

    processor.handle(100, CallEvent.FAIL)
    processor.handle(100, CallEvent.FAIL)

    assert db_session.get(CallModel, 100).state == CallState.FAILED
    assert db_session.get(AgentModel, 1).state == AgentState.AVAILABLE
