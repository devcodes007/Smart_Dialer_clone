import random

import pytest

from app.provider.base import ProviderError
from app.provider.provider_a import MockProviderA


def test_provider_a_places_call():

    provider = MockProviderA(failure_rate=0.0)

    provider.place_call(call_id=1, phone_number="5550001001")

    assert provider.placed_calls == [(1, "5550001001")]


def test_provider_a_can_fail():

    provider = MockProviderA(
        failure_rate=1.0,
        rng=random.Random(0),
    )

    with pytest.raises(ProviderError):

        provider.place_call(call_id=1, phone_number="5550001001")

    assert provider.placed_calls == []
