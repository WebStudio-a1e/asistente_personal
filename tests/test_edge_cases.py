"""Tests T-031 — edge cases: timeout expirado y multi-intención.

Cubre:
- Timeout de 30 minutos expira sin llegar a persist_node.
- _route_confirmation dirige correctamente confirmed/rejected/expired.
- Multi-intención: orchestrator produce pending_actions; cada acción
  se confirma por separado sin afectar las demás.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from langgraph.graph import END

from src.agents.orchestrator import orchestrator_node
from src.domain.confirmation import ConfirmationStatus
from src.graph.confirmation_node import confirmation_node
from src.graph.graph import _route_confirmation


# ── Helpers ───────────────────────────────────────────────────────────────────


def _llm(response: dict) -> MagicMock:
    mock = MagicMock()
    mock.invoke.return_value = MagicMock(content=json.dumps(response))
    return mock


def _awaiting_state(offset_minutes: int, message: str = "sí") -> dict:
    sent_at = datetime.now(tz=timezone.utc) - timedelta(minutes=offset_minutes)
    return {
        "message": message,
        "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
        "payload": {
            "_proposal_sent_at": sent_at.isoformat(),
            "operation": "create",
            "title": "Tarea de prueba",
        },
        "domain": "tasks",
        "pending_actions": [],
        "conversation_history": [],
    }


# ── Timeout expira sin persistir ──────────────────────────────────────────────


class TestTimeoutExpira:
    def test_expired_a_31_minutos(self):
        updates = confirmation_node(_awaiting_state(offset_minutes=31))
        assert updates["confirmation_status"] == ConfirmationStatus.EXPIRED

    def test_expired_no_confirma_aunque_mensaje_sea_si(self):
        """Timeout tiene prioridad sobre la señal positiva del usuario."""
        state = _awaiting_state(offset_minutes=31, message="sí")
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.EXPIRED

    def test_expired_retorna_agent_response(self):
        updates = confirmation_node(_awaiting_state(offset_minutes=35))
        assert updates.get("agent_response") is not None
        assert "expiró" in updates["agent_response"]

    def test_no_expired_a_29_minutos(self):
        state = _awaiting_state(offset_minutes=29, message="sí")
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_sin_timestamp_no_expira(self):
        """Sin _proposal_sent_at en payload, evalúa señal normalmente."""
        state = {
            "message": "sí",
            "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
            "payload": {"operation": "create"},
            "domain": "tasks",
            "pending_actions": [],
            "conversation_history": [],
        }
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_route_expired_es_END(self):
        """Estado expired → _route_confirmation devuelve END (no persist_node)."""
        state = {"confirmation_status": ConfirmationStatus.EXPIRED}
        assert _route_confirmation(state) == END

    def test_route_confirmed_es_persist_node(self):
        state = {"confirmation_status": ConfirmationStatus.CONFIRMED}
        assert _route_confirmation(state) == "persist_node"

    def test_route_rejected_es_orchestrator(self):
        state = {"confirmation_status": ConfirmationStatus.REJECTED}
        assert _route_confirmation(state) == "orchestrator"

    def test_route_awaiting_es_END(self):
        """awaiting_confirmation sin resolver → END (no persist)."""
        state = {"confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION}
        assert _route_confirmation(state) == END

    def test_route_none_es_END(self):
        """Sin status → END."""
        state = {"confirmation_status": None}
        assert _route_confirmation(state) == END


# ── Multi-intención confirma una por una ──────────────────────────────────────


class TestMultiIntencion:
    _MULTI_ORCH = {
        "intent": "task",
        "domain": "tasks",
        "agent_response": None,
        "pending_actions": [
            {"intent": "task", "domain": "tasks", "message": "crear tarea: revisar código"},
            {"intent": "idea", "domain": "ideas", "message": "registrar idea: refactor"},
        ],
    }

    def _orch_state(self) -> dict:
        return {
            "message": "Crear tarea: revisar código. Y anotá la idea de refactorizar.",
            "pending_actions": [],
            "conversation_history": [],
        }

    def test_orchestrator_retorna_dos_pending_actions(self):
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._MULTI_ORCH)):
            updates = orchestrator_node(self._orch_state())
        assert len(updates["pending_actions"]) == 2

    def test_pending_actions_tiene_campos_requeridos(self):
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._MULTI_ORCH)):
            updates = orchestrator_node(self._orch_state())
        for action in updates["pending_actions"]:
            assert "intent" in action
            assert "domain" in action
            assert "message" in action

    def test_primer_pending_action_domain_tasks(self):
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._MULTI_ORCH)):
            updates = orchestrator_node(self._orch_state())
        assert updates["pending_actions"][0]["domain"] == "tasks"

    def test_segundo_pending_action_domain_ideas(self):
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(self._MULTI_ORCH)):
            updates = orchestrator_node(self._orch_state())
        assert updates["pending_actions"][1]["domain"] == "ideas"

    def test_confirmar_primera_accion_no_toca_pending_actions(self):
        """confirmation_node no elimina pending_actions al confirmar una acción."""
        sent_at = datetime.now(tz=timezone.utc)
        state = {
            "message": "sí",
            "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
            "payload": {
                "_proposal_sent_at": sent_at.isoformat(),
                "operation": "create",
                "title": "revisar código",
            },
            "domain": "tasks",
            "pending_actions": [
                {"intent": "idea", "domain": "ideas", "message": "registrar idea: refactor"},
            ],
            "conversation_history": [],
        }
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.CONFIRMED
        # confirmation_node no modifica pending_actions
        assert "pending_actions" not in updates

    def test_rechazar_primera_accion_no_toca_pending_actions(self):
        """Rechazar una acción tampoco elimina las restantes pending_actions."""
        sent_at = datetime.now(tz=timezone.utc)
        state = {
            "message": "no",
            "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
            "payload": {
                "_proposal_sent_at": sent_at.isoformat(),
                "operation": "create",
            },
            "domain": "tasks",
            "pending_actions": [
                {"intent": "idea", "domain": "ideas", "message": "registrar idea"},
            ],
            "conversation_history": [],
        }
        updates = confirmation_node(state)
        assert updates["confirmation_status"] == ConfirmationStatus.REJECTED
        assert "pending_actions" not in updates

    def test_intencion_unica_produce_pending_actions_vacio(self):
        """Mensaje de intención única produce lista vacía de pending_actions."""
        single = {
            "intent": "task",
            "domain": "tasks",
            "agent_response": None,
            "pending_actions": [],
        }
        with patch("src.agents.orchestrator.get_llm", return_value=_llm(single)):
            updates = orchestrator_node(self._orch_state())
        assert updates["pending_actions"] == []
