"""Tests T-017 — Bootstrap SQLite.

Cubre:
- get_connection: crea archivo, directorios, modo WAL
- create_tables: 6 tablas, columnas clave, idempotencia, constraint UNIQUE
- run_bootstrap: tablas + SqliteSaver inicializable desde mismo path
"""

import os
import sqlite3

import pytest

from src.storage.sqlite import OPERATIONAL_TABLES, create_tables, get_connection


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


# ── get_connection ────────────────────────────────────────────────────────────


class TestGetConnection:
    def test_creates_db_file(self, tmp_db):
        conn = get_connection(tmp_db)
        conn.close()
        assert os.path.exists(tmp_db)

    def test_creates_parent_dirs(self, tmp_path):
        db_path = str(tmp_path / "nested" / "dir" / "test.db")
        conn = get_connection(db_path)
        conn.close()
        assert os.path.exists(db_path)

    def test_wal_mode(self, tmp_db):
        conn = get_connection(tmp_db)
        row = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        assert row[0] == "wal"

    def test_returns_connection(self, tmp_db):
        conn = get_connection(tmp_db)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()


# ── create_tables ─────────────────────────────────────────────────────────────


class TestCreateTables:
    def test_creates_all_six_tables(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        names = {r[0] for r in rows}
        for table in OPERATIONAL_TABLES:
            assert table in names, f"Tabla faltante: {table}"

    def test_idempotent(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        create_tables(conn)  # segunda ejecución no debe fallar
        conn.close()

    @pytest.mark.parametrize("table", OPERATIONAL_TABLES)
    def test_each_table_exists(self, tmp_db, table):
        conn = get_connection(tmp_db)
        create_tables(conn)
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        conn.close()
        assert row is not None

    def test_inbound_messages_columns(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(inbound_messages)").fetchall()}
        conn.close()
        assert {"id", "message_sid", "from_number", "body", "received_at", "created_at"} <= cols

    def test_confirmation_requests_columns(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(confirmation_requests)").fetchall()}
        conn.close()
        assert {"id", "thread_id", "idempotency_key", "status", "proposal_sent_at"} <= cols

    def test_audit_logs_columns(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_logs)").fetchall()}
        conn.close()
        assert {"id", "thread_id", "action", "domain", "payload", "status", "created_at"} <= cols

    def test_processed_events_unique_constraint(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        conn.execute(
            "INSERT INTO processed_events (idempotency_key) VALUES (?)",
            ("key-abc",),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO processed_events (idempotency_key) VALUES (?)",
                ("key-abc",),
            )
            conn.commit()
        conn.close()

    def test_confirmation_requests_unique_idempotency_key(self, tmp_db):
        conn = get_connection(tmp_db)
        create_tables(conn)
        conn.execute(
            "INSERT INTO confirmation_requests "
            "(thread_id, idempotency_key, proposal_json, proposal_sent_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            ("thread-1", "idem-key-1", "{}"),
        )
        conn.commit()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO confirmation_requests "
                "(thread_id, idempotency_key, proposal_json, proposal_sent_at) "
                "VALUES (?, ?, ?, datetime('now'))",
                ("thread-2", "idem-key-1", "{}"),
            )
            conn.commit()
        conn.close()


# ── Bootstrap ─────────────────────────────────────────────────────────────────


class TestBootstrap:
    def test_run_bootstrap_creates_tables(self, tmp_db):
        from src.storage.bootstrap import run_bootstrap

        run_bootstrap(db_path=tmp_db)
        conn = sqlite3.connect(tmp_db)
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        conn.close()
        names = {r[0] for r in rows}
        for table in OPERATIONAL_TABLES:
            assert table in names

    def test_run_bootstrap_idempotent(self, tmp_db):
        from src.storage.bootstrap import run_bootstrap

        run_bootstrap(db_path=tmp_db)
        run_bootstrap(db_path=tmp_db)  # segunda vez no debe fallar

    def test_sqlite_saver_initializable(self, tmp_db):
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = get_connection(tmp_db)
        create_tables(conn)
        conn.close()
        with SqliteSaver.from_conn_string(tmp_db) as saver:
            assert saver is not None

    def test_sqlite_saver_same_path_as_operational_tables(self, tmp_db):
        """SqliteSaver y tablas operativas conviven en el mismo archivo."""
        from langgraph.checkpoint.sqlite import SqliteSaver

        conn = get_connection(tmp_db)
        create_tables(conn)
        conn.close()

        with SqliteSaver.from_conn_string(tmp_db) as _saver:
            conn2 = sqlite3.connect(tmp_db)
            rows = conn2.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            conn2.close()
        names = {r[0] for r in rows}
        for table in OPERATIONAL_TABLES:
            assert table in names
