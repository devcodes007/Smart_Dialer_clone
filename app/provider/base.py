from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    pass


class TelecomProvider(ABC):
    @abstractmethod
    def place_call(self, call_id: int, phone_number: str) -> None:
        """Start an outbound call. Raise ProviderError on failure."""
