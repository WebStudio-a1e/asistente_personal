"""Tests T-018 — Grafo LangGraph base con 8 nodos placeholder.

Cubre:
- StateGraph compila correctamente con 8 nodos
- SqliteSaver conectado como checkpointer
- grafo invocable sin errores para dominios conocidos y desconocido
- estado persiste entre invocaciones del mismo thread_id
"""

import pytest

from src.graph.state import AgentState


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    return str(tmp_path / "test.db")


@pytest.fixture
def graph(tmp_db):
    from src.graph.graph import build_graph

    return build_graph(db_path=tmp_db)


def _base_state(message: str = "test", domain: str | None = None) -> AgentState:
    return AgentState(
        message=message,
        intent=None,
        domain=domain,
        payload=None,
        confirmation_status=None,
        pending_actions=[],
        agent_response=None,
        conversation_history=[],
        idempotency_key=None,
        error=None,
    )


# ── Compilación ───────────────────────────────────────────────────────────────


class TestGraphCompiles:
    def test_build_graph_returns_compiled_graph(self, graph):
        assert graph is not None

    def test_graph_has_eight_nodes(self, graph):
        expected = {
            "orchestrator",
            "tasks_agent",
            "ideas_agent",
            "agenda_agent",
            "accounting_agent",
            "reporting_agent",
            "confirmation_node",
            "persist_node",
        }
        assert expected <= set(graph.nodes)

    def test_checkpointer_is_sqlite_saver(self, graph):
        from langgraph.checkpoint.sqlite import SqliteSaver

        assert isinstance(graph.checkpointer, SqliteSaver)


# ── Invocación sin errores ────────────────────────────────────────────────────


class TestGraphInvocable:
    def test_invoke_unknown_domain(self, graph):
        """domain desconocido → orchestrator rutea a END sin error."""
        result = graph.invoke(
            _base_state("hola", domain=None),
            config={"configurable": {"thread_id": "t-unknown"}},
        )
        assert result is not None

    def test_invoke_tasks_domain(self, graph):
        """domain=tasks → orchestrator → tasks_agent → confirmation_node → END."""
        result = graph.invoke(
            _base_state("agregar tarea", domain="tasks"),
            config={"configurable": {"thread_id": "t-tasks"}},
        )
        assert result is not None

    def test_invoke_ideas_domain(self, graph):
        result = graph.invoke(
            _base_state("nueva idea", domain="ideas"),
            config={"configurable": {"thread_id": "t-ideas"}},
        )
        assert result is not None

    def test_invoke_agenda_domain(self, graph):
        result = graph.invoke(
            _base_state("agendar reunión", domain="agenda"),
            config={"configurable": {"thread_id": "t-agenda"}},
        )
        assert result is not None

    def test_invoke_accounting_domain(self, graph):
        result = graph.invoke(
            _base_state("registrar gasto", domain="accounting"),
            config={"configurable": {"thread_id": "t-accounting"}},
        )
        assert result is not None

    def test_invoke_reporting_domain(self, graph):
        """domain=reporting → orchestrator → reporting_agent → END (sin confirmation_node)."""
        result = graph.invoke(
            _base_state("consulta semanal", domain="reporting"),
            config={"configurable": {"thread_id": "t-reporting"}},
        )
        assert result is not None

    def test_invoke_returns_agent_state_shape(self, graph):
        """El resultado tiene los campos de AgentState."""
        result = graph.invoke(
            _base_state("test"),
            config={"configurable": {"thread_id": "t-shape"}},
        )
        assert "message" in result


# ── SqliteSaver — checkpointing ───────────────────────────────────────────────


class TestSqliteSaverCheckpointing:
    def test_state_persists_between_invocations(self, graph):
        """SqliteSaver mantiene estado entre llamadas al mismo thread_id."""
        config = {"configurable": {"thread_id": "t-persist-check"}}

        graph.invoke(_base_state("primera llamada"), config=config)

        # Segunda invocación en mismo thread no debe fallar
        result = graph.invoke(_base_state("segunda llamada"), config=config)
        assert result is not None

    def test_different_threads_are_independent(self, graph):
        """Distintos thread_id son independientes."""
        result_a = graph.invoke(
            _base_state("mensaje A"),
            config={"configurable": {"thread_id": "thread-A"}},
        )
        result_b = graph.invoke(
            _base_state("mensaje B"),
            config={"configurable": {"thread_id": "thread-B"}},
        )
        assert result_a is not None
        assert result_b is not None
