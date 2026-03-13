"""Punto de entrada de la aplicación — FastAPI base."""

import hashlib
import logging
import os
import sqlite3
import urllib.parse
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from src.connectors.twilio_client import get_twilio_client, send_whatsapp_message
from src.graph.graph import build_graph
from src.scheduler.jobs import start_scheduler, stop_scheduler
from src.storage.sqlite import create_tables, get_connection

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestiona el ciclo de vida de la app: inicia y detiene el scheduler."""
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="asistente_personal", version="0.1.0", lifespan=lifespan)


# ── Dependencias ──────────────────────────────────────────────


def _get_db() -> sqlite3.Connection:
    """Dependency: abre conexión SQLite desde SQLITE_DB_PATH."""
    db_path = os.getenv("SQLITE_DB_PATH", "data/asistente_personal.db")
    conn = get_connection(db_path)
    create_tables(conn)
    return conn


def _get_graph():
    """Dependency: construye el grafo LangGraph con SqliteSaver."""
    db_path = os.getenv("SQLITE_DB_PATH", "data/asistente_personal.db")
    return build_graph(db_path=db_path)


def _get_twilio():
    """Dependency: retorna cliente Twilio o None si no está configurado."""
    try:
        return get_twilio_client()
    except ValueError:
        return None


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
    graph=Depends(_get_graph),
    twilio_client=Depends(_get_twilio),
):
    """Recibe mensajes entrantes de Twilio (WhatsApp).

    Flujo:
      1. Parsea form body (MessageSid, From, DateCreated, Body).
      2. Genera clave de idempotencia.
      3. Consulta processed_events — si existe, responde 200 sin procesar.
      4. Registra la clave.
      5. Invoca el grafo con thread_id = From.
      6. Envía agent_response por Twilio si existe.
    """
    raw = await request.body()
    form = _parse_form(raw)

    message_sid = form.get("MessageSid", "")
    from_number = form.get("From", "")
    timestamp = form.get("DateCreated", "")
    body = form.get("Body", "")

    logger.info(
        "webhook: mensaje entrante — sid=%s from=%s body=%.120r",
        message_sid, from_number, body,
    )

    idem_key = _idempotency_key(message_sid, from_number, timestamp, body)
    logger.info("webhook: idempotency_key=%s", idem_key)

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

    # Invocar el grafo — thread_id = From (número de WhatsApp del remitente)
    logger.info("webhook: invocando grafo — thread_id=%s", from_number)
    try:
        result = graph.invoke(
            {
                "message": body,
                "idempotency_key": idem_key,
                "pending_actions": [],
                "conversation_history": [],
            },
            config={"configurable": {"thread_id": from_number}},
        )
        agent_response = result.get("agent_response")
        logger.info(
            "webhook: grafo finalizado — nodo_final=reporting_agent agent_response=%s",
            repr(agent_response[:120]) if agent_response else "<vacío>",
        )
    except Exception as exc:
        logger.exception("webhook: error en graph.invoke — %s", exc)
        agent_response = "Error interno. Por favor intentá de nuevo."

    if agent_response and twilio_client:
        logger.info(
            "webhook: enviando respuesta Twilio — to=%s from=%s",
            from_number, form.get("To", ""),
        )
        try:
            send_whatsapp_message(
                twilio_client,
                body=agent_response,
                to=from_number,
                from_=form.get("To", ""),
            )
        except Exception as exc:
            logger.exception("webhook: error al enviar Twilio — %s", exc)
    elif not agent_response:
        logger.warning("webhook: agent_response vacío — no se envía mensaje")
    elif not twilio_client:
        logger.warning("webhook: twilio_client no disponible — no se envía mensaje")

    logger.info("webhook: mensaje procesado — from=%s key=%s", from_number, idem_key)
    return {"status": "ok"}
