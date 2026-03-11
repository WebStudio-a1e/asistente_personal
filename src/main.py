"""Punto de entrada de la aplicación — FastAPI base."""

import hashlib
import logging
import os
import sqlite3
import urllib.parse

from fastapi import Depends, FastAPI, Request

from src.storage.sqlite import create_tables, get_connection

logger = logging.getLogger(__name__)

app = FastAPI(title="asistente_personal", version="0.1.0")


# ── Dependencia SQLite ────────────────────────────────────────


def _get_db() -> sqlite3.Connection:
    """Dependency: abre conexión SQLite desde SQLITE_DB_PATH."""
    db_path = os.getenv("SQLITE_DB_PATH", "data/asistente_personal.db")
    conn = get_connection(db_path)
    create_tables(conn)
    return conn


# ── Idempotencia ──────────────────────────────────────────────


def _idempotency_key(
    message_sid: str,
    from_number: str,
    timestamp: str,
    body: str,
) -> str:
    """Genera clave de idempotencia.

    Política (CLAUDE.md §12):
      1. Provider event id: MessageSid de Twilio si existe.
      2. Fallback: sha256(remitente + timestamp + body)[:32].
    """
    if message_sid:
        return message_sid
    raw = f"{from_number}{timestamp}{body}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _parse_form(raw: bytes) -> dict[str, str]:
    """Parsea cuerpo application/x-www-form-urlencoded sin dependencias externas."""
    parsed = urllib.parse.parse_qs(raw.decode("utf-8"), keep_blank_values=True)
    return {k: v[0] if v else "" for k, v in parsed.items()}


# ── Endpoints ─────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhook")
async def webhook(
    request: Request,
    conn: sqlite3.Connection = Depends(_get_db),
):
    """Recibe mensajes entrantes de Twilio (WhatsApp).

    Flujo:
      1. Parsea form body (MessageSid, From, DateCreated, Body).
      2. Genera clave de idempotencia.
      3. Consulta processed_events — si existe, responde 200 sin procesar.
      4. Registra la clave y procesa el mensaje.

    Invocación del grafo: T-029.
    """
    raw = await request.body()
    form = _parse_form(raw)

    message_sid = form.get("MessageSid", "")
    from_number = form.get("From", "")
    timestamp = form.get("DateCreated", "")
    body = form.get("Body", "")

    idem_key = _idempotency_key(message_sid, from_number, timestamp, body)

    # Dedupe: consultar processed_events
    existing = conn.execute(
        "SELECT id FROM processed_events WHERE idempotency_key = ?",
        (idem_key,),
    ).fetchone()

    if existing:
        logger.info("webhook: evento duplicado ignorado — key=%s", idem_key)
        return {"status": "duplicate"}

    # Registrar evento procesado
    with conn:
        conn.execute(
            "INSERT INTO processed_events (idempotency_key) VALUES (?)",
            (idem_key,),
        )

    # Invocación del grafo: T-029
    logger.info("webhook: mensaje recibido — from=%s key=%s", from_number, idem_key)
    return {"status": "ok"}
