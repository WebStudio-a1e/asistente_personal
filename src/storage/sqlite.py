"""SQLite — conexión y DDL de las 6 tablas operativas.

Rol: soporte operativo (no fuente de verdad funcional).
Las tablas del checkpointer LangGraph (SqliteSaver) se crean aparte.
"""

import sqlite3
from pathlib import Path

OPERATIONAL_TABLES = [
    "inbound_messages",
    "conversation_state",
    "confirmation_requests",
    "processed_events",
    "reminder_jobs",
    "audit_logs",
]

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS inbound_messages (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        message_sid TEXT    NOT NULL,
        from_number TEXT    NOT NULL,
        body        TEXT    NOT NULL,
        received_at TEXT    NOT NULL,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_state (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id  TEXT    NOT NULL UNIQUE,
        state_json TEXT    NOT NULL,
        updated_at TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS confirmation_requests (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id        TEXT    NOT NULL,
        idempotency_key  TEXT    NOT NULL UNIQUE,
        proposal_json    TEXT    NOT NULL,
        status           TEXT    NOT NULL DEFAULT 'awaiting_confirmation',
        proposal_sent_at TEXT    NOT NULL,
        resolved_at      TEXT,
        created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS processed_events (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        idempotency_key TEXT    NOT NULL UNIQUE,
        processed_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reminder_jobs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id     TEXT    NOT NULL,
        event_id      TEXT    NOT NULL,
        scheduled_for TEXT    NOT NULL,
        status        TEXT    NOT NULL DEFAULT 'pending',
        fired_at      TEXT,
        created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        thread_id  TEXT    NOT NULL,
        action     TEXT    NOT NULL,
        domain     TEXT,
        payload    TEXT,
        status     TEXT    NOT NULL,
        created_at TEXT    NOT NULL DEFAULT (datetime('now'))
    )
    """,
]


def get_connection(db_path: str) -> sqlite3.Connection:
    """Abre (o crea) la base SQLite en db_path con WAL mode."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """Crea las 6 tablas operativas si no existen. Idempotente."""
    with conn:
        for ddl in _DDL:
            conn.execute(ddl)
