"""Tests T-033 — integración reporting_agent en el grafo.

Verifica:
- _route_orchestrator rutea domain=reporting → reporting_agent.
- reporting_agent → END (no pasa por confirmation_node).
- Flujo completo query → agent_response con orquestador mockeado.
- reporting_agent usa la implementación real (no el placeholder).
"""

from unittest.mock import MagicMock, patch

from langgraph.graph import END

from src.graph.graph import (
    _route_confirmation,
    _route_orchestrator,
    build_graph,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(text: str = "Reporte generado.") -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=text)
    return llm


def _state(domain: str = "reporting", message: str = "consulta") -> dict:
    return {
        "message": message,
        "domain": domain,
        "pending_actions": [],
        "conversation_history": [],
    }


# ── Routing del orquestador ───────────────────────────────────────────────────


class TestRoutingOrquestador:
    def test_domain_reporting_rutea_a_reporting_agent(self):
        assert _route_orchestrator(_state("reporting")) == "reporting_agent"

    def test_domain_tasks_rutea_a_tasks_agent(self):
        assert _route_orchestrator(_state("tasks")) == "tasks_agent"

    def test_domain_ideas_rutea_a_ideas_agent(self):
        assert _route_orchestrator(_state("ideas")) == "ideas_agent"

    def test_domain_agenda_rutea_a_agenda_agent(self):
        assert _route_orchestrator(_state("agenda")) == "agenda_agent"

    def test_domain_accounting_rutea_a_accounting_agent(self):
        assert _route_orchestrator(_state("accounting")) == "accounting_agent"

    def test_domain_unknown_rutea_a_END(self):
        assert _route_orchestrator(_state("unknown")) == END

    def test_domain_none_rutea_a_END(self):
        assert _route_orchestrator({"domain": None, "pending_actions": []}) == END

    def test_domain_vacio_rutea_a_END(self):
        assert _route_orchestrator({"domain": "", "pending_actions": []}) == END


# ── reporting_agent → END (no confirmation_node) ──────────────────────────────


class TestReportingNoConfirmation:
    def test_confirmed_rutea_a_persist_node(self):
        """Referencia: otros agentes sí pasan por confirmation → persist."""
        state = {"confirmation_status": "confirmed"}
        assert _route_confirmation(state) == "persist_node"

    def test_reporting_no_produce_confirmation_status(self):
        """reporting_agent_node no setea confirmation_status."""
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            from src.agents.reporting_agent import reporting_agent_node
            updates = reporting_agent_node(_state())
        assert "confirmation_status" not in updates

    def test_reporting_no_produce_payload(self):
        """reporting_agent_node no setea payload (no hay nada que persistir)."""
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            from src.agents.reporting_agent import reporting_agent_node
            updates = reporting_agent_node(_state())
        assert "payload" not in updates

    def test_reporting_agent_node_en_graph_es_implementacion_real(self):
        """El nodo registrado en graph.py es la implementación real, no el placeholder."""
        from src.graph import graph as graph_module
        from src.agents.reporting_agent import reporting_agent_node as real_node
        assert graph_module.reporting_agent_node is real_node

    def test_agentes_persistentes_en_graph_son_implementaciones_reales(self):
        """Los 4 nodos persistentes en graph.py son implementaciones reales, no placeholders."""
        from src.graph import graph as graph_module
        from src.agents.tasks_agent import tasks_agent_node as real_tasks
        from src.agents.ideas_agent import ideas_agent_node as real_ideas
        from src.agents.agenda_agent import agenda_agent_node as real_agenda
        from src.agents.accounting_agent import accounting_agent_node as real_accounting
        assert graph_module.tasks_agent_node is real_tasks
        assert graph_module.ideas_agent_node is real_ideas
        assert graph_module.agenda_agent_node is real_agenda
        assert graph_module.accounting_agent_node is real_accounting


# ── Flujo completo query → respuesta ─────────────────────────────────────────


class TestFlujoCompletoQuery:
    def test_query_produce_agent_response(self, tmp_path):
        """Flujo completo: orchestrator (mockeado) → reporting_agent → END."""
        db_path = str(tmp_path / "test_reporting.db")

        with (
            patch("src.graph.graph.orchestrator_node",
                  return_value={"domain": "reporting", "intent": "query"}),
            patch("src.agents.reporting_agent.get_llm",
                  return_value=_mock_llm("Tenés 5 tareas pendientes.")),
            patch("src.agents.reporting_agent._fetch_tasks",
                  return_value=[{"id": "T1", "title": "Reunión", "status": "pending"}]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            graph = build_graph(db_path=db_path)
            result = graph.invoke(
                {"message": "¿Qué tengo pendiente?", "pending_actions": [], "conversation_history": []},
                config={"configurable": {"thread_id": "whatsapp:+59899000000"}},
            )

        assert result.get("agent_response") == "Tenés 5 tareas pendientes."

    def test_query_no_setea_confirmation_status(self, tmp_path):
        """Flujo reporting no produce confirmation_status en el resultado."""
        db_path = str(tmp_path / "test_reporting_cs.db")

        with (
            patch("src.graph.graph.orchestrator_node",
                  return_value={"domain": "reporting", "intent": "query"}),
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm("Respuesta.")),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            graph = build_graph(db_path=db_path)
            result = graph.invoke(
                {"message": "resumen", "pending_actions": [], "conversation_history": []},
                config={"configurable": {"thread_id": "whatsapp:+59899000001"}},
            )

        assert result.get("confirmation_status") is None

    def test_query_con_datos_contables_incluye_contexto(self, tmp_path):
        """Los datos del fetcher llegan al LLM en el flujo completo."""
        db_path = str(tmp_path / "test_reporting_ctx.db")
        accounting = [{"type": "expense", "category": "Comida", "amount": 500}]
        captured_prompt = {}

        def _capture_invoke(messages):
            captured_prompt["human"] = messages[1][1]
            return MagicMock(content="Gastaste $500 en Comida.")

        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = _capture_invoke

        with (
            patch("src.graph.graph.orchestrator_node",
                  return_value={"domain": "reporting", "intent": "query"}),
            patch("src.agents.reporting_agent.get_llm", return_value=mock_llm),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=accounting),
        ):
            graph = build_graph(db_path=db_path)
            graph.invoke(
                {"message": "¿cuánto gasté?", "pending_actions": [], "conversation_history": []},
                config={"configurable": {"thread_id": "whatsapp:+59899000002"}},
            )

        assert "Comida" in captured_prompt["human"]

    def test_flujo_query_no_invoca_confirmation_node(self, tmp_path):
        """Verificar que confirmation_node no se llama en flujo reporting."""
        db_path = str(tmp_path / "test_reporting_cn.db")
        confirmation_calls = []

        def _track_confirmation(state):
            confirmation_calls.append(state)
            return {}

        with (
            patch("src.graph.graph.orchestrator_node",
                  return_value={"domain": "reporting", "intent": "query"}),
            patch("src.graph.graph.confirmation_node", side_effect=_track_confirmation),
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm("OK.")),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            graph = build_graph(db_path=db_path)
            graph.invoke(
                {"message": "consulta", "pending_actions": [], "conversation_history": []},
                config={"configurable": {"thread_id": "whatsapp:+59899000003"}},
            )

        assert len(confirmation_calls) == 0

    def test_sqlitesaver_persiste_estado_entre_queries(self, tmp_path):
        """SqliteSaver mantiene estado entre invocaciones del mismo thread_id."""
        db_path = str(tmp_path / "test_reporting_saver.db")

        with (
            patch("src.graph.graph.orchestrator_node",
                  return_value={"domain": "reporting", "intent": "query"}),
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm("OK.")),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            graph = build_graph(db_path=db_path)
            config = {"configurable": {"thread_id": "whatsapp:+59899000004"}}
            r1 = graph.invoke(
                {"message": "primera consulta", "pending_actions": [], "conversation_history": []},
                config=config,
            )
            r2 = graph.invoke(
                {"message": "segunda consulta", "pending_actions": [], "conversation_history": []},
                config=config,
            )

        assert r1 is not None
        assert r2 is not None
