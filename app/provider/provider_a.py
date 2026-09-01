import random

from app.provider.base import ProviderError, TelecomProvider


class MockProviderA(TelecomProvider):
    """Fast and reliable. Low failure rate."""

    def __init__(self, failure_rate: float = 0.01, rng: random.Random | None = None):
        self.failure_rate = failure_rate
        self.rng = rng or random.Random()
        self.placed_calls: list[tuple[int, str]] = []

    def place_call(self, call_id: int, phone_number: str) -> None:
        if self.rng.random() < self.failure_rate:
            raise ProviderError("provider A originate failed")

        self.placed_calls.append((call_id, phone_number))
