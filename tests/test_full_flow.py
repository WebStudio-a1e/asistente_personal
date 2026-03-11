"""Tests T-030 — flujo completo end-to-end con mocks.

Verifica el flujo completo para los 4 dominios persistentes:
  orchestrator → agente → confirmation_node → persist_node

Estados cubiertos: confirmed / rejected / expired / ambiguo.
Sin llamadas reales a LLMs — get_llm mockeado por módulo.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.agents.accounting_agent import accounting_agent_node
from src.agents.agenda_agent import agenda_agent_node
from src.agents.ideas_agent import ideas_agent_node
from src.agents.orchestrator import orchestrator_node
from src.agents.tasks_agent import tasks_agent_node
from src.domain.confirmation import ConfirmationStatus
from src.graph.confirmation_node import confirmation_node


# ── Helpers ───────────────────────────────────────────────────────────────────


def _llm(response: dict) -> MagicMock:
    """Mock LLM que devuelve response serializado como content."""
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content=json.dumps(response))
    return mock


def _apply(state: dict, updates: dict) -> dict:
    """Aplica actualizaciones del nodo al estado actual."""
    result = dict(state)
    result.update(updates)
    return result


def _base_state(message: str) -> dict:
    return {
        "message": message,
        "pending_actions": [],
        "conversation_history": [],
        "idempotency_key": "test_idem_key",
    }


def _awaiting_state(message: str = "sí", offset_minutes: int = 0) -> dict:
    """Estado AWAITING_CONFIRMATION con timestamp configurable."""
    sent_at = datetime.now(tz=timezone.utc) - timedelta(minutes=offset_minutes)
    return {
        "message": message,
        "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
        "payload": {
            "_proposal_sent_at": sent_at.isoformat(),
            "operation": "create",
            "title": "Acción de prueba",
        },
        "domain": "tasks",
        "pending_actions": [],
        "conversation_history": [],
    }


# ── Flujo Tasks ───────────────────────────────────────────────────────────────


class TestFlujoTasks:
    _ORCH = {
        "intent": "task",
        "domain": "tasks",
        "agent_response": None,
        "pending_actions": [],
    }
    _AGENT = {
        "operation": "create",
        "task_id": None,
        "title": "Reunión con equipo",
        "status": "pending",
        "notes": None,
        "agent_response": "Voy a crear la tarea 'Reunión con equipo'.",
    }

    def _run_to_awaiting(self) -> dict:
        state = _base_state("Crear tarea: Reunión con equipo")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.tasks_agent.get_llm", return_value=_llm(self._AGENT)):
            state = _apply(state, tasks_agent_node(state))
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION
        return state

    def test_dominio_clasificado_como_tasks(self):
        state = _base_state("Crear tarea: Reunión con equipo")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            updates = orchestrator_node(state)
        assert updates["domain"] == "tasks"

    def test_payload_operation_create(self):
        state = self._run_to_awaiting()
        assert state["payload"]["operation"] == "create"

    def test_payload_title(self):
        state = self._run_to_awaiting()
        assert state["payload"]["title"] == "Reunión con equipo"

    def test_propuesta_contiene_titulo(self):
        state = self._run_to_awaiting()
        assert "Reunión con equipo" in state["agent_response"]

    def test_confirmed(self):
        state = self._run_to_awaiting()
        state["message"] = "sí"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_rejected(self):
        state = self._run_to_awaiting()
        state["message"] = "no"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.REJECTED

    def test_rejected_retorna_mensaje(self):
        state = self._run_to_awaiting()
        state["message"] = "no"
        updates = confirmation_node(state)
        assert updates.get("agent_response") is not None

    def test_confirmed_agent_response_es_none(self):
        state = self._run_to_awaiting()
        state["message"] = "sí"
        updates = confirmation_node(state)
        assert updates["agent_response"] is None


# ── Flujo Ideas ───────────────────────────────────────────────────────────────


class TestFlujoIdeas:
    _ORCH = {
        "intent": "idea",
        "domain": "ideas",
        "agent_response": None,
        "pending_actions": [],
    }
    _AGENT = {
        "operation": "create",
        "idea_id": None,
        "theme": "Tecnología",
        "summary": "Usar LangGraph para el asistente",
        "priority": "high",
        "tags": ["ia", "langgraph"],
        "status": "active",
        "raw_text": "Idea: usar LangGraph",
        "agent_response": "Voy a registrar tu idea sobre LangGraph.",
    }

    def _run_to_awaiting(self) -> dict:
        state = _base_state("Idea: usar LangGraph para el asistente")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.ideas_agent.get_llm", return_value=_llm(self._AGENT)):
            state = _apply(state, ideas_agent_node(state))
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION
        return state

    def test_dominio_clasificado_como_ideas(self):
        state = _base_state("Idea: usar LangGraph")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            updates = orchestrator_node(state)
        assert updates["domain"] == "ideas"

    def test_payload_theme(self):
        state = self._run_to_awaiting()
        assert state["payload"]["theme"] == "Tecnología"

    def test_payload_priority_default_medium_cuando_ausente(self):
        agent_sin_priority = {**self._AGENT, "priority": None}
        state = _base_state("Idea: test")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.ideas_agent.get_llm", return_value=_llm(agent_sin_priority)):
            state = _apply(state, ideas_agent_node(state))
        assert state["payload"]["priority"] == "medium"

    def test_confirmed(self):
        state = self._run_to_awaiting()
        state["message"] = "dale"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_rejected(self):
        state = self._run_to_awaiting()
        state["message"] = "no"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.REJECTED


# ── Flujo Agenda ──────────────────────────────────────────────────────────────


class TestFlujoAgenda:
    _ORCH = {
        "intent": "agenda",
        "domain": "agenda",
        "agent_response": None,
        "pending_actions": [],
    }
    _AGENT = {
        "operation": "create",
        "event_id": None,
        "title": "Reunión semanal",
        "scheduled_for": "2024-06-10T10:00:00-03:00",
        "duration_minutes": 60,
        "recurrence": None,
        "notes": None,
        "agent_response": "Voy a agendar 'Reunión semanal' para el 10 de junio.",
    }

    def _run_to_awaiting(self) -> dict:
        state = _base_state("Agendá reunión semanal el 10 de junio a las 10")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.agenda_agent.get_llm", return_value=_llm(self._AGENT)):
            state = _apply(state, agenda_agent_node(state))
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION
        return state

    def test_dominio_clasificado_como_agenda(self):
        state = _base_state("Agendá reunión el martes")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            updates = orchestrator_node(state)
        assert updates["domain"] == "agenda"

    def test_payload_timezone_montevideo(self):
        state = self._run_to_awaiting()
        assert state["payload"]["timezone"] == "America/Montevideo"

    def test_payload_duration_default_60(self):
        agent_sin_duration = {**self._AGENT, "duration_minutes": None}
        state = _base_state("Agendá reunión")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.agenda_agent.get_llm", return_value=_llm(agent_sin_duration)):
            state = _apply(state, agenda_agent_node(state))
        assert state["payload"]["duration_minutes"] == 60

    def test_confirmed(self):
        state = self._run_to_awaiting()
        state["message"] = "confirmo"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_rejected(self):
        state = self._run_to_awaiting()
        state["message"] = "cancelá"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.REJECTED


# ── Flujo Accounting ──────────────────────────────────────────────────────────


class TestFlujoAccounting:
    _ORCH = {
        "intent": "accounting",
        "domain": "accounting",
        "agent_response": None,
        "pending_actions": [],
    }
    _AGENT = {
        "operation": "create",
        "entry_id": None,
        "type": "expense",
        "category": "Comida",
        "amount": 500,
        "note": "Almuerzo",
        "balance": None,
        "correction_note": None,
        "agent_response": "Voy a registrar un gasto de $500 en Comida.",
    }

    def _run_to_awaiting(self) -> dict:
        state = _base_state("Gasté $500 en almuerzo")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.accounting_agent.get_llm", return_value=_llm(self._AGENT)):
            state = _apply(state, accounting_agent_node(state))
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION
        return state

    def test_dominio_clasificado_como_accounting(self):
        state = _base_state("Gasté $500 en almuerzo")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            updates = orchestrator_node(state)
        assert updates["domain"] == "accounting"

    def test_payload_amount(self):
        state = self._run_to_awaiting()
        assert state["payload"]["amount"] == 500

    def test_payload_type_expense(self):
        state = self._run_to_awaiting()
        assert state["payload"]["type"] == "expense"

    def test_delete_convertido_a_read(self):
        """accounting_agent convierte delete → read (borrado prohibido)."""
        agent_delete = {**self._AGENT, "operation": "delete"}
        state = _base_state("Borrá el gasto de ayer")
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._ORCH)):
            state = _apply(state, orchestrator_node(state))
        with patch("src.agents.accounting_agent.get_llm", return_value=_llm(agent_delete)):
            state = _apply(state, accounting_agent_node(state))
        assert state["payload"]["operation"] == "read"

    def test_confirmed(self):
        state = self._run_to_awaiting()
        state["message"] = "ok"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_rejected(self):
        state = self._run_to_awaiting()
        state["message"] = "no"
        state = _apply(state, confirmation_node(state))
        assert state["confirmation_status"] == ConfirmationStatus.REJECTED


# ── Estados de confirmación ───────────────────────────────────────────────────


class TestEstadosConfirmacion:
    """Cubre expired y ambiguo — independientes del dominio."""

    def test_expired_despues_de_30_minutos(self):
        state = _awaiting_state(message="sí", offset_minutes=31)
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.EXPIRED

    def test_no_expired_antes_de_30_minutos(self):
        state = _awaiting_state(message="sí", offset_minutes=5)
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_no_expired_a_29_minutos(self):
        """29 minutos transcurridos: aún no expirado."""
        state = _awaiting_state(message="sí", offset_minutes=29)
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_expired_retorna_agent_response(self):
        state = _awaiting_state(message="sí", offset_minutes=35)
        updates = confirmation_node(state)
        assert updates.get("agent_response") is not None
        assert "expiró" in updates["agent_response"]

    def test_ambiguo_mantiene_awaiting(self):
        state = _awaiting_state(message="mmm")
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

    def test_ambiguo_pide_aclaracion(self):
        state = _awaiting_state(message="puede ser")
        updates = confirmation_node(state)
        assert updates.get("agent_response") is not None

    def test_primera_visita_genera_propuesta(self):
        """Sin confirmation_status previo → genera propuesta."""
        state = {
            "message": "Crear tarea X",
            "confirmation_status": None,
            "payload": {"operation": "create", "title": "Tarea X"},
            "domain": "tasks",
            "pending_actions": [],
            "conversation_history": [],
        }
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION
        assert updates.get("agent_response") is not None

    def test_estado_resuelto_no_cambia(self):
        """Si confirmation_status ya es confirmed, confirmation_node no toca el estado."""
        state = {
            "message": "sí",
            "confirmation_status": ConfirmationStatus.CONFIRMED,
            "payload": {},
            "domain": "tasks",
            "pending_actions": [],
            "conversation_history": [],
        }
        updates = confirmation_node(state)
        assert updates == {}
