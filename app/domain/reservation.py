from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Reservation:
    reservation_id: UUID
    agent_id: int
    call_id: int
    worker_id: str
    created_at: datetime
    expires_at: datetime

    def __post_init__(self):
        if self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")