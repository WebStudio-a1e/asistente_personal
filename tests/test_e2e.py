"""Tests T-036 — Flujos críticos end-to-end de los 5 agentes.

Valida los ACs de release invocando los nodos directamente con LLMs mockeados:
- AC-TASK-001/002: tasks_agent propone creación con status kanban válido.
- AC-IDEA-001/002: ideas_agent propone idea con campos canónicos.
- AC-AGENDA-001:   agenda_agent propone evento con scheduled_for -03:00.
- AC-ACC-001/003:  accounting_agent propone movimiento; no tiene operación delete.
- AC-REP-001/005:  reporting_agent responde sin pasar por confirmation_node.
- AC-CORE-004:     todos los agentes persistentes producen confirmation_status.
"""

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from src.domain.confirmation import ConfirmationStatus
from src.graph.confirmation_node import confirmation_node


# ── Helpers ───────────────────────────────────────────────────────────────────

_KANBAN_STATUSES = {"pending", "in_progress", "today", "completed"}

_PROPOSAL_SENT_AT = (
    datetime.now(tz=timezone.utc) - timedelta(minutes=1)
).isoformat()


def _mock_llm(content: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


def _base_state(message: str = "consulta") -> dict:
    return {
        "message": message,
        "pending_actions": [],
        "conversation_history": [],
    }


def _with_proposal(domain: str, payload: dict) -> dict:
    """Estado en espera de confirmación."""
    payload["_proposal_sent_at"] = _PROPOSAL_SENT_AT
    return {
        "message": "sí",
        "domain": domain,
        "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
        "payload": payload,
        "pending_actions": [],
        "conversation_history": [],
    }


# ── Agente de tareas (AC-TASK-001, AC-TASK-002) ───────────────────────────────


class TestFlujoTasks:
    _LLM_JSON = json.dumps({
        "operation": "create",
        "task_id": None,
        "title": "Revisar propuesta",
        "status": "pending",
        "notes": None,
        "agent_response": "Voy a crear la tarea 'Revisar propuesta'.",
    })

    def test_tasks_agent_produce_confirmation_status(self):
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = tasks_agent_node(_base_state("Crear tarea Revisar propuesta"))
        assert "confirmation_status" in result

    def test_tasks_agent_produce_payload(self):
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = tasks_agent_node(_base_state("Crear tarea Revisar propuesta"))
        assert "payload" in result
        assert result["payload"]["operation"] == "create"

    def test_tasks_agent_status_kanban_valido(self):
        """AC-TASK-002: status en el payload usa columnas kanban canónicas."""
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = tasks_agent_node(_base_state("Crear tarea"))
        assert result["payload"]["status"] in _KANBAN_STATUSES

    def test_tasks_confirmation_node_confirma(self):
        """Flujo completo: proposal → sí → confirmed."""
        payload = {"operation": "create", "title": "X", "status": "pending"}
        state = _with_proposal("tasks", payload)
        result = confirmation_node(state)
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_tasks_agent_no_setea_confirmed_directamente(self):
        """El agente no puede saltarse confirmation_node."""
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = tasks_agent_node(_base_state("Crear tarea"))
        status = result.get("confirmation_status")
        assert status != ConfirmationStatus.CONFIRMED
        assert status != ConfirmationStatus.PERSISTED


# ── Agente de ideas (AC-IDEA-001, AC-IDEA-002) ───────────────────────────────


class TestFlujoIdeas:
    _LLM_JSON = json.dumps({
        "operation": "create",
        "idea_id": None,
        "theme": "Tecnología",
        "summary": "Usar LangGraph para orquestar agentes",
        "priority": "alta",
        "tags": ["LangGraph", "agentes"],
        "notes": None,
        "agent_response": "Voy a guardar esta idea.",
    })

    def test_ideas_agent_produce_confirmation_status(self):
        from src.agents.ideas_agent import ideas_agent_node
        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = ideas_agent_node(_base_state("Guardar idea sobre LangGraph"))
        assert "confirmation_status" in result

    def test_ideas_agent_produce_payload_con_theme(self):
        """AC-IDEA-002: propone tema, resumen, prioridad."""
        from src.agents.ideas_agent import ideas_agent_node
        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = ideas_agent_node(_base_state("Guardar idea sobre LangGraph"))
        payload = result.get("payload", {})
        assert "theme" in payload or "summary" in payload  # al menos uno presente

    def test_ideas_confirmation_node_confirma(self):
        payload = {"operation": "create", "theme": "Tech", "summary": "Idea"}
        state = _with_proposal("ideas", payload)
        result = confirmation_node(state)
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_ideas_agent_no_setea_confirmed_directamente(self):
        from src.agents.ideas_agent import ideas_agent_node
        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = ideas_agent_node(_base_state("Guardar idea"))
        status = result.get("confirmation_status")
        assert status != ConfirmationStatus.CONFIRMED


# ── Agente de agenda (AC-AGENDA-001) ─────────────────────────────────────────


class TestFlujoAgenda:
    _LLM_JSON = json.dumps({
        "operation": "create",
        "event_id": None,
        "title": "Dentista",
        "scheduled_for": "2024-06-10T10:00:00-03:00",
        "duration_minutes": 60,
        "recurrence": None,
        "notes": None,
        "agent_response": "Agendando Dentista para el 10/06.",
    })

    def test_agenda_agent_produce_confirmation_status(self):
        from src.agents.agenda_agent import agenda_agent_node
        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = agenda_agent_node(_base_state("Agendar Dentista el 10 de junio a las 10"))
        assert "confirmation_status" in result

    def test_agenda_agent_scheduled_for_contiene_offset_mvd(self):
        """AC-AGENDA-001: scheduled_for tiene offset -03:00 de Montevideo."""
        from src.agents.agenda_agent import agenda_agent_node
        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = agenda_agent_node(_base_state("Agendar Dentista"))
        scheduled_for = result.get("payload", {}).get("scheduled_for", "")
        assert "-03:00" in scheduled_for

    def test_agenda_confirmation_node_confirma(self):
        payload = {
            "operation": "create",
            "title": "Dentista",
            "scheduled_for": "2024-06-10T10:00:00-03:00",
        }
        state = _with_proposal("agenda", payload)
        result = confirmation_node(state)
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_agenda_agent_cancel_no_usa_delete(self):
        """AC-AGENDA-002: la operación de cancelación es 'cancel', nunca 'delete'."""
        llm_cancel = _mock_llm(json.dumps({
            "operation": "cancel",
            "event_id": "E1",
            "title": None,
            "scheduled_for": None,
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Cancelando el evento.",
        }))
        from src.agents.agenda_agent import agenda_agent_node
        with patch("src.agents.agenda_agent.get_llm", return_value=llm_cancel):
            result = agenda_agent_node(_base_state("Cancelar reunión"))
        assert result.get("payload", {}).get("operation") == "cancel"


# ── Agente contable (AC-ACC-001, AC-ACC-003) ──────────────────────────────────


class TestFlujoAccounting:
    _LLM_JSON = json.dumps({
        "operation": "create",
        "entry_type": "expense",
        "category": "Comida",
        "amount": 500.0,
        "note": "Almuerzo",
        "correction_note": None,
        "entry_id": None,
        "agent_response": "Registrando egreso de $500 en Comida.",
    })

    def test_accounting_agent_produce_confirmation_status(self):
        from src.agents.accounting_agent import accounting_agent_node
        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = accounting_agent_node(_base_state("Gasté 500 pesos en comida"))
        assert "confirmation_status" in result

    def test_accounting_agent_no_tiene_operacion_delete(self):
        """AC-ACC-003: el módulo accounting_agent no expone herramienta de borrado."""
        import src.agents.accounting_agent as mod
        assert not hasattr(mod, "delete_entry")
        assert not hasattr(mod, "remove_entry")
        assert not hasattr(mod, "erase_entry")

    def test_accounting_agent_payload_no_incluye_delete(self):
        """AC-ACC-003: el LLM del agente no genera operation=delete."""
        from src.agents.accounting_agent import accounting_agent_node
        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = accounting_agent_node(_base_state("Gasté 500"))
        assert result.get("payload", {}).get("operation") != "delete"

    def test_accounting_confirmation_node_confirma(self):
        payload = {
            "operation": "create",
            "entry_type": "expense",
            "amount": 500.0,
            "category": "Comida",
        }
        state = _with_proposal("accounting", payload)
        result = confirmation_node(state)
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_accounting_agent_no_setea_confirmed_directamente(self):
        from src.agents.accounting_agent import accounting_agent_node
        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(self._LLM_JSON)):
            result = accounting_agent_node(_base_state("Gasté 500"))
        status = result.get("confirmation_status")
        assert status != ConfirmationStatus.CONFIRMED


# ── Reporting agent (AC-REP-001, AC-REP-005) ─────────────────────────────────


class TestFlujoReporting:
    def _run(self, message: str = "consulta", llm_text: str = "Respuesta.") -> dict:
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=llm_text)
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=llm),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            from src.agents.reporting_agent import reporting_agent_node
            return reporting_agent_node({
                "message": message,
                "pending_actions": [],
                "conversation_history": [],
            })

    def test_reporting_produce_agent_response(self):
        result = self._run(llm_text="Tenés 3 tareas pendientes.")
        assert result.get("agent_response") == "Tenés 3 tareas pendientes."

    def test_reporting_no_produce_confirmation_status(self):
        """AC-REP-005: reporting_agent no pasa por confirmation_node."""
        result = self._run()
        assert "confirmation_status" not in result

    def test_reporting_no_produce_payload(self):
        """AC-REP-005: reporting_agent no propone persistencia."""
        result = self._run()
        assert "payload" not in result

    def test_reporting_consulta_cruzada_todos_dominios(self):
        """AC-REP-001: reporting puede cruzar datos de múltiples dominios."""
        tasks = [{"id": "T1", "title": "Reunión", "status": "pending"}]
        accounting = [{"type": "expense", "category": "Comida", "amount": 500}]
        captured = {}

        def _capture(messages):
            captured["human"] = messages[1][1]
            return MagicMock(content="Resumen cruzado.")

        llm = MagicMock()
        llm.invoke.side_effect = _capture

        with (
            patch("src.agents.reporting_agent.get_llm", return_value=llm),
            patch("src.agents.reporting_agent._fetch_tasks", return_value=tasks),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=accounting),
        ):
            from src.agents.reporting_agent import reporting_agent_node
            reporting_agent_node({
                "message": "resumen de todo",
                "pending_actions": [],
                "conversation_history": [],
            })

        assert "Reunión" in captured["human"]
        assert "Comida" in captured["human"]
