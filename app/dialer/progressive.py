from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.allocation.service import (
    AgentNotAvailable,
    AgentReservationService,
    BorrowerNotEligible,
    CallNotAvailable,
)
from app.db.model import AgentModel, BorrowerModel, CallModel
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState
from app.provider.base import ProviderError, TelecomProvider


@dataclass(frozen=True)
class PlacedCall:
    call_id: int
    borrower_id: int
    reservation_id: UUID | None = None
    agent_id: int | None = None


class ProgressiveDialer:
    """
    One available agent → one outbound call.

    Places the call through TelecomProvider. Does not commit.
    """

    def __init__(self, session: Session, provider: TelecomProvider):
        self.session = session
        self.provider = provider
        self.allocator = AgentReservationService(session)

    def dial(self, worker_id: str, limit: int | None = None) -> list[PlacedCall]:
        if limit is not None and limit <= 0:
            return []

        placed: list[PlacedCall] = []
        skip_agents: set[int] = set()
        skip_borrowers: set[int] = set()

        while True:
            if limit is not None and len(placed) >= limit:
                return placed

            agent_id = self._next_available_agent(skip_agents)
            borrower_id = self._next_eligible_borrower(skip_borrowers)

            if agent_id is None or borrower_id is None:
                return placed

            nested = self.session.begin_nested()

            try:
                self.allocator.claim_borrower(borrower_id)
                call_id = self._create_queued_call(borrower_id)
                reservation_id = self.allocator.allocate(
                    agent_id=agent_id,
                    call_id=call_id,
                    worker_id=worker_id,
                )
                self._originate(call_id, agent_id, borrower_id)
                nested.commit()
                placed.append(
                    PlacedCall(
                        reservation_id=reservation_id,
                        agent_id=agent_id,
                        call_id=call_id,
                        borrower_id=borrower_id,
                    )
                )
            except AgentNotAvailable:
                nested.rollback()
                skip_agents.add(agent_id)
            except BorrowerNotEligible:
                nested.rollback()
                skip_borrowers.add(borrower_id)
            except CallNotAvailable:
                nested.rollback()
                skip_agents.add(agent_id)
                skip_borrowers.add(borrower_id)
            except ProviderError:
                nested.rollback()
                skip_borrowers.add(borrower_id)

    def handle_call_failed_during_setup(
        self,
        agent_id: int,
        call_id: int,
        borrower_id: int,
    ) -> None:
        """
        Busy, no-answer, or provider failure before the borrower is answered.

        Agent returns to AVAILABLE.
        Borrower becomes ELIGIBLE again so we can retry.
        Call is FAILED.
        """

        self._update_call_if_in_setup(call_id, CallState.FAILED)
        self._update_agent_if_in_setup(agent_id, AgentState.AVAILABLE)
        self._release_borrower(borrower_id)
        self.session.flush()

    def handle_agent_disappeared_during_setup(
        self,
        agent_id: int,
        call_id: int,
        borrower_id: int,
    ) -> None:
        """
        The reserved agent vanished before the call was answered.

        Agent goes OFFLINE, not AVAILABLE. They are gone.
        Call is CANCELLED.
        Borrower becomes ELIGIBLE again.
        """

        self._update_call_if_in_setup(call_id, CallState.CANCELLED)
        self._update_agent_if_in_setup(agent_id, AgentState.OFFLINE)
        self._release_borrower(borrower_id)
        self.session.flush()

    def _next_available_agent(self, skip: set[int]) -> int | None:
        query = select(AgentModel.id).where(
            AgentModel.state == AgentState.AVAILABLE,
        )

        if skip:
            query = query.where(AgentModel.id.not_in(skip))

        query = query.order_by(AgentModel.id).limit(1)

        return self.session.execute(query).scalar_one_or_none()

    def _next_eligible_borrower(self, skip: set[int]) -> int | None:
        query = select(BorrowerModel.id).where(
            BorrowerModel.state == BorrowerState.ELIGIBLE,
        )

        if skip:
            query = query.where(BorrowerModel.id.not_in(skip))

        query = query.order_by(BorrowerModel.id).limit(1)

        return self.session.execute(query).scalar_one_or_none()

    def _originate(
        self,
        call_id: int,
        agent_id: int,
        borrower_id: int,
    ) -> None:
        borrower = self.session.get(BorrowerModel, borrower_id)
        self.provider.place_call(call_id, borrower.phone_number)
        self._mark_initiated(agent_id, call_id)

    def _mark_initiated(self, agent_id: int, call_id: int) -> None:
        call_result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.RESERVED,
            )
            .values(state=CallState.INITIATED)
        )

        if call_result.rowcount != 1:
            raise RuntimeError(f"Call {call_id} could not be initiated")

        agent_result = self.session.execute(
            update(AgentModel)
            .where(
                AgentModel.id == agent_id,
                AgentModel.state == AgentState.RESERVED,
            )
            .values(state=AgentState.DIALING)
        )

        if agent_result.rowcount != 1:
            raise RuntimeError(f"Agent {agent_id} could not start dialing")

    def _create_queued_call(self, borrower_id: int) -> int:
        call = CallModel(
            borrower_id=borrower_id,
            state=CallState.QUEUED,
        )
        self.session.add(call)
        self.session.flush()
        return call.id

    def _update_call_if_in_setup(
        self,
        call_id: int,
        new_state: CallState,
    ) -> None:
        result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state.in_(
                    (
                        CallState.RESERVED,
                        CallState.INITIATED,
                        CallState.RINGING,
                    )
                ),
            )
            .values(state=new_state)
        )

        if result.rowcount != 1:
            raise RuntimeError(
                f"Call {call_id} is not in setup"
            )

    def _update_agent_if_in_setup(
        self,
        agent_id: int,
        new_state: AgentState,
    ) -> None:
        result = self.session.execute(
            update(AgentModel)
            .where(
                AgentModel.id == agent_id,
                AgentModel.state.in_(
                    (
                        AgentState.RESERVED,
                        AgentState.DIALING,
                    )
                ),
            )
            .values(state=new_state)
        )

        if result.rowcount != 1:
            raise RuntimeError(
                f"Agent {agent_id} is not in setup"
            )

    def _release_borrower(self, borrower_id: int) -> None:
        result = self.session.execute(
            update(BorrowerModel)
            .where(
                BorrowerModel.id == borrower_id,
                BorrowerModel.state == BorrowerState.IN_CALL,
            )
            .values(
                state=BorrowerState.ELIGIBLE,
            )
        )

        if result.rowcount != 1:
            raise RuntimeError(
                f"Borrower {borrower_id} is not in a call"
            )
