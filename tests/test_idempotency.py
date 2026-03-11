"""Tests T-031 — idempotencia: webhook y doble confirmación.

Cubre:
- Webhook duplicado no persiste dos veces en processed_events.
- Webhook duplicado no invoca el grafo más de una vez.
- Doble confirmación (confirmation_node en estado ya resuelto) es no-op.
"""

import sqlite3
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from src.domain.confirmation import ConfirmationStatus
from src.graph.confirmation_node import confirmation_node
from src.main import _get_db, _get_graph, _get_twilio, app
from src.storage.sqlite import create_tables


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def client_mock():
    """TestClient con DB in-memory, grafo mock y Twilio mock."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    create_tables(conn)
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {}
    mock_twilio = MagicMock()
    app.dependency_overrides[_get_db] = lambda: conn
    app.dependency_overrides[_get_graph] = lambda: mock_graph
    app.dependency_overrides[_get_twilio] = lambda: mock_twilio
    yield TestClient(app), conn, mock_graph
    app.dependency_overrides.clear()
    conn.close()


def _form(
    message_sid: str = "SMtest001",
    from_number: str = "whatsapp:+59899000000",
    body: str = "Hola",
) -> dict:
    return {
        "MessageSid": message_sid,
        "From": from_number,
        "Body": body,
        "DateCreated": "2024-06-01T10:00:00Z",
        "To": "whatsapp:+14155238886",
    }


# ── Idempotencia de webhook ───────────────────────────────────────────────────


class TestWebhookIdempotencia:
    def test_primer_webhook_registra_en_processed_events(self, client_mock):
        client, conn, _ = client_mock
        client.post("/webhook", data=_form(message_sid="SM_idem_001"))
        count = conn.execute(
            "SELECT COUNT(*) FROM processed_events WHERE idempotency_key = ?",
            ("SM_idem_001",),
        ).fetchone()[0]
        assert count == 1

    def test_duplicado_no_inserta_segunda_fila(self, client_mock):
        client, conn, _ = client_mock
        form = _form(message_sid="SM_idem_002")
        client.post("/webhook", data=form)
        client.post("/webhook", data=form)
        count = conn.execute(
            "SELECT COUNT(*) FROM processed_events WHERE idempotency_key = ?",
            ("SM_idem_002",),
        ).fetchone()[0]
        assert count == 1

    def test_duplicado_no_invoca_grafo(self, client_mock):
        client, _, graph = client_mock
        form = _form(message_sid="SM_idem_003")
        client.post("/webhook", data=form)
        client.post("/webhook", data=form)
        assert graph.invoke.call_count == 1

    def test_tres_duplicados_solo_un_registro(self, client_mock):
        client, conn, _ = client_mock
        form = _form(message_sid="SM_idem_004")
        for _ in range(3):
            client.post("/webhook", data=form)
        count = conn.execute(
            "SELECT COUNT(*) FROM processed_events WHERE idempotency_key = ?",
            ("SM_idem_004",),
        ).fetchone()[0]
        assert count == 1

    def test_tres_duplicados_invocan_grafo_una_vez(self, client_mock):
        client, _, graph = client_mock
        form = _form(message_sid="SM_idem_005")
        for _ in range(3):
            client.post("/webhook", data=form)
        assert graph.invoke.call_count == 1

    def test_mensajes_distintos_se_registran_independientemente(self, client_mock):
        client, conn, _ = client_mock
        client.post("/webhook", data=_form(message_sid="SM_idem_A"))
        client.post("/webhook", data=_form(message_sid="SM_idem_B"))
        count = conn.execute(
            "SELECT COUNT(*) FROM processed_events"
        ).fetchone()[0]
        assert count == 2

    def test_mensajes_distintos_invocan_grafo_dos_veces(self, client_mock):
        client, _, graph = client_mock
        client.post("/webhook", data=_form(message_sid="SM_idem_C"))
        client.post("/webhook", data=_form(message_sid="SM_idem_D"))
        assert graph.invoke.call_count == 2

    def test_fallback_hash_duplicado_no_inserta_segunda_fila(self, client_mock):
        """Sin MessageSid, mismo remitente + timestamp + body es idempotente."""
        client, conn, _ = client_mock
        form = {
            "From": "whatsapp:+59899000000",
            "Body": "mismo mensaje",
            "DateCreated": "2024-06-01T10:00:00Z",
        }
        client.post("/webhook", data=form)
        client.post("/webhook", data=form)
        count = conn.execute(
            "SELECT COUNT(*) FROM processed_events"
        ).fetchone()[0]
        assert count == 1

    def test_fallback_hash_duplicado_no_invoca_grafo(self, client_mock):
        """Sin MessageSid, mismo remitente + timestamp + body no invoca grafo dos veces."""
        client, _, graph = client_mock
        form = {
            "From": "whatsapp:+59899000000",
            "Body": "mensaje hash",
            "DateCreated": "2024-06-01T12:00:00Z",
        }
        client.post("/webhook", data=form)
        client.post("/webhook", data=form)
        assert graph.invoke.call_count == 1


# ── Doble confirmación ────────────────────────────────────────────────────────


class TestDobleConfirmacion:
    """confirmation_node es idempotente en estados ya resueltos."""

    def _state(self, status: ConfirmationStatus) -> dict:
        return {
            "message": "sí",
            "confirmation_status": status,
            "payload": {"operation": "create", "title": "Tarea X"},
            "domain": "tasks",
            "pending_actions": [],
            "conversation_history": [],
        }

    def test_doble_confirmed_retorna_dict_vacio(self):
        updates = confirmation_node(self._state(ConfirmationStatus.CONFIRMED))
        assert updates == {}

    def test_doble_confirmed_no_modifica_status(self):
        """Retornar {} implica que el status no cambia."""
        updates = confirmation_node(self._state(ConfirmationStatus.CONFIRMED))
        assert "confirmation_status" not in updates

    def test_doble_rejected_retorna_dict_vacio(self):
        updates = confirmation_node(self._state(ConfirmationStatus.REJECTED))
        assert updates == {}

    def test_doble_persisted_retorna_dict_vacio(self):
        updates = confirmation_node(self._state(ConfirmationStatus.PERSISTED))
        assert updates == {}

    def test_doble_failed_retorna_dict_vacio(self):
        updates = confirmation_node(self._state(ConfirmationStatus.FAILED))
        assert updates == {}

    def test_si_despues_de_confirmed_es_noop(self):
        """'sí' cuando ya está confirmado no genera nueva confirmación."""
        state = self._state(ConfirmationStatus.CONFIRMED)
        state["message"] = "sí"
        updates = confirmation_node(state)
        assert updates == {}

    def test_no_despues_de_confirmed_es_noop(self):
        """'no' cuando ya está confirmado no cambia el estado."""
        state = self._state(ConfirmationStatus.CONFIRMED)
        state["message"] = "no"
        updates = confirmation_node(state)
        assert updates == {}
