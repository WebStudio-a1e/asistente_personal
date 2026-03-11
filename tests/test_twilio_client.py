"""Tests T-027 — twilio_client.

Sin llamadas reales a Twilio: Client y messages.create mockeados.
"""

from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_client(sid: str = "MSG123") -> MagicMock:
    """Cliente Twilio mock con messages.create que devuelve sid configurable."""
    client = MagicMock()
    client.messages.create.return_value = MagicMock(sid=sid)
    return client


# ── get_twilio_client ─────────────────────────────────────────────────────────


class TestGetTwilioClient:
    def test_retorna_client_con_credenciales_explicitas(self):
        from src.connectors.twilio_client import get_twilio_client

        with patch("src.connectors.twilio_client.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            result = get_twilio_client(account_sid="ACtest", auth_token="token123")

        mock_cls.assert_called_once_with("ACtest", "token123")
        assert result is not None

    def test_usa_env_vars_si_no_se_pasan_argumentos(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACenv")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tokenenv")

        from src.connectors.twilio_client import get_twilio_client

        with patch("src.connectors.twilio_client.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_twilio_client()

        mock_cls.assert_called_once_with("ACenv", "tokenenv")

    def test_lanza_error_si_account_sid_ausente(self, monkeypatch):
        monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)

        from src.connectors.twilio_client import get_twilio_client

        with pytest.raises(ValueError, match="TWILIO_ACCOUNT_SID"):
            get_twilio_client(auth_token="token")

    def test_lanza_error_si_auth_token_ausente(self, monkeypatch):
        monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)

        from src.connectors.twilio_client import get_twilio_client

        with pytest.raises(ValueError, match="TWILIO_AUTH_TOKEN"):
            get_twilio_client(account_sid="ACtest")

    def test_lanza_error_si_account_sid_vacio(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "")

        from src.connectors.twilio_client import get_twilio_client

        with pytest.raises(ValueError, match="TWILIO_ACCOUNT_SID"):
            get_twilio_client(auth_token="token")

    def test_lanza_error_si_auth_token_vacio(self, monkeypatch):
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")

        from src.connectors.twilio_client import get_twilio_client

        with pytest.raises(ValueError, match="TWILIO_AUTH_TOKEN"):
            get_twilio_client(account_sid="ACtest")

    def test_argumento_explicito_tiene_prioridad_sobre_env(self, monkeypatch):
        monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACenv")
        monkeypatch.setenv("TWILIO_AUTH_TOKEN", "tokenenv")

        from src.connectors.twilio_client import get_twilio_client

        with patch("src.connectors.twilio_client.Client") as mock_cls:
            mock_cls.return_value = MagicMock()
            get_twilio_client(account_sid="ACexplicit", auth_token="tokenexplicit")

        mock_cls.assert_called_once_with("ACexplicit", "tokenexplicit")


# ── send_whatsapp_message ─────────────────────────────────────────────────────


class TestSendWhatsappMessage:
    def test_retorna_sid_del_mensaje(self):
        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client(sid="SM_test_001")
        result = send_whatsapp_message(
            client,
            body="Hola!",
            to="whatsapp:+59899000000",
            from_="whatsapp:+14155238886",
        )
        assert result == "SM_test_001"

    def test_llama_messages_create_con_parametros_correctos(self):
        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client()
        send_whatsapp_message(
            client,
            body="Mensaje de prueba",
            to="whatsapp:+59899000000",
            from_="whatsapp:+14155238886",
        )
        client.messages.create.assert_called_once_with(
            body="Mensaje de prueba",
            from_="whatsapp:+14155238886",
            to="whatsapp:+59899000000",
        )

    def test_usa_env_vars_si_to_y_from_ausentes(self, monkeypatch):
        monkeypatch.setenv("TWILIO_WHATSAPP_TO", "whatsapp:+59899111111")
        monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client()
        send_whatsapp_message(client, body="Test")
        client.messages.create.assert_called_once_with(
            body="Test",
            from_="whatsapp:+14155238886",
            to="whatsapp:+59899111111",
        )

    def test_argumento_to_tiene_prioridad_sobre_env(self, monkeypatch):
        monkeypatch.setenv("TWILIO_WHATSAPP_TO", "whatsapp:+59899000000")

        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client()
        send_whatsapp_message(
            client,
            body="X",
            to="whatsapp:+59899999999",
            from_="whatsapp:+14155238886",
        )
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["to"] == "whatsapp:+59899999999"

    def test_argumento_from_tiene_prioridad_sobre_env(self, monkeypatch):
        monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")

        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client()
        send_whatsapp_message(
            client,
            body="X",
            to="whatsapp:+59899000000",
            from_="whatsapp:+19999999999",
        )
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["from_"] == "whatsapp:+19999999999"

    def test_lanza_error_si_to_ausente(self, monkeypatch):
        monkeypatch.delenv("TWILIO_WHATSAPP_TO", raising=False)

        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client()
        with pytest.raises(ValueError, match="destinatario"):
            send_whatsapp_message(client, body="X", from_="whatsapp:+14155238886")

    def test_lanza_error_si_from_ausente(self, monkeypatch):
        monkeypatch.delenv("TWILIO_WHATSAPP_NUMBER", raising=False)

        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client()
        with pytest.raises(ValueError, match="remitente"):
            send_whatsapp_message(client, body="X", to="whatsapp:+59899000000")

    def test_no_realiza_llamadas_reales_a_twilio(self):
        """Verificar que el mock intercepta todas las llamadas."""
        from src.connectors.twilio_client import send_whatsapp_message

        client = _mock_client(sid="MOCK_SID")
        result = send_whatsapp_message(
            client,
            body="sin red",
            to="whatsapp:+59899000000",
            from_="whatsapp:+14155238886",
        )
        # Si llegamos aquí sin excepción, no hubo llamada real
        assert result == "MOCK_SID"
        assert client.messages.create.called
