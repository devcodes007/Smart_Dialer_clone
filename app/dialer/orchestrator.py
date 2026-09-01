from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.allocation.service import AgentNotAvailable, AgentReservationService
from app.db.model import AgentModel, BorrowerModel, CallModel, ReservationModel
from app.dialer.predictive import PredictiveDialer
from app.dialer.progressive import PlacedCall, ProgressiveDialer
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallEvent, CallState
from app.events.processor import ProviderEventProcessor
from app.pacing.engine import PredictivePacingEngine
from app.provider.base import TelecomProvider
from app.recovery.service import ReservationRecovery, release_wrap_up
from app.safety.controller import DialerSnapshot, SafetyController, SafetyDecision


class SmartDialer:
    """
    Campaign tick: snapshot → pacing request → Safety Controller → execute.
    """

    def __init__(
        self,
        session: Session,
        provider: TelecomProvider,
        pacing: PredictivePacingEngine | None = None,
        safety: SafetyController | None = None,
    ):
        self.session = session
        self.provider = provider
        self.pacing = pacing or PredictivePacingEngine(
            answer_rate=0.5,
            avg_talk_seconds=90,
        )
        self.safety = safety or SafetyController()
        self.progressive = ProgressiveDialer(session, provider)
        self.predictive = PredictiveDialer(session, provider)
        self.allocator = AgentReservationService(session)
        self.processor = ProviderEventProcessor(session)
        self.recovery = ReservationRecovery(session)

    def snapshot(self) -> DialerSnapshot:
        available = self._count_agents(AgentState.AVAILABLE)
        eligible = self._count_borrowers(BorrowerState.ELIGIBLE)
        in_flight = self._count_calls(
            (CallState.INITIATED, CallState.RINGING)
        )
        connected = self._count_agents(AgentState.CONNECTED)
        answered = self._count_calls((CallState.ANSWERED,))
        reserved_call_ids = set(
            self.session.execute(
                select(ReservationModel.call_id)
            ).scalars().all()
        )
        unmatched = 0

        if answered:
            answered_rows = self.session.execute(
                select(CallModel.id).where(
                    CallModel.state == CallState.ANSWERED
                )
            ).scalars().all()
            unmatched = len(
                [call_id for call_id in answered_rows if call_id not in reserved_call_ids]
            )

        return DialerSnapshot(
            available_agents=available,
            eligible_borrowers=eligible,
            in_flight=in_flight,
            connected=connected,
            answered_unmatched=unmatched,
            provider_healthy=True,
        )

    def tick(
        self,
        worker_id: str,
        mode: str = "progressive",
        provider_healthy: bool = True,
    ) -> tuple[list[PlacedCall], SafetyDecision]:
        self.recovery.recover_expired()
        release_wrap_up(self.session)
        self._bind_or_abandon_answered(worker_id)

        snap = self.snapshot()
        snap = DialerSnapshot(
            available_agents=snap.available_agents,
            eligible_borrowers=snap.eligible_borrowers,
            in_flight=snap.in_flight,
            connected=snap.connected,
            answered_unmatched=snap.answered_unmatched,
            provider_healthy=provider_healthy,
        )

        if mode == "progressive":
            requested = min(snap.available_agents, snap.eligible_borrowers)
        else:
            requested = self.pacing.recommend(snap)

        decision = self.safety.authorize(requested, snap, mode)

        if decision.allowed <= 0:
            return [], decision

        if mode == "progressive" or decision.fallback_progressive:
            placed = self.progressive.dial(worker_id, limit=decision.allowed)
            return placed, decision

        matched = self.progressive.dial(
            worker_id,
            limit=min(decision.allowed, snap.available_agents),
        )
        remaining = decision.allowed - len(matched)
        unmatched = self.predictive.originate_unmatched(worker_id, remaining)
        return matched + unmatched, decision

    def _bind_or_abandon_answered(self, worker_id: str) -> None:
        answered = self.session.execute(
            select(CallModel).where(CallModel.state == CallState.ANSWERED)
        ).scalars().all()
        reserved = set(
            self.session.execute(select(ReservationModel.call_id)).scalars().all()
        )

        for call in answered:
            if call.id in reserved:
                continue

            agent_id = self.session.execute(
                select(AgentModel.id)
                .where(AgentModel.state == AgentState.AVAILABLE)
                .order_by(AgentModel.id)
                .limit(1)
            ).scalar_one_or_none()

            if agent_id is None:
                self.processor.handle(call.id, CallEvent.FAIL)
                continue

            try:
                self.allocator.bind_agent_to_answered_call(
                    agent_id=agent_id,
                    call_id=call.id,
                    worker_id=worker_id,
                )
            except AgentNotAvailable:
                self.processor.handle(call.id, CallEvent.FAIL)

    def _count_agents(self, state: AgentState) -> int:
        return self.session.execute(
            select(func.count()).select_from(AgentModel).where(
                AgentModel.state == state
            )
        ).scalar_one()

    def _count_borrowers(self, state: BorrowerState) -> int:
        return self.session.execute(
            select(func.count()).select_from(BorrowerModel).where(
                BorrowerModel.state == state
            )
        ).scalar_one()

    def _count_calls(self, states: tuple[CallState, ...]) -> int:
        return self.session.execute(
            select(func.count()).select_from(CallModel).where(
                CallModel.state.in_(states)
            )
        ).scalar_one()
