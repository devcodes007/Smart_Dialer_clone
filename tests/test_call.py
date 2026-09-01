import pytest

from app.domain.call import Call, CallEvent, CallState


def test_call_starts_queued():

    call = Call(id=1, borrower_id=10)

    assert call.state == CallState.QUEUED


def test_call_reservation():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)

    assert call.state == CallState.RESERVED


def test_call_can_be_initiated():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)

    assert call.state == CallState.INITIATED


def test_call_happy_path_completes():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)
    call.transition(CallEvent.RINGING)
    call.transition(CallEvent.ANSWERED)
    call.transition(CallEvent.CONNECT)
    call.transition(CallEvent.COMPLETED)

    assert call.state == CallState.COMPLETED


def test_ringing_can_be_skipped():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)
    call.transition(CallEvent.ANSWERED)

    assert call.state == CallState.ANSWERED


def test_call_can_fail_while_ringing():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)
    call.transition(CallEvent.RINGING)
    call.transition(CallEvent.FAIL)

    assert call.state == CallState.FAILED


def test_call_can_be_cancelled_during_setup():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)
    call.transition(CallEvent.CANCEL)

    assert call.state == CallState.CANCELLED


def test_answered_call_without_agent_fails():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)
    call.transition(CallEvent.ANSWERED)
    call.transition(CallEvent.FAIL)

    assert call.state == CallState.FAILED


def test_invalid_transition_is_rejected():

    call = Call(id=1, borrower_id=10)

    with pytest.raises(ValueError):

        call.transition(CallEvent.ANSWERED)


def test_completed_call_rejects_further_events():

    call = Call(id=1, borrower_id=10)

    call.transition(CallEvent.RESERVE)
    call.transition(CallEvent.INITIATE)
    call.transition(CallEvent.ANSWERED)
    call.transition(CallEvent.CONNECT)
    call.transition(CallEvent.COMPLETED)

    with pytest.raises(ValueError):

        call.transition(CallEvent.ANSWERED)
