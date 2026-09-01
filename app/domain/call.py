from dataclasses import dataclass
from enum import Enum


class CallState(Enum):
    QUEUED = "QUEUED"
    RESERVED = "RESERVED"
    INITIATED = "INITIATED"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CallEvent(Enum):
    RESERVE = "RESERVE"
    INITIATE = "INITIATE"
    RINGING = "RINGING"
    ANSWERED = "ANSWERED"
    CONNECT = "CONNECT"
    COMPLETED = "COMPLETED"
    FAIL = "FAIL"
    CANCEL = "CANCEL"


@dataclass
class Call:
    id: int
    borrower_id: int
    state: CallState = CallState.QUEUED

    def transition(self, event: CallEvent) -> None:
        transitions = {
            (CallState.QUEUED, CallEvent.RESERVE):
                CallState.RESERVED,

            (CallState.QUEUED, CallEvent.CANCEL):
                CallState.CANCELLED,

            (CallState.RESERVED, CallEvent.INITIATE):
                CallState.INITIATED,

            (CallState.RESERVED, CallEvent.FAIL):
                CallState.FAILED,

            (CallState.RESERVED, CallEvent.CANCEL):
                CallState.CANCELLED,

            (CallState.INITIATED, CallEvent.RINGING):
                CallState.RINGING,

            (CallState.INITIATED, CallEvent.ANSWERED):
                CallState.ANSWERED,

            (CallState.INITIATED, CallEvent.FAIL):
                CallState.FAILED,

            (CallState.INITIATED, CallEvent.CANCEL):
                CallState.CANCELLED,

            (CallState.RINGING, CallEvent.ANSWERED):
                CallState.ANSWERED,

            (CallState.RINGING, CallEvent.FAIL):
                CallState.FAILED,

            (CallState.RINGING, CallEvent.CANCEL):
                CallState.CANCELLED,

            (CallState.ANSWERED, CallEvent.CONNECT):
                CallState.CONNECTED,

            (CallState.ANSWERED, CallEvent.FAIL):
                CallState.FAILED,

            (CallState.CONNECTED, CallEvent.COMPLETED):
                CallState.COMPLETED,
        }

        transition = transitions.get((self.state, event))

        if transition is None:
            raise ValueError(
                f"Invalid transition: "
                f"{self.state.value} + {event.value}"
            )

        self.state = transition
