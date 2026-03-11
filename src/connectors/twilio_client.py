"""Connector para Twilio — envío de mensajes WhatsApp.

Configurable desde variables de entorno:
    TWILIO_ACCOUNT_SID       — SID de la cuenta Twilio
    TWILIO_AUTH_TOKEN        — token de autenticación
    TWILIO_WHATSAPP_NUMBER   — número remitente (ej. whatsapp:+14155238886)
    TWILIO_WHATSAPP_TO       — número destinatario por defecto (ej. whatsapp:+598...)

Sin llamadas reales en tests — inyección de cliente para mockeo.
"""

import logging
import os

from twilio.rest import Client

logger = logging.getLogger(__name__)


# ── Factory ───────────────────────────────────────────────────


def get_twilio_client(
    account_sid: str | None = None,
    auth_token: str | None = None,
) -> Client:
    """Devuelve un cliente Twilio configurado desde env vars o parámetros.

    Args:
        account_sid: SID de cuenta. Si None, usa TWILIO_ACCOUNT_SID.
        auth_token:  Token de auth. Si None, usa TWILIO_AUTH_TOKEN.

    Raises:
        ValueError: si account_sid o auth_token están ausentes.
    """
    sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID", "")
    token = auth_token or os.getenv("TWILIO_AUTH_TOKEN", "")

    if not sid or not sid.strip():
        raise ValueError("TWILIO_ACCOUNT_SID no configurado")
    if not token or not token.strip():
        raise ValueError("TWILIO_AUTH_TOKEN no configurado")

    return Client(sid, token)


# ── Envío ─────────────────────────────────────────────────────


def send_whatsapp_message(
    client: Client,
    body: str,
    to: str | None = None,
    from_: str | None = None,
) -> str:
    """Envía un mensaje WhatsApp mediante Twilio.

    Args:
        client: cliente Twilio (inyectado para facilitar mockeo en tests).
        body:   texto del mensaje.
        to:     número destinatario con prefijo whatsapp:. Si None, usa
                TWILIO_WHATSAPP_TO.
        from_:  número remitente con prefijo whatsapp:. Si None, usa
                TWILIO_WHATSAPP_NUMBER.

    Returns:
        SID del mensaje enviado.

    Raises:
        ValueError: si to o from_ están ausentes.
    """
    to_number = to or os.getenv("TWILIO_WHATSAPP_TO", "")
    from_number = from_ or os.getenv("TWILIO_WHATSAPP_NUMBER", "")

    if not to_number:
        raise ValueError("Número destinatario no configurado (TWILIO_WHATSAPP_TO)")
    if not from_number:
        raise ValueError("Número remitente no configurado (TWILIO_WHATSAPP_NUMBER)")

    message = client.messages.create(
        body=body,
        from_=from_number,
        to=to_number,
    )
    logger.info("send_whatsapp_message: mensaje enviado — sid=%s to=%s", message.sid, to_number)
    return message.sid
