from app.simulation.runner import run_scenario


def test_simulation_scenario_a(db_session):

    result = run_scenario(
        db_session,
        name="A",
        answer_rate=0.20,
        talk_seconds=120,
    )

    assert result["initiated"] >= 1
    assert result["safety_allowed"] >= 1
    assert result["connected"] >= 0
    assert result["answered"] <= result["initiated"]
