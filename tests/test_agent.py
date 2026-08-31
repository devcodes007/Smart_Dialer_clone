import pytest

from app.domain.agent import Agent, AgentState, AgentEvent


def test_agent_login():

    agent = Agent(id=1)

    assert agent.state == AgentState.OFFLINE

    agent.transition(AgentEvent.LOGIN)

    assert agent.state == AgentState.AVAILABLE


def test_agent_reservation():

    agent = Agent(id=1)

    agent.transition(AgentEvent.LOGIN)
    agent.transition(AgentEvent.RESERVE)

    assert agent.state == AgentState.RESERVED


def test_agent_can_start_dialing():

    agent = Agent(id=1)

    agent.transition(AgentEvent.LOGIN)
    agent.transition(AgentEvent.RESERVE)
    agent.transition(AgentEvent.CALL_INITIATED)

    assert agent.state == AgentState.DIALING


def test_agent_can_connect():

    agent = Agent(id=1)

    agent.transition(AgentEvent.LOGIN)
    agent.transition(AgentEvent.RESERVE)
    agent.transition(AgentEvent.CALL_INITIATED)
    agent.transition(AgentEvent.CALL_ANSWERED)

    assert agent.state == AgentState.CONNECTED


def test_agent_returns_to_available_after_wrap_up():

    agent = Agent(id=1)

    agent.transition(AgentEvent.LOGIN)
    agent.transition(AgentEvent.RESERVE)
    agent.transition(AgentEvent.CALL_INITIATED)
    agent.transition(AgentEvent.CALL_ANSWERED)
    agent.transition(AgentEvent.CALL_ENDED)
    agent.transition(AgentEvent.WRAP_UP_COMPLETE)

    assert agent.state == AgentState.AVAILABLE


def test_invalid_transition_is_rejected():

    agent = Agent(id=1)

    with pytest.raises(ValueError):

        agent.transition(AgentEvent.CALL_ANSWERED)