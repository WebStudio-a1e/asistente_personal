"""Agenda agent node — extrae payload de evento y propone hacia confirmation_node.

Paso B del flujo para dominio 'agenda':
  orchestrator → agenda_agent → confirmation_node → persist_node

El agente:
- Clasifica la operación: create | update | cancel | read.
- Extrae datos estructurados del mensaje en español.
- Propone el payload hacia confirmation_node.
- Nunca persiste directamente.
- Timezone: America/Montevideo (UTC-3 permanente).
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from src.domain.confirmation import ConfirmationStatus
from src.graph.llm_factory import get_llm
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

_TIMEZONE = "America/Montevideo"
_MVD_TZ = timezone(timedelta(hours=-3))

_SYSTEM_PROMPT = """\
Eres el agente de agenda de un asistente personal en español.
Timezone del sistema: America/Montevideo (UTC-3).

Tu tarea es extraer información estructurada para una operación sobre eventos o recordatorios.

Operaciones posibles:
- create: crear un nuevo evento o recordatorio
- update: modificar un evento existente
- cancel: cancelar un evento (nunca se borra, solo se marca cancelado)
- read:   consultar o listar eventos

Responde SOLO con JSON válido, sin texto adicional:
{
  "operation":        "<create|update|cancel|read>",
  "event_id":         "<id del evento si el usuario lo menciona, null si es nuevo>",
  "title":            "<título del evento, null si no aplica>",
  "scheduled_for":    "<datetime ISO 8601 con offset -03:00, null si no aplica>",
  "duration_minutes": <duración en minutos entero, 60 por defecto, null si no aplica>,
  "recurrence":       "<RRULE string (ej. FREQ=WEEKLY;BYDAY=MO), null si no aplica>",
  "notes":            "<notas adicionales, null si no hay>",
  "agent_response":   "<resumen breve en español de lo que vas a hacer>"
}
"""


def _parse_llm_response(content: str) -> dict[str, Any]:
    """Parsea JSON de respuesta del LLM. Retorna dict vacío en caso de error."""
    try:
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            inner = lines[1:] if len(lines) > 1 else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            text = "\n".join(inner)
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, AttributeError) as exc:
        logger.warning("agenda_agent: parse error — %s", exc)
        return {}


def agenda_agent_node(state: AgentState) -> dict:
    """Extrae payload de evento del mensaje y prepara propuesta para confirmation_node.

    Actualiza en AgentState: payload, confirmation_status, agent_response.
    """
    message = state.get("message", "")
    llm = get_llm("agenda")
    response = llm.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", message),
    ])
    data = _parse_llm_response(response.content)

    operation = data.get("operation") or "create"
    now = datetime.now(tz=_MVD_TZ).isoformat()

    payload: dict[str, Any] = {
        "operation":        operation,
        "event_id":         data.get("event_id") or str(uuid.uuid4()),
        "title":            data.get("title"),
        "scheduled_for":    data.get("scheduled_for"),
        "duration_minutes": data.get("duration_minutes") or 60,
        "recurrence":       data.get("recurrence"),
        "notes":            data.get("notes"),
        "status":           "active",
        "source":           "whatsapp",
        "created_at":       now,
        "updated_at":       now,
        "timezone":         _TIMEZONE,
    }

    return {
        "payload":             payload,
        "confirmation_status": ConfirmationStatus.DETECTED,
        "agent_response":      data.get("agent_response"),
    }
