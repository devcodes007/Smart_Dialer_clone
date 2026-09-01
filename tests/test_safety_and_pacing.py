from app.pacing.engine import PredictivePacingEngine
from app.safety.controller import DialerSnapshot, SafetyController


def test_safety_caps_progressive_to_available_agents():

    decision = SafetyController().authorize(
        requested=20,
        snapshot=DialerSnapshot(
            available_agents=5,
            eligible_borrowers=40,
            in_flight=0,
            connected=0,
            answered_unmatched=0,
        ),
        mode="progressive",
    )

    assert decision.allowed == 5
    assert decision.fallback_progressive is False


def test_safety_falls_back_when_unmatched_answered_exists():

    decision = SafetyController().authorize(
        requested=20,
        snapshot=DialerSnapshot(
            available_agents=5,
            eligible_borrowers=40,
            in_flight=3,
            connected=0,
            answered_unmatched=2,
        ),
        mode="predictive",
    )

    assert decision.fallback_progressive is True
    assert decision.allowed == 5


def test_safety_rejects_when_provider_unhealthy():

    decision = SafetyController().authorize(
        requested=10,
        snapshot=DialerSnapshot(
            available_agents=5,
            eligible_borrowers=40,
            in_flight=0,
            connected=0,
            answered_unmatched=0,
            provider_healthy=False,
        ),
        mode="predictive",
    )

    assert decision.allowed == 0


def test_pacing_requests_more_than_agents_when_answer_rate_is_low():

    engine = PredictivePacingEngine(
        answer_rate=0.2,
        avg_talk_seconds=120,
    )
    requested = engine.recommend(
        DialerSnapshot(
            available_agents=10,
            eligible_borrowers=100,
            in_flight=0,
            connected=0,
            answered_unmatched=0,
        )
    )

    assert requested == 50
