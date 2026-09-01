from dataclasses import dataclass
from enum import Enum


class BorrowerState(Enum):
    ELIGIBLE = "ELIGIBLE"
    IN_CALL = "IN_CALL"
    COMPLETED = "COMPLETED"


class BorrowerEvent(Enum):
    RESERVE = "RESERVE"
    RELEASE = "RELEASE"
    COMPLETE = "COMPLETE"


@dataclass
class Borrower:
    id: int
    phone_number: str
    state: BorrowerState = BorrowerState.ELIGIBLE

    def __post_init__(self):
        self.phone_number = self.phone_number.strip()

        if not self.phone_number:
            raise ValueError("phone_number is required")

    def transition(self, event: BorrowerEvent) -> None:
        transitions = {
            (BorrowerState.ELIGIBLE, BorrowerEvent.RESERVE):
                BorrowerState.IN_CALL,

            (BorrowerState.IN_CALL, BorrowerEvent.RELEASE):
                BorrowerState.ELIGIBLE,

            (BorrowerState.IN_CALL, BorrowerEvent.COMPLETE):
                BorrowerState.COMPLETED,
        }

        transition = transitions.get((self.state, event))

        if transition is None:
            raise ValueError(
                f"Invalid transition: "
                f"{self.state.value} + {event.value}"
            )

        self.state = transition
