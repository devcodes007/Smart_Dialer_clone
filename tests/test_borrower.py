import pytest

from app.domain.borrower import Borrower, BorrowerEvent, BorrowerState


def test_borrower_starts_eligible():

    borrower = Borrower(
        id=1,
        phone_number="5550001001",
    )

    assert borrower.state == BorrowerState.ELIGIBLE
    assert borrower.phone_number == "5550001001"


def test_borrower_can_be_reserved():

    borrower = Borrower(
        id=1,
        phone_number="5550001001",
    )

    borrower.transition(BorrowerEvent.RESERVE)

    assert borrower.state == BorrowerState.IN_CALL


def test_borrower_is_released_after_failed_attempt():

    borrower = Borrower(
        id=1,
        phone_number="5550001001",
    )

    borrower.transition(BorrowerEvent.RESERVE)
    borrower.transition(BorrowerEvent.RELEASE)

    assert borrower.state == BorrowerState.ELIGIBLE


def test_borrower_completes_after_successful_call():

    borrower = Borrower(
        id=1,
        phone_number="5550001001",
    )

    borrower.transition(BorrowerEvent.RESERVE)
    borrower.transition(BorrowerEvent.COMPLETE)

    assert borrower.state == BorrowerState.COMPLETED


def test_borrower_cannot_be_reserved_twice():

    borrower = Borrower(
        id=1,
        phone_number="5550001001",
    )

    borrower.transition(BorrowerEvent.RESERVE)

    with pytest.raises(ValueError):

        borrower.transition(BorrowerEvent.RESERVE)


def test_phone_number_is_required():

    with pytest.raises(ValueError):

        Borrower(
            id=1,
            phone_number="   ",
        )
