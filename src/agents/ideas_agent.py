"""Ideas agent node — extrae payload de idea y propone hacia confirmation_node.

Paso B del flujo para dominio 'ideas':
  orchestrator → ideas_agent → confirmation_node → persist_node

El agente:
- Clasifica la operación: create | update | delete | read.
- Extrae datos estructurados del mensaje en español.
- Propone el payload hacia confirmation_node.
- Nunca persiste directamente.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.domain.confirmation import ConfirmationStatus
from src.graph.llm_factory import get_llm
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
Eres el agente de ideas/notas de un asistente personal en español.

Tu tarea es extraer información estructurada para una operación sobre ideas o notas.

Operaciones posibles:
- create: registrar una nueva idea o nota
- update: modificar una idea existente
- delete: borrar una idea
- read:   consultar o listar ideas

Prioridades válidas: low | medium | high
Estados válidos: active | archived

Responde SOLO con JSON válido, sin texto adicional:
{
  "operation":      "<create|update|delete|read>",
  "idea_id":        "<id de la idea si el usuario lo menciona, null si es nueva>",
  "theme":          "<tema o categoría de la idea, null si no aplica>",
  "summary":        "<resumen breve de la idea, null si no aplica>",
  "priority":       "<low|medium|high, null si no aplica>",
  "tags":           ["<tag1>", "<tag2>"],
  "status":         "<active|archived, null si no aplica>",
  "raw_text":       "<texto completo tal como lo expresó el usuario, null si no aplica>",
  "agent_response": "<resumen breve en español de lo que vas a hacer>"
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
        logger.warning("ideas_agent: parse error — %s", exc)
        return {}


def ideas_agent_node(state: AgentState) -> dict:
    """Extrae payload de idea del mensaje y prepara propuesta para confirmation_node.

    Actualiza en AgentState: payload, confirmation_status, agent_response.
    """
    message = state.get("message", "")
    llm = get_llm("ideas")
    response = llm.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", message),
    ])
    data = _parse_llm_response(response.content)

    operation = data.get("operation") or "create"
    now = datetime.now(tz=timezone.utc).isoformat()

    payload: dict[str, Any] = {
        "operation":  operation,
        "idea_id":    data.get("idea_id") or str(uuid.uuid4()),
        "theme":      data.get("theme"),
        "summary":    data.get("summary"),
        "priority":   data.get("priority") or "medium",
        "tags":       data.get("tags") or [],
        "status":     data.get("status") or "active",
        "raw_text":   data.get("raw_text"),
        "source":     "whatsapp",
        "created_at": now,
        "updated_at": now,
    }

    return {
        "payload":             payload,
        "confirmation_status": ConfirmationStatus.DETECTED,
        "agent_response":      data.get("agent_response"),
    }
