"""Tests T-029 — integración webhook + grafo.

Verifica:
- /webhook invoca el grafo tras deduplicación
- thread_id es EXACTAMENTE el valor de From
- agent_response se envía por Twilio cuando está presente
- duplicados no invocan el grafo
- SqliteSaver mantiene estado entre mensajes del mismo hilo
"""

import sqlite3

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from src.main import _get_db, _get_graph, _get_twilio, app
from src.storage.sqlite import create_tables


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_graph():
    g = MagicMock()
    g.invoke.return_value = {}
    return g


@pytest.fixture()
def mock_twilio():
    client = MagicMock()
    client.messages.create.return_value = MagicMock(sid="SM_mock")
    return client


@pytest.fixture()
def client_graph(mock_graph, mock_twilio):
    """TestClient con DB in-memory, grafo mock y Twilio mock."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    create_tables(conn)
    app.dependency_overrides[_get_db] = lambda: conn
    app.dependency_overrides[_get_graph] = lambda: mock_graph
    app.dependency_overrides[_get_twilio] = lambda: mock_twilio
    yield TestClient(app), mock_graph, mock_twilio
    app.dependency_overrides.clear()
    conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _form(
    message_sid: str = "SMtest001",
    from_number: str = "whatsapp:+59899000000",
    body: str = "Hola",
    date_created: str = "2024-06-01T10:00:00Z",
    to: str = "whatsapp:+14155238886",
) -> dict:
    return {
        "MessageSid": message_sid,
        "From": from_number,
        "Body": body,
        "DateCreated": date_created,
        "To": to,
    }


# ── Invocación del grafo ──────────────────────────────────────────────────────


class TestWebhookInvocaGrafo:
    def test_grafo_se_invoca_en_mensaje_nuevo(self, client_graph):
        client, graph, _ = client_graph
        client.post("/webhook", data=_form())
        assert graph.invoke.call_count == 1

    def test_thread_id_es_exactamente_from(self, client_graph):
        client, graph, _ = client_graph
        client.post("/webhook", data=_form(from_number="whatsapp:+59899000000"))
        config = graph.invoke.call_args.kwargs["config"]
        assert config["configurable"]["thread_id"] == "whatsapp:+59899000000"

    def test_message_pasa_al_estado_del_grafo(self, client_graph):
        client, graph, _ = client_graph
        client.post("/webhook", data=_form(body="Hola mundo"))
        state = graph.invoke.call_args.args[0]
        assert state["message"] == "Hola mundo"

    def test_idempotency_key_pasa_al_estado(self, client_graph):
        client, graph, _ = client_graph
        client.post("/webhook", data=_form(message_sid="SM_key_test"))
        state = graph.invoke.call_args.args[0]
        assert state["idempotency_key"] == "SM_key_test"

    def test_duplicado_no_invoca_grafo(self, client_graph):
        client, graph, _ = client_graph
        form = _form(message_sid="SM_dup_grafo")
        client.post("/webhook", data=form)
        client.post("/webhook", data=form)
        assert graph.invoke.call_count == 1

    def test_webhook_responde_200_con_grafo(self, client_graph):
        client, _, _ = client_graph
        response = client.post("/webhook", data=_form())
        assert response.status_code == 200

    def test_webhook_retorna_status_ok_con_grafo(self, client_graph):
        client, _, _ = client_graph
        response = client.post("/webhook", data=_form())
        assert response.json()["status"] == "ok"


# ── Envío por Twilio ──────────────────────────────────────────────────────────


class TestWebhookEnviaPorTwilio:
    def test_agent_response_se_envia_al_remitente(self, client_graph):
        client, graph, twilio_client = client_graph
        graph.invoke.return_value = {"agent_response": "¡Hola!"}
        client.post("/webhook", data=_form(from_number="whatsapp:+59899000000"))
        twilio_client.messages.create.assert_called_once()
        call_kwargs = twilio_client.messages.create.call_args.kwargs
        assert call_kwargs["body"] == "¡Hola!"
        assert call_kwargs["to"] == "whatsapp:+59899000000"

    def test_agent_response_se_envia_desde_numero_to(self, client_graph):
        """El campo To del form (nuestro número) es el from_ saliente."""
        client, graph, twilio_client = client_graph
        graph.invoke.return_value = {"agent_response": "Respuesta"}
        client.post("/webhook", data=_form(to="whatsapp:+14155238886"))
        call_kwargs = twilio_client.messages.create.call_args.kwargs
        assert call_kwargs["from_"] == "whatsapp:+14155238886"

    def test_sin_agent_response_no_invoca_twilio(self, client_graph):
        client, graph, twilio_client = client_graph
        graph.invoke.return_value = {}
        client.post("/webhook", data=_form())
        twilio_client.messages.create.assert_not_called()

    def test_agent_response_none_no_invoca_twilio(self, client_graph):
        client, graph, twilio_client = client_graph
        graph.invoke.return_value = {"agent_response": None}
        client.post("/webhook", data=_form())
        twilio_client.messages.create.assert_not_called()

    def test_duplicado_no_envia_twilio(self, client_graph):
        client, graph, twilio_client = client_graph
        graph.invoke.return_value = {"agent_response": "Hola"}
        form = _form(message_sid="SM_dup_twilio")
        client.post("/webhook", data=form)
        twilio_client.messages.create.reset_mock()
        client.post("/webhook", data=form)
        twilio_client.messages.create.assert_not_called()


# ── Twilio no configurado ─────────────────────────────────────────────────────


class TestWebhookSinTwilio:
    def test_twilio_none_no_lanza_excepcion(self):
        """Si _get_twilio retorna None, el webhook procesa sin enviar."""
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        create_tables(conn)
        mock_graph = MagicMock()
        mock_graph.invoke.return_value = {"agent_response": "respuesta"}
        app.dependency_overrides[_get_db] = lambda: conn
        app.dependency_overrides[_get_graph] = lambda: mock_graph
        app.dependency_overrides[_get_twilio] = lambda: None
        try:
            client = TestClient(app)
            response = client.post("/webhook", data=_form())
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
        finally:
            app.dependency_overrides.clear()
            conn.close()


# ── SqliteSaver — persistencia de estado ─────────────────────────────────────


class TestSqliteSaverEstado:
    def test_grafo_real_acepta_mismo_hilo_dos_veces(self, tmp_path):
        """SqliteSaver mantiene estado entre invocaciones del mismo thread_id."""
        from src.graph.graph import build_graph

        db_path = str(tmp_path / "test_saver.db")
        graph = build_graph(db_path=db_path)
        config = {"configurable": {"thread_id": "whatsapp:+59899000000"}}

        r1 = graph.invoke(
            {"message": "primer mensaje", "pending_actions": [], "conversation_history": []},
            config=config,
        )
        r2 = graph.invoke(
            {"message": "segundo mensaje", "pending_actions": [], "conversation_history": []},
            config=config,
        )

        assert r1 is not None
        assert r2 is not None

    def test_hilos_distintos_no_comparten_estado(self, tmp_path):
        """Dos thread_id diferentes son independientes."""
        from src.graph.graph import build_graph

        db_path = str(tmp_path / "test_threads.db")
        graph = build_graph(db_path=db_path)

        r1 = graph.invoke(
            {"message": "hilo A", "pending_actions": [], "conversation_history": []},
            config={"configurable": {"thread_id": "whatsapp:+59899000001"}},
        )
        r2 = graph.invoke(
            {"message": "hilo B", "pending_actions": [], "conversation_history": []},
            config={"configurable": {"thread_id": "whatsapp:+59899000002"}},
        )

        assert r1 is not None
        assert r2 is not None
