# SmartDialer

Prototype 2: Predictive SmartDialer with a deterministic Safety Controller, plus Progressive as the safe baseline.

## Setup

Python 3.11+, PostgreSQL.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create databases `smart_dialer` and `smart_dialer_test`.

`.env`:

```
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/smart_dialer
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@localhost:5432/smart_dialer_test
```

URL-encode special characters in the password.

```bash
python -m app.db.init_db
.venv\Scripts\python.exe -m pytest -v
```

## Run simulation

```bash
python -m app.simulation
```

Uses `TEST_DATABASE_URL` only (`smart_dialer_test`). It will not write to the development database.

## Architecture

See `docs/ARCHITECTURE.md` and `docs/ADR.md`.
