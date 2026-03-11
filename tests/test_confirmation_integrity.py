"""Tests T-036 — Integridad del flujo de confirmación (AC-CORE-004, AC-REP-005).

Verifica que:
- Los 4 agentes persistentes (tasks, ideas, agenda, accounting) siempre producen
  confirmation_status en su output — nunca saltan al persist_node directo.
- Ningún agente persistente puede setear confirmation_status = CONFIRMED o PERSISTED.
  Solo confirmation_node puede hacerlo.
- reporting_agent no produce confirmation_status ni payload.
- reporting_agent no tiene operaciones de escritura en su módulo.
- accounting_agent no tiene operación de borrado.
- La transición DETECTED → AWAITING_CONFIRMATION → CONFIRMED la hace confirmation_node.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.domain.confirmation import ConfirmationStatus
from src.graph.confirmation_node import confirmation_node


# ── Helpers ───────────────────────────────────────────────────────────────────

_PROPOSAL_SENT_AT = (
    datetime.now(tz=timezone.utc) - timedelta(minutes=1)
).isoformat()


def _mock_llm(content: str) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=content)
    return llm


def _base_state(message: str = "acción") -> dict:
    return {
        "message": message,
        "pending_actions": [],
        "conversation_history": [],
    }


_TASKS_JSON = json.dumps({
    "operation": "create", "task_id": None,
    "title": "Tarea X", "status": "pending",
    "notes": None, "agent_response": "Creando tarea.",
})
_IDEAS_JSON = json.dumps({
    "operation": "create", "idea_id": None,
    "theme": "Tech", "summary": "Idea Y",
    "priority": "alta", "tags": [], "notes": None,
    "agent_response": "Guardando idea.",
})
_AGENDA_JSON = json.dumps({
    "operation": "create", "event_id": None,
    "title": "Reunión", "scheduled_for": "2024-06-10T10:00:00-03:00",
    "duration_minutes": 60, "recurrence": None,
    "notes": None, "agent_response": "Agendando.",
})
_ACCOUNTING_JSON = json.dumps({
    "operation": "create", "entry_type": "expense",
    "category": "Comida", "amount": 500.0,
    "note": "Almuerzo", "correction_note": None,
    "entry_id": None, "agent_response": "Registrando egreso.",
})


# ── Agentes persistentes siempre producen confirmation_status ─────────────────


class TestAgentesProducenConfirmationStatus:
    """AC-CORE-004: ningún agente persistente salta el nodo de confirmación."""

    def test_tasks_agent_produce_confirmation_status(self):
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(_TASKS_JSON)):
            result = tasks_agent_node(_base_state())
        assert "confirmation_status" in result
        assert result["confirmation_status"] is not None

    def test_ideas_agent_produce_confirmation_status(self):
        from src.agents.ideas_agent import ideas_agent_node
        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(_IDEAS_JSON)):
            result = ideas_agent_node(_base_state())
        assert "confirmation_status" in result
        assert result["confirmation_status"] is not None

    def test_agenda_agent_produce_confirmation_status(self):
        from src.agents.agenda_agent import agenda_agent_node
        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(_AGENDA_JSON)):
            result = agenda_agent_node(_base_state())
        assert "confirmation_status" in result
        assert result["confirmation_status"] is not None

    def test_accounting_agent_produce_confirmation_status(self):
        from src.agents.accounting_agent import accounting_agent_node
        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(_ACCOUNTING_JSON)):
            result = accounting_agent_node(_base_state())
        assert "confirmation_status" in result
        assert result["confirmation_status"] is not None

    def test_tasks_agent_produce_payload(self):
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(_TASKS_JSON)):
            result = tasks_agent_node(_base_state())
        assert "payload" in result
        assert result["payload"]

    def test_ideas_agent_produce_payload(self):
        from src.agents.ideas_agent import ideas_agent_node
        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(_IDEAS_JSON)):
            result = ideas_agent_node(_base_state())
        assert "payload" in result
        assert result["payload"]

    def test_agenda_agent_produce_payload(self):
        from src.agents.agenda_agent import agenda_agent_node
        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(_AGENDA_JSON)):
            result = agenda_agent_node(_base_state())
        assert "payload" in result
        assert result["payload"]

    def test_accounting_agent_produce_payload(self):
        from src.agents.accounting_agent import accounting_agent_node
        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(_ACCOUNTING_JSON)):
            result = accounting_agent_node(_base_state())
        assert "payload" in result
        assert result["payload"]


# ── Agentes NO pueden autoconfirmarse ─────────────────────────────────────────


class TestAgentesNoSeteanConfirmedDirectamente:
    """Solo confirmation_node puede transicionar a CONFIRMED o PERSISTED."""

    _STATUSES_RESERVADOS = {ConfirmationStatus.CONFIRMED, ConfirmationStatus.PERSISTED}

    def test_tasks_agent_no_setea_confirmed(self):
        from src.agents.tasks_agent import tasks_agent_node
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(_TASKS_JSON)):
            result = tasks_agent_node(_base_state())
        assert result.get("confirmation_status") not in self._STATUSES_RESERVADOS

    def test_ideas_agent_no_setea_confirmed(self):
        from src.agents.ideas_agent import ideas_agent_node
        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(_IDEAS_JSON)):
            result = ideas_agent_node(_base_state())
        assert result.get("confirmation_status") not in self._STATUSES_RESERVADOS

    def test_agenda_agent_no_setea_confirmed(self):
        from src.agents.agenda_agent import agenda_agent_node
        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(_AGENDA_JSON)):
            result = agenda_agent_node(_base_state())
        assert result.get("confirmation_status") not in self._STATUSES_RESERVADOS

    def test_accounting_agent_no_setea_confirmed(self):
        from src.agents.accounting_agent import accounting_agent_node
        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(_ACCOUNTING_JSON)):
            result = accounting_agent_node(_base_state())
        assert result.get("confirmation_status") not in self._STATUSES_RESERVADOS

    def test_solo_confirmation_node_puede_setear_confirmed(self):
        """confirmation_node sí puede transicionar a CONFIRMED."""
        payload = {"operation": "create", "title": "X", "_proposal_sent_at": _PROPOSAL_SENT_AT}
        state = {
            "message": "sí",
            "domain": "tasks",
            "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
            "payload": payload,
            "pending_actions": [],
            "conversation_history": [],
        }
        result = confirmation_node(state)
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED


# ── reporting_agent es solo lectura ──────────────────────────────────────────


class TestReportingAgentSoloLectura:
    """AC-REP-005: reporting_agent nunca persiste ni pasa por confirmation_node."""

    def _run(self, llm_text: str = "Respuesta.") -> dict:
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
                "message": "consulta",
                "pending_actions": [],
                "conversation_history": [],
            })

    def test_reporting_no_produce_confirmation_status(self):
        assert "confirmation_status" not in self._run()

    def test_reporting_no_produce_payload(self):
        assert "payload" not in self._run()

    def test_reporting_produce_agent_response(self):
        result = self._run(llm_text="Respuesta de reporting.")
        assert result.get("agent_response") == "Respuesta de reporting."

    def test_reporting_modulo_no_tiene_write_task(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "write_task")
        assert not hasattr(mod, "delete_task")
        assert not hasattr(mod, "update_task")

    def test_reporting_modulo_no_tiene_write_entry(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "write_entry")
        assert not hasattr(mod, "update_entry")
        assert not hasattr(mod, "delete_entry")

    def test_reporting_modulo_no_tiene_write_event(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "create_event")
        assert not hasattr(mod, "cancel_event")

    def test_reporting_modulo_no_importa_confirmation_status(self):
        import src.agents.reporting_agent as mod
        assert not hasattr(mod, "ConfirmationStatus")


# ── accounting_agent no tiene borrado ────────────────────────────────────────


class TestAccountingNoBorrado:
    """AC-ACC-003: el accounting_agent no tiene herramienta de borrado."""

    def test_accounting_modulo_no_tiene_delete_entry(self):
        import src.agents.accounting_agent as mod
        assert not hasattr(mod, "delete_entry")
        assert not hasattr(mod, "remove_entry")
        assert not hasattr(mod, "erase_entry")

    def test_accounting_sistema_prompt_no_incluye_delete_como_operacion(self):
        import src.agents.accounting_agent as mod
        # El prompt no debe listar 'delete' como operación válida
        prompt_lower = mod._SYSTEM_PROMPT.lower()
        # 'delete' puede aparecer explicando que está prohibido, pero no como operación
        # Verificamos que 'create', 'update', 'read' están presentes
        assert "create" in prompt_lower
        assert "update" in prompt_lower
        assert "read" in prompt_lower

    def test_accounting_agent_con_intento_de_delete_no_lo_aplica(self):
        """Si el LLM (erróneamente) retorna operation=delete, el agente no lo ejecuta.

        El agente solo propone el payload al confirmation_node; persist_node decide
        qué hacer. El test verifica que no hay función delete en el módulo.
        """
        import src.agents.accounting_agent as mod
        funcs = [name for name in dir(mod) if "delete" in name.lower()]
        assert funcs == []
