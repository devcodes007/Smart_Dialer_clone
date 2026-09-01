import math

from app.safety.controller import DialerSnapshot


class PredictivePacingEngine:
    """
    Recommends how many new originates to attempt.

    Never places a call. Safety Controller must authorize the request.
    """

    def __init__(
        self,
        answer_rate: float,
        avg_talk_seconds: float,
        setup_seconds: float = 5.0,
    ):
        self.answer_rate = answer_rate
        self.avg_talk_seconds = avg_talk_seconds
        self.setup_seconds = setup_seconds

    def recommend(self, snapshot: DialerSnapshot) -> int:
        if not snapshot.provider_healthy:
            return 0

        if self.answer_rate <= 0:
            return 0

        soon_free = 0.0

        if self.avg_talk_seconds > 0:
            soon_free = (
                snapshot.connected * self.setup_seconds / self.avg_talk_seconds
            )

        target_answers = snapshot.available_agents + soon_free
        needed = math.ceil(target_answers / self.answer_rate)
        return max(0, int(needed - snapshot.in_flight))
