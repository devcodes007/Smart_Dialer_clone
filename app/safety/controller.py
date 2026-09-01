from dataclasses import dataclass


@dataclass(frozen=True)
class DialerSnapshot:
    available_agents: int
    eligible_borrowers: int
    in_flight: int
    connected: int
    answered_unmatched: int
    provider_healthy: bool = True


@dataclass(frozen=True)
class SafetyDecision:
    allowed: int
    fallback_progressive: bool
    reason: str


class SafetyController:
    """
    Final authority on how many calls may be originated.

    The pacing engine cannot skip this class.
    """

    def __init__(self, max_overdial_ratio: float = 0.5):
        self.max_overdial_ratio = max_overdial_ratio

    def authorize(
        self,
        requested: int,
        snapshot: DialerSnapshot,
        mode: str,
    ) -> SafetyDecision:
        if requested <= 0:
            return SafetyDecision(0, False, "nothing requested")

        if not snapshot.provider_healthy:
            return SafetyDecision(0, True, "provider unhealthy")

        progressive_cap = min(
            snapshot.available_agents,
            snapshot.eligible_borrowers,
        )

        if snapshot.answered_unmatched > 0:
            allowed = min(requested, progressive_cap)
            return SafetyDecision(
                allowed,
                True,
                "unmatched answered call, progressive fallback",
            )

        if mode == "progressive":
            allowed = min(requested, progressive_cap)
            return SafetyDecision(allowed, False, "progressive 1:1")

        overdial_slots = snapshot.available_agents + int(
            snapshot.available_agents * self.max_overdial_ratio
        )
        capacity = max(0, overdial_slots - snapshot.in_flight)
        allowed = min(
            requested,
            snapshot.eligible_borrowers,
            capacity,
        )

        if snapshot.available_agents == 0 and snapshot.connected == 0:
            allowed = 0

        return SafetyDecision(allowed, False, "predictive capped by safety")
