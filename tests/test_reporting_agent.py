"""Tests T-032 — reporting_agent: comportamiento del nodo.

Verifica:
- Retorna agent_response con el contenido del LLM.
- No setea confirmation_status (no pasa por confirmation_node).
- No setea payload (no persiste nada).
- Llama a los 4 fetchers de solo lectura.
- Usa el LLM de reporting.
- Los fetchers no tienen capacidad de escritura.
"""

from unittest.mock import MagicMock, patch

from src.agents.reporting_agent import (
    _build_context,
    reporting_agent_node,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(text: str = "Respuesta de reporting.") -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=text)
    return llm


def _base_state(message: str = "¿Qué tengo pendiente?") -> dict:
    return {
        "message": message,
        "pending_actions": [],
        "conversation_history": [],
    }


def _patched_node(
    message: str = "consulta",
    llm_text: str = "Respuesta.",
    tasks: list = None,
    ideas: list = None,
    events: list = None,
    accounting: list = None,
) -> dict:
    """Ejecuta reporting_agent_node con todos los fetchers y LLM mockeados."""
    with (
        patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm(llm_text)),
        patch("src.agents.reporting_agent._fetch_tasks", return_value=tasks or []),
        patch("src.agents.reporting_agent._fetch_ideas", return_value=ideas or []),
        patch("src.agents.reporting_agent._fetch_events", return_value=events or []),
        patch("src.agents.reporting_agent._fetch_accounting", return_value=accounting or []),
    ):
        return reporting_agent_node(_base_state(message))


# ── Comportamiento del nodo ───────────────────────────────────────────────────


class TestReportingAgentComportamiento:
    def test_retorna_agent_response(self):
        updates = _patched_node(llm_text="Reporte completo.")
        assert "agent_response" in updates

    def test_agent_response_contiene_texto_del_llm(self):
        updates = _patched_node(llm_text="Tienes 3 tareas pendientes.")
        assert updates["agent_response"] == "Tienes 3 tareas pendientes."

    def test_no_setea_confirmation_status(self):
        """reporting_agent no pasa por confirmation_node."""
        updates = _patched_node()
        assert "confirmation_status" not in updates

    def test_no_setea_payload(self):
        """reporting_agent no propone persistencia."""
        updates = _patched_node()
        assert "payload" not in updates

    def test_llama_a_get_llm_con_reporting(self):
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()) as mock_get_llm,
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            reporting_agent_node(_base_state())
        mock_get_llm.assert_called_once_with("reporting")

    def test_llama_a_los_cuatro_fetchers(self):
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]) as ft,
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]) as fi,
            patch("src.agents.reporting_agent._fetch_events", return_value=[]) as fe,
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]) as fa,
        ):
            reporting_agent_node(_base_state())
        ft.assert_called_once()
        fi.assert_called_once()
        fe.assert_called_once()
        fa.assert_called_once()

    def test_mensaje_se_incluye_en_prompt_al_llm(self):
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()) as mock_get_llm,
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            reporting_agent_node(_base_state("¿cuánto gasté este mes?"))
        llm_instance = mock_get_llm.return_value
        human_message = llm_instance.invoke.call_args.args[0][1][1]
        assert "¿cuánto gasté este mes?" in human_message

    def test_datos_de_todos_los_dominios_se_incluyen_en_contexto(self):
        tasks = [{"id": "T1", "title": "Reunión", "status": "pending"}]
        accounting = [{"type": "expense", "category": "Comida", "amount": 500}]

        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()) as mock_get_llm,
            patch("src.agents.reporting_agent._fetch_tasks", return_value=tasks),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=accounting),
        ):
            reporting_agent_node(_base_state("consulta"))

        llm_instance = mock_get_llm.return_value
        human_message = llm_instance.invoke.call_args.args[0][1][1]
        assert "Reunión" in human_message
        assert "Comida" in human_message


# ── Fetchers son solo lectura ─────────────────────────────────────────────────


class TestFetchersSoloLectura:
    """Verifica que los fetchers no exponen operaciones de escritura."""

    def test_fetch_tasks_no_tiene_write(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "write_task")
        assert not hasattr(mod, "delete_task")
        assert not hasattr(mod, "update_task")

    def test_fetch_accounting_no_tiene_write(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "write_entry")
        assert not hasattr(mod, "update_entry")
        assert not hasattr(mod, "delete_entry")

    def test_fetch_events_no_tiene_write(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "create_event")
        assert not hasattr(mod, "update_event")
        assert not hasattr(mod, "cancel_event")

    def test_fetch_ideas_no_tiene_write(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "write_idea")
        assert not hasattr(mod, "delete_idea")

    def test_no_importa_confirmation_status(self):
        """reporting_agent no usa ConfirmationStatus."""
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "ConfirmationStatus")


# ── _build_context ────────────────────────────────────────────────────────────


class TestBuildContext:
    def test_contexto_vacio_con_listas_vacias(self):
        ctx = _build_context([], [], [], [])
        assert ctx == "No hay datos disponibles."

    def test_contexto_incluye_seccion_tareas(self):
        tasks = [{"id": "T1", "title": "Reunión"}]
        ctx = _build_context(tasks, [], [], [])
        assert "TAREAS" in ctx
        assert "Reunión" in ctx

    def test_contexto_incluye_seccion_agenda(self):
        events = [{"title": "Dentista", "scheduled_for": "2024-06-10T10:00:00-03:00"}]
        ctx = _build_context([], [], events, [])
        assert "AGENDA" in ctx
        assert "Dentista" in ctx

    def test_contexto_incluye_seccion_contabilidad(self):
        accounting = [{"type": "expense", "amount": 500, "category": "Comida"}]
        ctx = _build_context([], [], [], accounting)
        assert "CONTABILIDAD" in ctx
        assert "Comida" in ctx

    def test_contexto_incluye_seccion_ideas(self):
        ideas = [{"theme": "Tecnología", "summary": "Usar LangGraph"}]
        ctx = _build_context([], ideas, [], [])
        assert "IDEAS" in ctx
        assert "LangGraph" in ctx

    def test_contexto_excluye_secciones_vacias(self):
        tasks = [{"id": "T1", "title": "X"}]
        ctx = _build_context(tasks, [], [], [])
        assert "AGENDA" not in ctx
        assert "CONTABILIDAD" not in ctx
        assert "IDEAS" not in ctx

    def test_contexto_es_json_valido_internamente(self):
        """El contenido de cada sección es JSON parseable."""
        tasks = [{"id": "T1", "title": "Reunión"}]
        ctx = _build_context(tasks, [], [], [])
        # Extraer el JSON después de "TAREAS:\n"
        json_part = ctx.split("TAREAS:\n", 1)[1]
        parsed = __import__("json").loads(json_part)
        assert parsed[0]["title"] == "Reunión"
