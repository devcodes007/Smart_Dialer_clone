from concurrent.futures import ThreadPoolExecutor
import time

from app.db.model import AgentModel, BorrowerModel, ReservationModel
from app.dialer.progressive import ProgressiveDialer
from app.domain.agent import AgentState
from app.domain.borrower import BorrowerState
from app.provider.provider_a import MockProviderA
from sqlalchemy import select


def test_load_fifty_agents_ten_workers(db_reset, session_factory):

    agent_count = 50
    borrower_count = 50

    with session_factory() as session:
        for agent_id in range(1, agent_count + 1):
            session.add(AgentModel(id=agent_id, state=AgentState.AVAILABLE))
        for borrower_id in range(1, borrower_count + 1):
            session.add(
                BorrowerModel(
                    id=borrower_id,
                    phone_number=f"555{borrower_id:07d}",
                    state=BorrowerState.ELIGIBLE,
                )
            )
        session.commit()

    def worker(worker_number: int):
        with session_factory() as session:
            placed = ProgressiveDialer(
                session,
                MockProviderA(failure_rate=0.0),
            ).dial(worker_id=f"load-{worker_number}")
            session.commit()
            return len(placed)

    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=10) as executor:
        counts = list(executor.map(worker, range(1, 11)))

    elapsed = time.perf_counter() - started

    with session_factory() as session:
        reservations = session.execute(select(ReservationModel)).scalars().all()
        reserved_agents = session.execute(
            select(AgentModel).where(
                AgentModel.state.in_(
                    (AgentState.RESERVED, AgentState.DIALING, AgentState.CONNECTED)
                )
            )
        ).scalars().all()

        assert len(reservations) == 50
        assert len(reserved_agents) == 50
        assert sum(counts) == 50
        assert elapsed < 10
