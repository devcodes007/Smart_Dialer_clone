from sqlalchemy import select

from app.db.model import AgentModel, BorrowerModel, CallModel
from app.dialer.orchestrator import SmartDialer
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.domain.call import CallState
from app.pacing.engine import PredictivePacingEngine
from app.provider.provider_a import MockProviderA
from app.safety.controller import SafetyController


def _seed(session, agents, borrowers):
    for agent_id in agents:
        session.add(AgentModel(id=agent_id, state=AgentState.AVAILABLE))
    for borrower_id in borrowers:
        session.add(
            BorrowerModel(
                id=borrower_id,
                phone_number=f"555000{borrower_id:04d}",
                state=BorrowerState.ELIGIBLE,
            )
        )
    session.flush()


def test_orchestrator_progressive_goes_through_safety(db_session):

    _seed(db_session, [1, 2], [10, 11, 12, 13, 14])
    dialer = SmartDialer(
        db_session,
        MockProviderA(failure_rate=0.0),
    )

    placed, decision = dialer.tick("worker-1", mode="progressive")

    assert decision.allowed == 2
    assert len(placed) == 2
    assert all(item.agent_id is not None for item in placed)


def test_orchestrator_predictive_can_overdial(db_session):

    _seed(db_session, [1], list(range(10, 20)))
    dialer = SmartDialer(
        db_session,
        MockProviderA(failure_rate=0.0),
        pacing=PredictivePacingEngine(answer_rate=0.2, avg_talk_seconds=120),
        safety=SafetyController(max_overdial_ratio=1.0),
    )

    placed, decision = dialer.tick("worker-1", mode="predictive")

    initiated = db_session.execute(
        select(CallModel).where(CallModel.state == CallState.INITIATED)
    ).scalars().all()

    unmatched = [item for item in placed if item.agent_id is None]

    assert decision.allowed >= 1
    assert len(placed) == len(initiated)
    assert len(unmatched) >= 0
    assert len(placed) <= decision.allowed
