from sqlalchemy import text


def test_database_connection(test_engine):
    with test_engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

        assert result.scalar() == 1


def test_suite_uses_test_database(test_engine):
    with test_engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar()

    assert database_name == "smart_dialer_test"
