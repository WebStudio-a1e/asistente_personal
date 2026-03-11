"""Accounting agent node — extrae payload de movimiento y propone hacia confirmation_node.

Paso B del flujo para dominio 'accounting':
  orchestrator → accounting_agent → confirmation_node → persist_node

El agente:
- Clasifica la operación: create | update | read.
- Borrado NO existe — prohibido por política (DataHandling.md §6).
- Edición requiere correction_note obligatoria.
- Extrae datos estructurados del mensaje en español.
- Propone el payload hacia confirmation_node.
- Nunca persiste directamente.
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

_MVD_TZ = timezone(timedelta(hours=-3))

_SYSTEM_PROMPT = """\
Eres el agente de contabilidad de un asistente personal en español.
Timezone del sistema: America/Montevideo (UTC-3).

Tu tarea es extraer información estructurada para una operación sobre movimientos contables.

Operaciones posibles:
- create: registrar un nuevo movimiento (ingreso o egreso)
- update: corregir un movimiento existente (correction_note obligatoria)
- read:   consultar movimientos

IMPORTANTE: No existe operación 'delete'. El borrado de movimientos contables está PROHIBIDO.
Si el usuario pide borrar, responde con operation='read' y aclara en agent_response que no es posible.

Tipos válidos: income | expense

Responde SOLO con JSON válido, sin texto adicional:
{
  "operation":       "<create|update|read>",
  "entry_id":        "<id del movimiento si el usuario lo menciona, null si es nuevo>",
  "type":            "<income|expense, null si no aplica>",
  "category":        "<categoría del movimiento, null si no aplica>",
  "amount":          <monto numérico positivo, null si no aplica>,
  "note":            "<descripción del movimiento, null si no hay>",
  "balance":         <balance acumulado numérico, null si no se menciona>,
  "correction_note": "<razón de la corrección (obligatoria en update), null en create/read>",
  "agent_response":  "<resumen breve en español de lo que vas a hacer>"
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
        logger.warning("accounting_agent: parse error — %s", exc)
        return {}


def accounting_agent_node(state: AgentState) -> dict:
    """Extrae payload de movimiento del mensaje y prepara propuesta para confirmation_node.

    Actualiza en AgentState: payload, confirmation_status, agent_response.
    """
    message = state.get("message", "")
    llm = get_llm("accounting")
    response = llm.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", message),
    ])
    data = _parse_llm_response(response.content)

    operation = data.get("operation") or "create"
    # Guardar: el agente nunca permite delete
    if operation == "delete":
        logger.warning("accounting_agent: operación 'delete' rechazada — no permitida")
        operation = "read"

    now = datetime.now(tz=_MVD_TZ).isoformat()

    payload: dict[str, Any] = {
        "operation":       operation,
        "entry_id":        data.get("entry_id") or str(uuid.uuid4()),
        "type":            data.get("type") or "expense",
        "category":        data.get("category"),
        "amount":          data.get("amount"),
        "note":            data.get("note"),
        "balance":         data.get("balance"),
        "correction_note": data.get("correction_note"),
        "date":            now,
        "source":          "whatsapp",
    }

    return {
        "payload":             payload,
        "confirmation_status": ConfirmationStatus.DETECTED,
        "agent_response":      data.get("agent_response"),
    }
