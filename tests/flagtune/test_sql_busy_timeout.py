"""Validate the sqlite busy-timeout configuration of the tuning-cache backend."""

import sqlalchemy

from flag_gems.utils.models import sql as sql_module
from flag_gems.utils.models.sql import SQLITE_BUSY_TIMEOUT, SQLPersistantModel


def _effective_busy_timeout_ms(engine: sqlalchemy.engine.Engine) -> int:
    """Read the busy timeout sqlite actually applies to this engine."""
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout")
            return cursor.fetchone()[0]
        finally:
            cursor.close()
    finally:
        raw.close()


def test_sqlite_engine_gets_the_configured_busy_timeout(tmp_path):
    """The timeout must reach sqlite, not just sit in a constant.

    Without connect_args the engine runs at sqlite3's 5s default, which
    concurrent ranks writing a newly tuned config can exceed.
    """
    model = SQLPersistantModel(f"sqlite:///{tmp_path / 'tune.db'}")
    try:
        assert _effective_busy_timeout_ms(model.engine) == SQLITE_BUSY_TIMEOUT * 1000
    finally:
        model.engine.dispose()


def test_busy_timeout_exceeds_sqlite_default():
    """A value at or below sqlite3's own 5s default would not fix anything."""
    assert SQLITE_BUSY_TIMEOUT > 5


def test_non_sqlite_url_gets_no_connect_args(monkeypatch):
    """Only sqlite takes a `timeout` connect arg; other drivers would reject it."""
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return "engine-sentinel"

    monkeypatch.setattr(sql_module.sqlalchemy, "create_engine", fake_create_engine)
    SQLPersistantModel("postgresql://user@host/db")

    assert captured["kwargs"] == {}
