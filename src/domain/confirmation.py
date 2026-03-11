"""Confirmación — estado, señales y timeout.

ConfirmationStatus: alineado con state_machine.yaml.
normalize_signal:   clasifica la respuesta del usuario.
is_expired:         verifica timeout de 30 minutos.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


# ── Estado de confirmación ────────────────────────────────────────────────────

class ConfirmationStatus(str, Enum):
    DETECTED              = "detected"
    PROPOSED              = "proposed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    CONFIRMED             = "confirmed"
    REJECTED              = "rejected"
    PERSISTED             = "persisted"
    FAILED                = "failed"
    EXPIRED               = "expired"


# ── Señales reconocidas (state_machine.yaml §confirmation_signals) ────────────

class SignalType(str, Enum):
    POSITIVE  = "positive"
    NEGATIVE  = "negative"
    AMBIGUOUS = "ambiguous"
    UNKNOWN   = "unknown"


_POSITIVE: frozenset[str] = frozenset([
    "sí", "si", "ok", "dale", "hacelo", "confirmo",
    "correcto", "exacto", "perfecto", "adelante", "sí eso",
])

_NEGATIVE: frozenset[str] = frozenset([
    "no", "cancelá", "cancela", "rechazo", "no confirmo",
    "no era eso", "eso no", "para", "stop",
])

_AMBIGUOUS: frozenset[str] = frozenset([
    "mmm", "puede ser", "creo que sí", "después",
    "más o menos", "tal vez", "no sé",
])


def normalize_signal(text: str) -> SignalType:
    """Clasifica la respuesta del usuario como positiva, negativa, ambigua o desconocida."""
    normalized = text.lower().strip()
    if normalized in _POSITIVE:
        return SignalType.POSITIVE
    if normalized in _NEGATIVE:
        return SignalType.NEGATIVE
    if normalized in _AMBIGUOUS:
        return SignalType.AMBIGUOUS
    return SignalType.UNKNOWN


# ── Timeout ───────────────────────────────────────────────────────────────────

CONFIRMATION_TIMEOUT_MINUTES = 30


def is_expired(proposal_sent_at: datetime, now: Optional[datetime] = None) -> bool:
    """Retorna True si han pasado más de 30 minutos desde proposal_sent_at."""
    if now is None:
        now = datetime.now(tz=proposal_sent_at.tzinfo)
    return (now - proposal_sent_at) > timedelta(minutes=CONFIRMATION_TIMEOUT_MINUTES)
