import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.domain.reservation import Reservation


def test_reservation_creation():

    now = datetime.now(timezone.utc)

    reservation = Reservation(
        reservation_id=uuid4(),
        agent_id=1,
        call_id=101,
        worker_id="worker-1",
        created_at=now,
        expires_at=now + timedelta(seconds=30),
    )

    assert reservation.agent_id == 1
    assert reservation.call_id == 101
    assert reservation.worker_id == "worker-1"
    assert reservation.created_at == now
    assert reservation.expires_at == now + timedelta(seconds=30)