from sqlalchemy import select

from app.db.model import BorrowerModel
from app.domain.borrower import BorrowerState


def test_create_and_read_borrower(db_session):

    borrower = BorrowerModel(
        id=1,
        phone_number="5550001001",
        state=BorrowerState.ELIGIBLE,
    )

    db_session.add(borrower)
    db_session.flush()

    result = db_session.execute(
        select(BorrowerModel).where(BorrowerModel.id == 1)
    )

    saved_borrower = result.scalar_one()

    assert saved_borrower.id == 1
    assert saved_borrower.phone_number == "5550001001"
    assert saved_borrower.state == BorrowerState.ELIGIBLE
