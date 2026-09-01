from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.allocation.service import AgentReservationService, BorrowerNotEligible
from app.db.model import BorrowerModel, CallModel
from app.dialer.progressive import PlacedCall
from app.domain.borrower import BorrowerState
from app.domain.call import CallState
from app.provider.base import ProviderError, TelecomProvider


class PredictiveDialer:
    """
    Originate calls without an agent already reserved.

    Used only after Safety Controller allows overdial.
    """

    def __init__(self, session: Session, provider: TelecomProvider):
        self.session = session
        self.provider = provider
        self.allocator = AgentReservationService(session)

    def originate_unmatched(
        self,
        worker_id: str,
        limit: int,
    ) -> list[PlacedCall]:
        if limit <= 0:
            return []

        placed: list[PlacedCall] = []
        skip_borrowers: set[int] = set()

        while len(placed) < limit:
            borrower_id = self._next_eligible_borrower(skip_borrowers)

            if borrower_id is None:
                return placed

            nested = self.session.begin_nested()

            try:
                self.allocator.claim_borrower(borrower_id)
                call_id = self._create_queued_call(borrower_id)
                borrower = self.session.get(BorrowerModel, borrower_id)
                self.provider.place_call(call_id, borrower.phone_number)
                self._mark_initiated(call_id)
                nested.commit()
                placed.append(
                    PlacedCall(
                        call_id=call_id,
                        borrower_id=borrower_id,
                    )
                )
            except (BorrowerNotEligible, ProviderError):
                nested.rollback()
                skip_borrowers.add(borrower_id)

        return placed

    def _next_eligible_borrower(self, skip: set[int]) -> int | None:
        query = select(BorrowerModel.id).where(
            BorrowerModel.state == BorrowerState.ELIGIBLE,
        )

        if skip:
            query = query.where(BorrowerModel.id.not_in(skip))

        query = query.order_by(BorrowerModel.id).limit(1)
        return self.session.execute(query).scalar_one_or_none()

    def _create_queued_call(self, borrower_id: int) -> int:
        call = CallModel(
            borrower_id=borrower_id,
            state=CallState.QUEUED,
        )
        self.session.add(call)
        self.session.flush()
        return call.id

    def _mark_initiated(self, call_id: int) -> None:
        result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.QUEUED,
            )
            .values(state=CallState.INITIATED)
        )

        if result.rowcount != 1:
            raise RuntimeError(f"Call {call_id} could not be initiated")
