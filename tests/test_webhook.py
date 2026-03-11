"""Tests T-028 — POST /webhook + deduplicación.

Sin llamadas reales a Twilio ni al grafo.
Dependency _get_db se sobreescribe con SQLite in-memory.
"""

import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.main import _get_db, _idempotency_key, _parse_form, app
from src.storage.sqlite import create_tables


# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def client_db():
    """TestClient con DB in-memory y override de dependencia."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    create_tables(conn)
    app.dependency_overrides[_get_db] = lambda: conn
    yield TestClient(app), conn
    app.dependency_overrides.clear()
    conn.close()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _twilio_form(
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


# ── GET /health (regresión) ───────────────────────────────────────────────────


class TestHealth:
    def test_health_sigue_respondiendo_200(self, client_db):
        client, _ = client_db
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ── POST /webhook — respuesta básica ─────────────────────────────────────────


class TestWebhookBasico:
    def test_webhook_responde_200(self, client_db):
        client, _ = client_db
        response = client.post("/webhook", data=_twilio_form())
        assert response.status_code == 200

    def test_webhook_retorna_status_ok(self, client_db):
        client, _ = client_db
        response = client.post("/webhook", data=_twilio_form())
        assert response.json()["status"] == "ok"

    def test_webhook_acepta_body_vacio(self, client_db):
        client, _ = client_db
        response = client.post("/webhook", data=_twilio_form(body=""))
        assert response.status_code == 200

    def test_webhook_acepta_form_sin_message_sid(self, client_db):
        client, _ = client_db
        form = {
            "From": "whatsapp:+59899000000",
            "Body": "sin sid",
            "DateCreated": "2024-06-01T10:00:00Z",
        }
        response = client.post("/webhook", data=form)
        assert response.status_code == 200


# ── _parse_form ───────────────────────────────────────────────────────────────


class TestParseForm:
    def test_extrae_campos_simples(self):
        raw = b"MessageSid=SM123&From=whatsapp%3A%2B1&Body=Hola"
        form = _parse_form(raw)
        assert form["MessageSid"] == "SM123"
        assert form["From"] == "whatsapp:+1"
        assert form["Body"] == "Hola"

    def test_campo_ausente_no_en_dict(self):
        raw = b"Body=Test"
        form = _parse_form(raw)
        assert "MessageSid" not in form

    def test_body_vacio_devuelve_string_vacio(self):
        raw = b"Body="
        form = _parse_form(raw)
        assert form["Body"] == ""

    def test_cuerpo_vacio_devuelve_dict_vacio(self):
        form = _parse_form(b"")
        assert form == {}


# ── Idempotencia — _idempotency_key ──────────────────────────────────────────


class TestIdempotencyKey:
    def test_usa_message_sid_si_presente(self):
        key = _idempotency_key("SM12345", "whatsapp:+1", "2024-06-01T10:00:00Z", "hola")
        assert key == "SM12345"

    def test_fallback_hash_incluye_remitente_timestamp_y_body(self):
        key = _idempotency_key("", "whatsapp:+59899000000", "2024-06-01T10:00:00Z", "hola")
        raw = "whatsapp:+59899000000" "2024-06-01T10:00:00Z" "hola"
        expected = hashlib.sha256(raw.encode()).hexdigest()[:32]
        assert key == expected

    def test_fallback_hash_longitud_32(self):
        key = _idempotency_key("", "whatsapp:+1", "2024-06-01", "body")
        assert len(key) == 32

    def test_mismo_sid_produce_misma_clave(self):
        k1 = _idempotency_key("SMabc", "whatsapp:+1", "ts1", "a")
        k2 = _idempotency_key("SMabc", "whatsapp:+2", "ts2", "b")
        assert k1 == k2  # el SID tiene prioridad

    def test_mismo_remitente_timestamp_body_produce_misma_clave(self):
        k1 = _idempotency_key("", "whatsapp:+1", "2024-06-01T10:00:00Z", "hola")
        k2 = _idempotency_key("", "whatsapp:+1", "2024-06-01T10:00:00Z", "hola")
        assert k1 == k2

    def test_diferente_timestamp_produce_diferente_clave(self):
        k1 = _idempotency_key("", "whatsapp:+1", "2024-06-01T10:00:00Z", "hola")
        k2 = _idempotency_key("", "whatsapp:+1", "2024-06-01T11:00:00Z", "hola")
        assert k1 != k2

    def test_diferente_body_produce_diferente_clave(self):
        k1 = _idempotency_key("", "whatsapp:+1", "2024-06-01T10:00:00Z", "mensaje A")
        k2 = _idempotency_key("", "whatsapp:+1", "2024-06-01T10:00:00Z", "mensaje B")
        assert k1 != k2

    def test_diferente_remitente_produce_diferente_clave(self):
        k1 = _idempotency_key("", "whatsapp:+59899000001", "2024-06-01T10:00:00Z", "hola")
        k2 = _idempotency_key("", "whatsapp:+59899000002", "2024-06-01T10:00:00Z", "hola")
        assert k1 != k2

    def test_timestamp_vacio_es_parte_del_hash(self):
        k1 = _idempotency_key("", "whatsapp:+1", "", "hola")
        k2 = _idempotency_key("", "whatsapp:+1", "2024-06-01", "hola")
        assert k1 != k2


# ── Deduplicación ─────────────────────────────────────────────────────────────


class TestDeduplicacion:
    def test_primer_mensaje_registra_en_processed_events(self, client_db):
        client, conn = client_db
        form = _twilio_form(message_sid="SM_uniq_001")
        client.post("/webhook", data=form)

        row = conn.execute(
            "SELECT idempotency_key FROM processed_events WHERE idempotency_key = ?",
            ("SM_uniq_001",),
        ).fetchone()
        assert row is not None
        assert row[0] == "SM_uniq_001"

    def test_mensaje_duplicado_retorna_200(self, client_db):
        client, _ = client_db
        form = _twilio_form(message_sid="SM_dup_001")
        client.post("/webhook", data=form)
        response = client.post("/webhook", data=form)
        assert response.status_code == 200

    def test_mensaje_duplicado_retorna_status_duplicate(self, client_db):
        client, _ = client_db
        form = _twilio_form(message_sid="SM_dup_002")
        client.post("/webhook", data=form)
        response = client.post("/webhook", data=form)
        assert response.json()["status"] == "duplicate"

    def test_duplicado_no_inserta_segunda_fila(self, client_db):
        client, conn = client_db
        form = _twilio_form(message_sid="SM_dup_003")
        client.post("/webhook", data=form)
        client.post("/webhook", data=form)

        count = conn.execute(
            "SELECT COUNT(*) FROM processed_events WHERE idempotency_key = ?",
            ("SM_dup_003",),
        ).fetchone()[0]
        assert count == 1

    def test_mensajes_distintos_se_procesan_independientemente(self, client_db):
        client, conn = client_db
        client.post("/webhook", data=_twilio_form(message_sid="SM_a"))
        client.post("/webhook", data=_twilio_form(message_sid="SM_b"))

        count = conn.execute("SELECT COUNT(*) FROM processed_events").fetchone()[0]
        assert count == 2

    def test_fallback_hash_detecta_duplicado_mismo_remitente_timestamp_body(self, client_db):
        """Sin MessageSid, mismo remitente + timestamp + body es duplicado."""
        client, _ = client_db
        form = {
            "From": "whatsapp:+59899000000",
            "Body": "mismo mensaje",
            "DateCreated": "2024-06-01T10:00:00Z",
        }
        client.post("/webhook", data=form)
        response = client.post("/webhook", data=form)
        assert response.json()["status"] == "duplicate"

    def test_fallback_hash_distinto_body_no_es_duplicado(self, client_db):
        client, _ = client_db
        client.post("/webhook", data={
            "From": "whatsapp:+1", "Body": "mensaje A", "DateCreated": "2024-06-01T10:00:00Z"
        })
        response = client.post("/webhook", data={
            "From": "whatsapp:+1", "Body": "mensaje B", "DateCreated": "2024-06-01T10:00:00Z"
        })
        assert response.json()["status"] == "ok"

    def test_fallback_hash_distinto_timestamp_no_es_duplicado(self, client_db):
        """Mismo remitente + body pero diferente timestamp → no es duplicado."""
        client, _ = client_db
        client.post("/webhook", data={
            "From": "whatsapp:+1", "Body": "hola", "DateCreated": "2024-06-01T10:00:00Z"
        })
        response = client.post("/webhook", data={
            "From": "whatsapp:+1", "Body": "hola", "DateCreated": "2024-06-01T11:00:00Z"
        })
        assert response.json()["status"] == "ok"

    def test_multiples_envios_duplicados_retornan_siempre_200(self, client_db):
        client, _ = client_db
        form = _twilio_form(message_sid="SM_multi")
        for _ in range(5):
            response = client.post("/webhook", data=form)
            assert response.status_code == 200
