from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.model import (
    AgentModel,
    BorrowerModel,
    CallModel,
    PendingEventModel,
    ReservationModel,
)
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallEvent, CallState


class UnknownProviderEvent(RuntimeError):
    pass


class InvalidCallEvent(RuntimeError):
    pass


_SETUP = (
    CallState.RESERVED,
    CallState.INITIATED,
    CallState.RINGING,
    CallState.ANSWERED,
)

_TERMINAL = (
    CallState.COMPLETED,
    CallState.FAILED,
    CallState.CANCELLED,
)


class ProviderEventProcessor:
    def __init__(self, session: Session):
        self.session = session

    def handle(self, call_id: int, event: CallEvent) -> None:
        call = self.session.get(CallModel, call_id)

        if call is None:
            raise InvalidCallEvent(f"Call {call_id} not found")

        if self._already_applied(call.state, event):
            return

        if event == CallEvent.RINGING:
            self._ring(call_id)
        elif event == CallEvent.ANSWERED:
            self._answer(call_id)
            self._connect_if_agent_waiting(call_id)
            self._apply_pending_completed(call_id)
        elif event == CallEvent.COMPLETED:
            self._handle_completed(call_id, call.state)
        elif event == CallEvent.FAIL:
            self._fail(call_id)
        else:
            raise UnknownProviderEvent(
                f"Unsupported provider event: {event.value}"
            )

        self.session.flush()
        self.session.expire_all()

    def _already_applied(self, state: CallState, event: CallEvent) -> bool:
        if event == CallEvent.RINGING:
            return state in (
                CallState.RINGING,
                CallState.ANSWERED,
                CallState.CONNECTED,
                *_TERMINAL,
            )

        if event == CallEvent.ANSWERED:
            return state in (
                CallState.ANSWERED,
                CallState.CONNECTED,
                *_TERMINAL,
            )

        if event == CallEvent.COMPLETED:
            return state == CallState.COMPLETED

        if event == CallEvent.FAIL:
            return state in (CallState.FAILED, CallState.CANCELLED)

        return False

    def _handle_completed(self, call_id: int, state: CallState) -> None:
        if state == CallState.CONNECTED:
            self._complete(call_id)
            return

        if state in _SETUP:
            self._stash(call_id, CallEvent.COMPLETED)
            return

        if state in _TERMINAL:
            return

        raise InvalidCallEvent(f"Call {call_id} cannot COMPLETED")

    def _stash(self, call_id: int, event: CallEvent) -> None:
        exists = self.session.execute(
            select(PendingEventModel).where(
                PendingEventModel.call_id == call_id,
                PendingEventModel.event == event.value,
            )
        ).scalar_one_or_none()

        if exists is not None:
            return

        self.session.add(
            PendingEventModel(
                call_id=call_id,
                event=event.value,
            )
        )

    def _apply_pending_completed(self, call_id: int) -> None:
        self.session.flush()
        call = self.session.get(CallModel, call_id)

        if call is not None:
            self.session.expire(call)
            call = self.session.get(CallModel, call_id)
        pending = self.session.execute(
            select(PendingEventModel).where(
                PendingEventModel.call_id == call_id,
                PendingEventModel.event == CallEvent.COMPLETED.value,
            )
        ).scalars().all()

        if not pending:
            return

        call = self.session.get(CallModel, call_id)

        if call is not None and call.state == CallState.CONNECTED:
            self._complete(call_id)

        for row in pending:
            self.session.delete(row)

    def _ring(self, call_id: int) -> None:
        result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.INITIATED,
            )
            .values(state=CallState.RINGING)
        )

        if result.rowcount != 1:
            raise InvalidCallEvent(
                f"Call {call_id} cannot RINGING"
            )

    def _answer(self, call_id: int) -> None:
        result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state.in_(
                    (CallState.INITIATED, CallState.RINGING)
                ),
            )
            .values(state=CallState.ANSWERED)
        )

        if result.rowcount != 1:
            raise InvalidCallEvent(
                f"Call {call_id} cannot ANSWERED"
            )

    def _connect_if_agent_waiting(self, call_id: int) -> None:
        reservation = self.session.execute(
            select(ReservationModel).where(
                ReservationModel.call_id == call_id
            )
        ).scalar_one_or_none()

        if reservation is None:
            return

        agent_result = self.session.execute(
            update(AgentModel)
            .where(
                AgentModel.id == reservation.agent_id,
                AgentModel.state == AgentState.DIALING,
            )
            .values(state=AgentState.CONNECTED)
        )

        if agent_result.rowcount != 1:
            return

        self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.ANSWERED,
            )
            .values(state=CallState.CONNECTED)
        )

    def _complete(self, call_id: int) -> None:
        call_result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state == CallState.CONNECTED,
            )
            .values(state=CallState.COMPLETED)
        )

        if call_result.rowcount != 1:
            raise InvalidCallEvent(
                f"Call {call_id} cannot COMPLETED"
            )

        reservation = self.session.execute(
            select(ReservationModel).where(
                ReservationModel.call_id == call_id
            )
        ).scalar_one_or_none()

        if reservation is not None:
            self.session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == reservation.agent_id,
                    AgentModel.state == AgentState.CONNECTED,
                )
                .values(state=AgentState.WRAP_UP)
            )

        call = self.session.get(CallModel, call_id)

        self.session.execute(
            update(BorrowerModel)
            .where(
                BorrowerModel.id == call.borrower_id,
                BorrowerModel.state == BorrowerState.IN_CALL,
            )
            .values(state=BorrowerState.COMPLETED)
        )

    def _fail(self, call_id: int) -> None:
        call_result = self.session.execute(
            update(CallModel)
            .where(
                CallModel.id == call_id,
                CallModel.state.in_(
                    (
                        CallState.RESERVED,
                        CallState.INITIATED,
                        CallState.RINGING,
                        CallState.ANSWERED,
                    )
                ),
            )
            .values(state=CallState.FAILED)
        )

        if call_result.rowcount != 1:
            raise InvalidCallEvent(
                f"Call {call_id} cannot FAIL"
            )

        reservation = self.session.execute(
            select(ReservationModel).where(
                ReservationModel.call_id == call_id
            )
        ).scalar_one_or_none()

        call = self.session.get(CallModel, call_id)

        if reservation is not None:
            self.session.execute(
                update(AgentModel)
                .where(
                    AgentModel.id == reservation.agent_id,
                    AgentModel.state.in_(
                        (
                            AgentState.RESERVED,
                            AgentState.DIALING,
                            AgentState.CONNECTED,
                        )
                    ),
                )
                .values(state=AgentState.AVAILABLE)
            )

        self.session.execute(
            update(BorrowerModel)
            .where(
                BorrowerModel.id == call.borrower_id,
                BorrowerModel.state == BorrowerState.IN_CALL,
            )
            .values(state=BorrowerState.ELIGIBLE)
        )
