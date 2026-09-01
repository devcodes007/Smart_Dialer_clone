import random

from app.domain.call import CallEvent
from app.provider.base import ProviderError, TelecomProvider


class MockProviderB(TelecomProvider):
    """
    Slow and unreliable.

    Timeouts on originate. After a successful place, event sequences
    may be duplicated or out of order. The dialer does not consume
    those events; that is for the event processor.
    """

    def __init__(
        self,
        timeout_rate: float = 0.1,
        event_mode: str = "out_of_order",
        rng: random.Random | None = None,
    ):
        self.timeout_rate = timeout_rate
        self.event_mode = event_mode
        self.rng = rng or random.Random()
        self.placed_calls: list[tuple[int, str]] = []
        self._events: list[tuple[int, CallEvent]] = []

    def place_call(self, call_id: int, phone_number: str) -> None:
        if self.rng.random() < self.timeout_rate:
            raise ProviderError("provider B timeout")

        self.placed_calls.append((call_id, phone_number))
        self._events.extend(self._scripted_events(call_id))

    def poll_events(self) -> list[tuple[int, CallEvent]]:
        events = list(self._events)
        self._events.clear()
        return events

    def _scripted_events(self, call_id: int) -> list[tuple[int, CallEvent]]:
        if self.event_mode == "duplicates":
            return [
                (call_id, CallEvent.ANSWERED),
                (call_id, CallEvent.ANSWERED),
                (call_id, CallEvent.ANSWERED),
                (call_id, CallEvent.COMPLETED),
            ]

        if self.event_mode == "out_of_order":
            return [
                (call_id, CallEvent.COMPLETED),
                (call_id, CallEvent.ANSWERED),
                (call_id, CallEvent.RINGING),
            ]

        return [
            (call_id, CallEvent.RINGING),
            (call_id, CallEvent.ANSWERED),
            (call_id, CallEvent.COMPLETED),
        ]
