from sqlalchemy import select

from app.db.model import AgentModel
from app.domain.agent import AgentState


def test_create_and_read_agent(db_session):

    agent = AgentModel(
        id=1000,
        state=AgentState.AVAILABLE,
    )

    db_session.add(agent)
    db_session.flush()

    result = db_session.execute(
        select(AgentModel).where(AgentModel.id == 1000)
    )

    saved_agent = result.scalar_one()

    assert saved_agent.id == 1000
    assert saved_agent.state == AgentState.AVAILABLE