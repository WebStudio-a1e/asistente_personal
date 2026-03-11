"""Orchestrator node — clasifica intención y dominio, rutea al agente correcto.

Paso A del flujo de clasificación:
  mensaje → orchestrator → agente especializado → confirmation_node → persist_node

El orquestador:
- Clasifica intent y domain a partir del mensaje en español.
- Pide aclaración si la intención es ambigua, incompleta o fuera de dominio.
- Descompone mensajes multi-intención en pending_actions.
- Nunca persiste datos directamente.
"""

import json
import logging
from typing import Any

from src.domain.intents import Domain, Intent
from src.graph.llm_factory import get_llm
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

# ── Mapa intent → domain ──────────────────────────────────────

_INTENT_TO_DOMAIN: dict[str, str] = {
    Intent.TASK:       Domain.TASKS,
    Intent.IDEA:       Domain.IDEAS,
    Intent.AGENDA:     Domain.AGENDA,
    Intent.ACCOUNTING: Domain.ACCOUNTING,
    Intent.QUERY:      Domain.REPORTING,
    Intent.UNKNOWN:    Domain.UNKNOWN,
}

# ── Prompt del sistema ────────────────────────────────────────

_SYSTEM_PROMPT = """\
Eres el orquestador de un asistente personal en español.

Tu tarea es clasificar el mensaje del usuario en una de estas intenciones:
- task: crear, editar, mover, borrar o consultar tareas (kanban)
- idea: crear, editar, borrar o consultar ideas/notas
- agenda: crear, editar, cancelar o consultar eventos/recordatorios
- accounting: registrar o consultar ingresos/egresos
- query: consulta compleja que cruza múltiples dominios
- unknown: intención ambigua, payload incompleto, fuera de dominio o no reconocida

Dominios válidos: tasks | ideas | agenda | accounting | reporting | unknown

Reglas:
1. Si la intención es clara y única, responde con intent y domain sin agent_response.
2. Si el mensaje contiene múltiples acciones persistentes distintas, descompone en \
pending_actions con todas las acciones.
3. Si la intención es ambigua, incompleta o fuera de dominio, usa intent=unknown y \
escribe un agent_response pidiendo aclaración en español, de forma breve y amable.
4. Nunca inventes datos que el usuario no proporcionó.
5. Responde SOLO con JSON válido, sin texto adicional.

Formato para intención única clara:
{
  "intent": "<intent>",
  "domain": "<domain>",
  "agent_response": null,
  "pending_actions": []
}

Formato para intención ambigua (pide aclaración):
{
  "intent": "unknown",
  "domain": "unknown",
  "agent_response": "<pregunta breve en español>",
  "pending_actions": []
}

Formato para multi-intención:
{
  "intent": "<intent de la primera acción>",
  "domain": "<domain de la primera acción>",
  "agent_response": null,
  "pending_actions": [
    {"intent": "<intent1>", "domain": "<domain1>", "message": "<acción 1>"},
    {"intent": "<intent2>", "domain": "<domain2>", "message": "<acción 2>"}
  ]
}
"""


# ── Parser ────────────────────────────────────────────────────

def _parse_llm_response(content: str) -> dict[str, Any]:
    """Parsea la respuesta JSON del LLM. Fallback a unknown ante cualquier error."""
    try:
        text = content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first line (```json or ```) and last line (```)
            inner = lines[1:] if len(lines) > 1 else lines
            if inner and inner[-1].strip() == "```":
                inner = inner[:-1]
            text = "\n".join(inner)

        data = json.loads(text)

        intent = data.get("intent") or Intent.UNKNOWN
        domain = data.get("domain") or _INTENT_TO_DOMAIN.get(intent, Domain.UNKNOWN)

        return {
            "intent":          intent,
            "domain":          domain,
            "agent_response":  data.get("agent_response") or None,
            "pending_actions": data.get("pending_actions") or [],
        }

    except (json.JSONDecodeError, KeyError, TypeError, AttributeError) as exc:
        logger.warning("orchestrator: parse error — %s", exc)
        return {
            "intent":          Intent.UNKNOWN,
            "domain":          Domain.UNKNOWN,
            "agent_response":  "No pude entender tu mensaje. ¿Podés reformularlo?",
            "pending_actions": [],
        }


# ── Nodo ─────────────────────────────────────────────────────

def orchestrator_node(state: AgentState) -> dict:
    """Clasifica intención y dominio del mensaje entrante.

    Actualiza en AgentState: intent, domain, agent_response, pending_actions.
    """
    message = state.get("message", "")
    llm = get_llm("orchestrator")
    response = llm.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", message),
    ])
    return _parse_llm_response(response.content)
