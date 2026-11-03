import os

# Tests get their own database so they never wipe collected history.
ADMIN_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://trend_radar:trend_radar@localhost:5432/trend_radar")
os.environ["DATABASE_URL"] = ADMIN_URL.rsplit("/", 1)[0] + "/trend_radar_test"

import pytest  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

with create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT").connect() as c:
    if not c.scalar(text("select 1 from pg_database where datname = 'trend_radar_test'")):
        c.execute(text("create database trend_radar_test"))

from trend_radar.connectors import youtube  # noqa: E402
from trend_radar.db import Base, engine  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(monkeypatch):
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(youtube._call.retry, "sleep", lambda _: None)  # no real backoff waits in tests
