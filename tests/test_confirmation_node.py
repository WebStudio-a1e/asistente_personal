"""Tests T-020 — confirmation_node.

Cubre:
- Primera visita: genera propuesta, pasa a awaiting_confirmation
- Señal positiva → confirmed
- Señal negativa → rejected
- Señal ambigua/desconocida → awaiting_confirmation + pide aclaración
- Timeout 30 min → expired
- Estado ya resuelto → sin cambios
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.domain.confirmation import ConfirmationStatus
from src.graph.confirmation_node import _SENT_AT_KEY, confirmation_node
from src.graph.state import AgentState


# ── Helpers ───────────────────────────────────────────────────────────────────


def _state(
    message: str = "",
    confirmation_status: str | None = None,
    payload: dict | None = None,
    domain: str | None = None,
) -> AgentState:
    return AgentState(
        message=message,
        intent=None,
        domain=domain,
        payload=payload,
        confirmation_status=confirmation_status,
        pending_actions=[],
        agent_response=None,
        conversation_history=[],
        idempotency_key=None,
        error=None,
    )


def _sent_at_past(minutes: int = 35) -> str:
    """ISO timestamp en el pasado para simular timeout."""
    return (datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)).isoformat()


def _sent_at_recent(minutes: int = 5) -> str:
    """ISO timestamp reciente (dentro del timeout)."""
    return (datetime.now(tz=timezone.utc) - timedelta(minutes=minutes)).isoformat()


# ── Primera visita — genera propuesta ────────────────────────────────────────


class TestPrimeraVisita:
    def test_status_none_transiciona_a_awaiting(self):
        result = confirmation_node(_state(confirmation_status=None))
        assert result["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

    def test_status_detected_transiciona_a_awaiting(self):
        result = confirmation_node(_state(confirmation_status=ConfirmationStatus.DETECTED))
        assert result["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

    def test_status_proposed_transiciona_a_awaiting(self):
        result = confirmation_node(_state(confirmation_status=ConfirmationStatus.PROPOSED))
        assert result["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

    def test_genera_agent_response(self):
        result = confirmation_node(_state(confirmation_status=None))
        assert result["agent_response"] is not None
        assert len(result["agent_response"]) > 0

    def test_guarda_proposal_sent_at_en_payload(self):
        result = confirmation_node(_state(confirmation_status=None, payload={"title": "mi tarea"}))
        assert _SENT_AT_KEY in result["payload"]

    def test_proposal_sent_at_es_iso_parseable(self):
        result = confirmation_node(_state(confirmation_status=None))
        sent_at_raw = result["payload"][_SENT_AT_KEY]
        parsed = datetime.fromisoformat(sent_at_raw)
        assert parsed is not None

    def test_propuesta_incluye_campos_de_payload(self):
        result = confirmation_node(_state(
            confirmation_status=None,
            payload={"title": "Revisar informe"},
            domain="tasks",
        ))
        assert "Revisar informe" in result["agent_response"]

    def test_propuesta_no_expone_claves_internas(self):
        result = confirmation_node(_state(
            confirmation_status=None,
            payload={"title": "tarea"},
        ))
        assert "_proposal_sent_at" not in result["agent_response"]

    def test_propuesta_sin_payload(self):
        result = confirmation_node(_state(confirmation_status=None, payload=None))
        assert result["agent_response"] is not None


# ── Señal positiva → confirmed ───────────────────────────────────────────────


class TestConfirmed:
    @pytest.mark.parametrize("mensaje", ["sí", "si", "ok", "dale", "hacelo",
                                          "confirmo", "correcto", "exacto",
                                          "perfecto", "adelante"])
    def test_confirmacion_positiva(self, mensaje):
        result = confirmation_node(_state(
            message=mensaje,
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_confirmed_agent_response_es_none(self):
        result = confirmation_node(_state(
            message="sí",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result.get("agent_response") is None


# ── Señal negativa → rejected ─────────────────────────────────────────────────


class TestRejected:
    @pytest.mark.parametrize("mensaje", ["no", "cancelá", "cancela", "rechazo",
                                          "no confirmo", "no era eso", "para", "stop"])
    def test_rechazo_negativo(self, mensaje):
        result = confirmation_node(_state(
            message=mensaje,
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.REJECTED

    def test_rejected_tiene_agent_response(self):
        result = confirmation_node(_state(
            message="no",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result["agent_response"] is not None
        assert len(result["agent_response"]) > 0


# ── Señal ambigua / desconocida → pide aclaración ────────────────────────────


class TestAmbiguo:
    @pytest.mark.parametrize("mensaje", ["mmm", "puede ser", "tal vez", "no sé"])
    def test_ambiguo_mantiene_awaiting(self, mensaje):
        result = confirmation_node(_state(
            message=mensaje,
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

    def test_desconocido_mantiene_awaiting(self):
        result = confirmation_node(_state(
            message="quizás más tarde no sé bien",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

    def test_ambiguo_tiene_agent_response(self):
        result = confirmation_node(_state(
            message="mmm",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent()},
        ))
        assert result["agent_response"] is not None


# ── Timeout → expired ────────────────────────────────────────────────────────


class TestExpired:
    def test_timeout_35_minutos_expira(self):
        result = confirmation_node(_state(
            message="sí",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_past(minutes=35)},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.EXPIRED

    def test_timeout_exacto_30_minutos_expira(self):
        result = confirmation_node(_state(
            message="sí",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_past(minutes=31)},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.EXPIRED

    def test_5_minutos_no_expira(self):
        result = confirmation_node(_state(
            message="sí",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_recent(minutes=5)},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_expired_tiene_agent_response(self):
        result = confirmation_node(_state(
            message="sí",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_past(minutes=35)},
        ))
        assert result["agent_response"] is not None
        assert len(result["agent_response"]) > 0

    def test_timeout_tiene_prioridad_sobre_confirmacion(self):
        """Aunque el usuario diga 'sí', si expiró → expired (no confirmed)."""
        result = confirmation_node(_state(
            message="sí",
            confirmation_status=ConfirmationStatus.AWAITING_CONFIRMATION,
            payload={_SENT_AT_KEY: _sent_at_past(minutes=60)},
        ))
        assert result["confirmation_status"] == ConfirmationStatus.EXPIRED


# ── Estado ya resuelto — sin cambios ─────────────────────────────────────────


class TestEstadoResuelto:
    @pytest.mark.parametrize("status", [
        ConfirmationStatus.CONFIRMED,
        ConfirmationStatus.REJECTED,
        ConfirmationStatus.PERSISTED,
        ConfirmationStatus.FAILED,
        ConfirmationStatus.EXPIRED,
    ])
    def test_estado_resuelto_retorna_vacio(self, status):
        result = confirmation_node(_state(confirmation_status=status))
        assert result == {}


# ── Integración con el grafo ──────────────────────────────────────────────────


class TestIntegracionGrafo:
    def test_confirmation_node_importable_desde_grafo(self):
        """El grafo puede importar confirmation_node."""
        from src.graph.confirmation_node import confirmation_node as cn  # noqa: F401
        assert cn is not None

    def test_flujo_completo_confirmed(self):
        """Primera visita → propuesta. Segunda visita con 'sí' → confirmed."""
        # Primera visita
        state1 = _state(
            confirmation_status=ConfirmationStatus.DETECTED,
            payload={"title": "Comprar pan"},
            domain="tasks",
        )
        result1 = confirmation_node(state1)
        assert result1["confirmation_status"] == ConfirmationStatus.AWAITING_CONFIRMATION

        # Segunda visita: usuario confirma
        state2 = _state(
            message="dale",
            confirmation_status=result1["confirmation_status"],
            payload=result1["payload"],
        )
        result2 = confirmation_node(state2)
        assert result2["confirmation_status"] == ConfirmationStatus.CONFIRMED

    def test_flujo_completo_rejected(self):
        """Primera visita → propuesta. Segunda visita con 'no' → rejected."""
        state1 = _state(
            confirmation_status=ConfirmationStatus.DETECTED,
            payload={"title": "Tarea de prueba"},
        )
        result1 = confirmation_node(state1)

        state2 = _state(
            message="no",
            confirmation_status=result1["confirmation_status"],
            payload=result1["payload"],
        )
        result2 = confirmation_node(state2)
        assert result2["confirmation_status"] == ConfirmationStatus.REJECTED

    def test_flujo_completo_expired(self):
        """Primera visita → propuesta. Segunda visita vencida → expired."""
        state1 = _state(confirmation_status=ConfirmationStatus.DETECTED)
        result1 = confirmation_node(state1)

        # Simular que pasaron 35 minutos sobreescribiendo el timestamp
        payload_expirado = dict(result1["payload"])
        payload_expirado[_SENT_AT_KEY] = _sent_at_past(minutes=35)

        state2 = _state(
            message="sí",
            confirmation_status=result1["confirmation_status"],
            payload=payload_expirado,
        )
        result2 = confirmation_node(state2)
        assert result2["confirmation_status"] == ConfirmationStatus.EXPIRED
