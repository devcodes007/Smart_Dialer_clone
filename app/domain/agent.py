from dataclasses import dataclass
from enum import Enum


class AgentState(Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    DIALING = "DIALING"
    CONNECTED = "CONNECTED"
    WRAP_UP = "WRAP_UP"
    PAUSED = "PAUSED"


class AgentEvent(Enum):
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
    RESERVE = "RESERVE"
    CALL_INITIATED = "CALL_INITIATED"
    CALL_ANSWERED = "CALL_ANSWERED"
    CALL_ENDED = "CALL_ENDED"
    WRAP_UP_COMPLETE = "WRAP_UP_COMPLETE"
    PAUSE = "PAUSE"
    UNPAUSE = "UNPAUSE"
    CALL_FAILED = "CALL_FAILED"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"
    RESERVATION_EXPIRED = "RESERVATION_EXPIRED"


@dataclass
class Agent:
    id: int
    state: AgentState = AgentState.OFFLINE

    def transition(self, event: AgentEvent) -> None:
        transitions = {
            (AgentState.OFFLINE, AgentEvent.LOGIN):
                AgentState.AVAILABLE,

            (AgentState.OFFLINE, AgentEvent.LOGOUT):
                AgentState.OFFLINE,

            (AgentState.AVAILABLE, AgentEvent.LOGOUT):
                AgentState.OFFLINE,

            (AgentState.AVAILABLE, AgentEvent.RESERVE):
                AgentState.RESERVED,

            (AgentState.AVAILABLE, AgentEvent.PAUSE):
                AgentState.PAUSED,

            (AgentState.RESERVED, AgentEvent.CALL_INITIATED):
                AgentState.DIALING,

            (AgentState.RESERVED, AgentEvent.RESERVATION_CANCELLED):
                AgentState.AVAILABLE,

            (AgentState.RESERVED, AgentEvent.RESERVATION_EXPIRED):
                AgentState.AVAILABLE,

            (AgentState.DIALING, AgentEvent.CALL_ANSWERED):
                AgentState.CONNECTED,

            (AgentState.DIALING, AgentEvent.CALL_FAILED):
                AgentState.AVAILABLE,

            (AgentState.CONNECTED, AgentEvent.CALL_ENDED):
                AgentState.WRAP_UP,

            (AgentState.WRAP_UP, AgentEvent.WRAP_UP_COMPLETE):
                AgentState.AVAILABLE,

            (AgentState.PAUSED, AgentEvent.UNPAUSE):
                AgentState.AVAILABLE,

            (AgentState.PAUSED, AgentEvent.LOGOUT):
                AgentState.OFFLINE,
        }

        transition = transitions.get((self.state, event))

        if transition is None:
            raise ValueError(
                f"Invalid transition: "
                f"{self.state.value} + {event.value}"
            )

        self.state = transition