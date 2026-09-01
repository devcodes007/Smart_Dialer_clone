from app.db.model import AgentModel, BorrowerModel, CallModel
from app.dialer.orchestrator import SmartDialer
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallEvent, CallState
from app.events.processor import ProviderEventProcessor
from app.pacing.engine import PredictivePacingEngine
from app.provider.provider_a import MockProviderA
from app.safety.controller import SafetyController


def seed(session, agent_count: int, borrower_count: int, id_offset: int = 0) -> None:
    for agent_id in range(id_offset + 1, id_offset + agent_count + 1):
        session.add(AgentModel(id=agent_id, state=AgentState.AVAILABLE))
    for n in range(1, borrower_count + 1):
        borrower_id = id_offset + 1000 + n
        session.add(
            BorrowerModel(
                id=borrower_id,
                phone_number=f"555{borrower_id:07d}",
                state=BorrowerState.ELIGIBLE,
            )
        )
    session.flush()


def run_scenario(
    session,
    name: str,
    answer_rate: float,
    talk_seconds: float,
    agent_count: int = 8,
    borrower_count: int = 30,
    id_offset: int = 0,
) -> dict:
    seed(session, agent_count, borrower_count, id_offset=id_offset)
    provider = MockProviderA(failure_rate=0.0)
    dialer = SmartDialer(
        session,
        provider,
        pacing=PredictivePacingEngine(
            answer_rate=answer_rate,
            avg_talk_seconds=talk_seconds,
        ),
        safety=SafetyController(max_overdial_ratio=0.5),
    )
    processor = ProviderEventProcessor(session)
    placed, decision = dialer.tick("sim-worker", mode="predictive")

    answers_wanted = int(round(len(placed) * answer_rate))
    answered = 0
    connected = 0

    for index, item in enumerate(placed):
        processor.handle(item.call_id, CallEvent.RINGING)
        if index < answers_wanted:
            processor.handle(item.call_id, CallEvent.ANSWERED)
            answered += 1
            call = session.get(CallModel, item.call_id)
            if call is not None and call.state == CallState.CONNECTED:
                connected += 1
                processor.handle(item.call_id, CallEvent.COMPLETED)
            elif call is not None and call.state == CallState.ANSWERED:
                processor.handle(item.call_id, CallEvent.FAIL)
        else:
            processor.handle(item.call_id, CallEvent.FAIL)

    return {
        "scenario": name,
        "answer_rate": answer_rate,
        "avg_talk_seconds": talk_seconds,
        "safety_allowed": decision.allowed,
        "safety_reason": decision.reason,
        "fallback_progressive": decision.fallback_progressive,
        "initiated": len(placed),
        "answered": answered,
        "connected": connected,
    }
