"""Reporting agent node — consultas de solo lectura sobre todos los dominios.

Flujo:
  orchestrator → reporting_agent → END

El agente:
- Lee datos de los 4 dominios (tasks, ideas, agenda, accounting).
- Solo tiene herramientas de lectura — nunca escribe ni modifica.
- No pasa por confirmation_node.
- Genera respuestas en español a consultas complejas o cruzadas.
"""

import json
import logging
from typing import Any

from src.graph.llm_factory import get_llm
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

# ── Prompt del sistema ─────────────────────────────────────────

_SYSTEM_PROMPT = """\
Eres el agente de reporting de un asistente personal en español.

Tu tarea es responder consultas usando únicamente los datos proporcionados en el contexto.

Reglas:
1. Solo lees y analizas datos. NUNCA modificas, creas ni borras información.
2. Responde en español, de forma clara y concisa.
3. Si los datos no son suficientes para responder, indicalo explícitamente.
4. Para consultas de gastos: agrupa por categoría o período según se pida.
5. Para "qué tengo hoy": muestra agenda del día y tareas activas (pending, in_progress, today).
6. Para productividad: compara tareas completadas vs pendientes.
7. Para resumen contable: muestra totales de ingresos/egresos y balance.
"""


# ── Fetchers (patcheables en tests) ───────────────────────────

def _fetch_tasks() -> list[dict]:
    """Lee tareas desde Google Sheets. Retorna [] si el conector no está disponible."""
    try:
        from src.config import load_config
        from src.connectors.google_auth import get_sheets_client
        from src.connectors.sheets_tasks import read_tasks

        cfg = load_config()
        client = get_sheets_client()
        return read_tasks(client, cfg.google_sheet_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reporting_agent: no se pudo leer tareas — %s", exc)
        return []


def _fetch_ideas() -> list[dict]:
    """Lee ideas desde Google Docs. Retorna [] si el conector no está disponible."""
    try:
        from src.config import load_config
        from src.connectors.google_auth import get_docs_service
        from src.connectors.docs_ideas import read_ideas

        cfg = load_config()
        service = get_docs_service()
        return read_ideas(service, cfg.google_doc_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reporting_agent: no se pudo leer ideas — %s", exc)
        return []


def _fetch_events() -> list[dict]:
    """Lee eventos desde Google Calendar. Retorna [] si el conector no está disponible."""
    try:
        from src.config import load_config
        from src.connectors.google_auth import get_calendar_service
        from src.connectors.calendar_client import read_events

        cfg = load_config()
        service = get_calendar_service()
        return read_events(service, cfg.google_calendar_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reporting_agent: no se pudo leer eventos — %s", exc)
        return []


def _fetch_accounting() -> list[dict]:
    """Lee movimientos desde Google Sheets. Retorna [] si el conector no está disponible."""
    try:
        from src.config import load_config
        from src.connectors.google_auth import get_sheets_client
        from src.connectors.sheets_accounting import read_entries

        cfg = load_config()
        client = get_sheets_client()
        return read_entries(client, cfg.google_sheet_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("reporting_agent: no se pudo leer contabilidad — %s", exc)
        return []


# ── Construcción de contexto ───────────────────────────────────

def _build_context(
    tasks: list[dict],
    ideas: list[dict],
    events: list[dict],
    accounting: list[dict],
) -> str:
    """Serializa los datos de los 4 dominios en un contexto legible para el LLM."""
    sections: list[str] = []

    if tasks:
        sections.append(
            "TAREAS:\n" + json.dumps(tasks, ensure_ascii=False, indent=2)
        )
    if ideas:
        sections.append(
            "IDEAS:\n" + json.dumps(ideas, ensure_ascii=False, indent=2)
        )
    if events:
        sections.append(
            "AGENDA:\n" + json.dumps(events, ensure_ascii=False, indent=2)
        )
    if accounting:
        sections.append(
            "CONTABILIDAD:\n" + json.dumps(accounting, ensure_ascii=False, indent=2)
        )

    return "\n\n".join(sections) if sections else "No hay datos disponibles."


# ── Nodo ──────────────────────────────────────────────────────

def reporting_agent_node(state: AgentState) -> dict[str, Any]:
    """Genera respuesta a consulta de reporting leyendo los 4 dominios.

    No llama a confirmation_node — responde directamente al usuario.
    No modifica ninguna fuente de verdad.

    Actualiza en AgentState: agent_response.
    """
    message = state.get("message", "")

    tasks = _fetch_tasks()
    ideas = _fetch_ideas()
    events = _fetch_events()
    accounting = _fetch_accounting()

    context = _build_context(tasks, ideas, events, accounting)

    llm = get_llm("reporting")
    response = llm.invoke([
        ("system", _SYSTEM_PROMPT),
        ("human", f"Contexto actual:\n{context}\n\nConsulta: {message}"),
    ])

    return {"agent_response": response.content}
