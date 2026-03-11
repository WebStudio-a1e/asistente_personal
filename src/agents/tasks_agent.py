"""Tasks agent node — extrae payload de tarea y propone hacia confirmation_node.

Paso B del flujo para dominio 'tasks':
  orchestrator → tasks_agent → confirmation_node → persist_node

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
Eres el agente de tareas de un asistente personal en español.

Tu tarea es extraer información estructurada para una operación sobre tareas kanban.

Operaciones posibles:
- create: crear una nueva tarea
- update: cambiar el estado o los datos de una tarea existente
- delete: borrar una tarea
- read:   consultar o listar tareas

Estados válidos: pending | in_progress | today | completed

Responde SOLO con JSON válido, sin texto adicional:
{
  "operation": "<create|update|delete|read>",
  "task_id":   "<id de la tarea si el usuario lo menciona, null si es nueva>",
  "title":     "<título de la tarea, null si no aplica>",
  "status":    "<estado canónico, null si no aplica>",
  "notes":     "<notas adicionales, null si no hay>",
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
        logger.warning("tasks_agent: parse error — %s", exc)
        return {}


def tasks_agent_node(state: AgentState) -> dict:
    """Extrae payload de tarea del mensaje y prepara propuesta para confirmation_node.

    Actualiza en AgentState: payload, confirmation_status, agent_response.
    """
    message = state.get("message", "")
    llm = get_llm("tasks")
    response = llm.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", message),
    ])
    data = _parse_llm_response(response.content)

    operation = data.get("operation") or "create"
    now = datetime.now(tz=timezone.utc).isoformat()

    payload: dict[str, Any] = {
        "operation":  operation,
        "task_id":    data.get("task_id") or str(uuid.uuid4()),
        "title":      data.get("title"),
        "status":     data.get("status") or "pending",
        "notes":      data.get("notes"),
        "source":     "whatsapp",
        "created_at": now,
        "updated_at": now,
    }

    return {
        "payload":             payload,
        "confirmation_status": ConfirmationStatus.DETECTED,
        "agent_response":      data.get("agent_response"),
    }
