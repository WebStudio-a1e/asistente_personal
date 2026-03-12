"""Grafo LangGraph — StateGraph con SqliteSaver como checkpointer.

Nodos funcionales implementados:
  - reporting_agent_node (T-033)

Nodos aún placeholder (FASE_2+):
  - orchestrator_node, tasks_agent_node, ideas_agent_node,
    agenda_agent_node, accounting_agent_node, confirmation_node, persist_node

Checkpointer: SqliteSaver desde SQLITE_DB_PATH.
Entry point: orchestrator.
"""

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from src.agents.reporting_agent import reporting_agent_node
from src.config import load_config
from src.graph.state import AgentState
from src.storage.sqlite import create_tables, get_connection


# ── Nodos placeholder ─────────────────────────────────────────


def orchestrator_node(state: AgentState) -> dict:
    return {"agent_response": "Hola, soy tu asistente. Estoy en línea. (modo prueba)"}


def tasks_agent_node(state: AgentState) -> dict:
    return {}


def ideas_agent_node(state: AgentState) -> dict:
    return {}


def agenda_agent_node(state: AgentState) -> dict:
    return {}


def accounting_agent_node(state: AgentState) -> dict:
    return {}


def confirmation_node(state: AgentState) -> dict:
    return {}


def persist_node(state: AgentState) -> dict:
    return {}


# ── Routers ───────────────────────────────────────────────────


def _route_orchestrator(state: AgentState) -> str:
    domain = state.get("domain") or ""
    return {
        "tasks":      "tasks_agent",
        "ideas":      "ideas_agent",
        "agenda":     "agenda_agent",
        "accounting": "accounting_agent",
        "reporting":  "reporting_agent",
    }.get(domain, END)


def _route_confirmation(state: AgentState) -> str:
    status = state.get("confirmation_status") or ""
    if status == "confirmed":
        return "persist_node"
    if status == "rejected":
        return "orchestrator"
    return END


# ── Graph factory ─────────────────────────────────────────────


def build_graph(db_path: str | None = None):
    """Construye y compila el StateGraph con SqliteSaver como checkpointer.

    Args:
        db_path: ruta al archivo SQLite. Si es None usa SQLITE_DB_PATH de config.

    Returns:
        CompiledStateGraph listo para invocar.
    """
    if db_path is None:
        cfg = load_config()
        db_path = cfg.sqlite_db_path

    conn = get_connection(db_path)
    create_tables(conn)

    builder = StateGraph(AgentState)

    # Nodos
    builder.add_node("orchestrator",      orchestrator_node)
    builder.add_node("tasks_agent",       tasks_agent_node)
    builder.add_node("ideas_agent",       ideas_agent_node)
    builder.add_node("agenda_agent",      agenda_agent_node)
    builder.add_node("accounting_agent",  accounting_agent_node)
    builder.add_node("reporting_agent",   reporting_agent_node)
    builder.add_node("confirmation_node", confirmation_node)
    builder.add_node("persist_node",      persist_node)

    # Entry point
    builder.set_entry_point("orchestrator")

    # orchestrator → agente según domain
    builder.add_conditional_edges(
        "orchestrator",
        _route_orchestrator,
        {
            "tasks_agent":      "tasks_agent",
            "ideas_agent":      "ideas_agent",
            "agenda_agent":     "agenda_agent",
            "accounting_agent": "accounting_agent",
            "reporting_agent":  "reporting_agent",
            END:                END,
        },
    )

    # Agentes persistentes → confirmation_node
    for agent in ("tasks_agent", "ideas_agent", "agenda_agent", "accounting_agent"):
        builder.add_edge(agent, "confirmation_node")

    # reporting_agent → END (solo lectura, sin confirmación)
    builder.add_edge("reporting_agent", END)

    # confirmation_node → persist_node | orchestrator | END
    builder.add_conditional_edges(
        "confirmation_node",
        _route_confirmation,
        {
            "persist_node": "persist_node",
            "orchestrator": "orchestrator",
            END:            END,
        },
    )

    # persist_node → END
    builder.add_edge("persist_node", END)

    checkpointer = SqliteSaver(conn)
    return builder.compile(checkpointer=checkpointer)
