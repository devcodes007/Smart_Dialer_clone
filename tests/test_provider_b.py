import random

import pytest

from app.domain.call import CallEvent
from app.provider.base import ProviderError
from app.provider.provider_b import MockProviderB


def test_provider_b_timeout():

    provider = MockProviderB(
        timeout_rate=1.0,
        rng=random.Random(0),
    )

    with pytest.raises(ProviderError):

        provider.place_call(call_id=1, phone_number="5550001001")

    assert provider.placed_calls == []
    assert provider.poll_events() == []


def test_provider_b_duplicate_events():

    provider = MockProviderB(
        timeout_rate=0.0,
        event_mode="duplicates",
    )

    provider.place_call(call_id=1, phone_number="5550001001")

    assert provider.poll_events() == [
        (1, CallEvent.ANSWERED),
        (1, CallEvent.ANSWERED),
        (1, CallEvent.ANSWERED),
        (1, CallEvent.COMPLETED),
    ]


def test_provider_b_out_of_order_events():

    provider = MockProviderB(
        timeout_rate=0.0,
        event_mode="out_of_order",
    )

    provider.place_call(call_id=1, phone_number="5550001001")

    assert provider.poll_events() == [
        (1, CallEvent.COMPLETED),
        (1, CallEvent.ANSWERED),
        (1, CallEvent.RINGING),
    ]
