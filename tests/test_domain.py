"""Tests para src/domain/ — T-016."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


# ── Intent y Domain ───────────────────────────────────────────────────────────

def test_intent_valores():
    from src.domain.intents import Intent

    assert Intent.TASK       == "task"
    assert Intent.IDEA       == "idea"
    assert Intent.AGENDA     == "agenda"
    assert Intent.ACCOUNTING == "accounting"
    assert Intent.QUERY      == "query"
    assert Intent.UNKNOWN    == "unknown"


def test_intent_todos_los_valores():
    from src.domain.intents import Intent

    valores = {i.value for i in Intent}
    assert valores == {"task", "idea", "agenda", "accounting", "query", "unknown"}


def test_domain_valores():
    from src.domain.intents import Domain

    assert Domain.TASKS      == "tasks"
    assert Domain.IDEAS      == "ideas"
    assert Domain.AGENDA     == "agenda"
    assert Domain.ACCOUNTING == "accounting"
    assert Domain.REPORTING  == "reporting"
    assert Domain.UNKNOWN    == "unknown"


# ── Schemas Pydantic ──────────────────────────────────────────────────────────

def test_task_schema_valido():
    from src.domain.schemas import Task

    ahora = datetime.now(tz=timezone.utc)
    task = Task(
        id="t-001",
        title="Terminar informe",
        status="pending",
        created_at=ahora,
        updated_at=ahora,
    )
    assert task.id == "t-001"
    assert task.status == "pending"
    assert task.source == "whatsapp"
    assert task.notes is None


def test_task_status_invalido():
    from pydantic import ValidationError
    from src.domain.schemas import Task

    ahora = datetime.now(tz=timezone.utc)
    with pytest.raises(ValidationError):
        Task(id="t-001", title="X", status="borrador", created_at=ahora, updated_at=ahora)


def test_idea_schema_valida():
    from src.domain.schemas import Idea

    idea = Idea(
        id="i-001",
        raw_text="Usar LangGraph para el asistente",
        theme="tecnología",
        summary="Arquitectura multiagente",
        priority="high",
        created_at=datetime.now(tz=timezone.utc),
    )
    assert idea.priority == "high"
    assert idea.status == "active"
    assert idea.tags == []


def test_event_schema_valido():
    from src.domain.schemas import Event

    evento = Event(
        id="e-001",
        title="Reunión de equipo",
        scheduled_for=datetime.now(tz=timezone.utc),
    )
    assert evento.status == "active"
    assert evento.recurrence is None
    assert evento.source == "whatsapp"


def test_event_status_cancelled():
    from src.domain.schemas import Event

    evento = Event(
        id="e-002",
        title="Reunión cancelada",
        scheduled_for=datetime.now(tz=timezone.utc),
        status="cancelled",
    )
    assert evento.status == "cancelled"


def test_accounting_entry_schema_valido():
    from src.domain.schemas import AccountingEntry

    entry = AccountingEntry(
        id="a-001",
        date=datetime.now(tz=timezone.utc),
        type="expense",
        category="alimentación",
        amount=Decimal("1500.50"),
        note="supermercado",
    )
    assert entry.type == "expense"
    assert entry.amount == Decimal("1500.50")
    assert entry.correction_note is None
    assert entry.balance is None


def test_accounting_entry_con_correction_note():
    from src.domain.schemas import AccountingEntry

    entry = AccountingEntry(
        id="a-002",
        date=datetime.now(tz=timezone.utc),
        type="income",
        category="freelance",
        amount=Decimal("5000"),
        note="proyecto web",
        correction_note="monto corregido de 4500 a 5000",
    )
    assert entry.correction_note == "monto corregido de 4500 a 5000"


# ── ConfirmationStatus ────────────────────────────────────────────────────────

def test_confirmation_status_valores():
    from src.domain.confirmation import ConfirmationStatus

    assert ConfirmationStatus.DETECTED              == "detected"
    assert ConfirmationStatus.PROPOSED              == "proposed"
    assert ConfirmationStatus.AWAITING_CONFIRMATION == "awaiting_confirmation"
    assert ConfirmationStatus.CONFIRMED             == "confirmed"
    assert ConfirmationStatus.REJECTED              == "rejected"
    assert ConfirmationStatus.PERSISTED             == "persisted"
    assert ConfirmationStatus.FAILED                == "failed"
    assert ConfirmationStatus.EXPIRED               == "expired"


def test_confirmation_status_todos_los_valores():
    from src.domain.confirmation import ConfirmationStatus

    valores = {s.value for s in ConfirmationStatus}
    esperados = {
        "detected", "proposed", "awaiting_confirmation",
        "confirmed", "rejected", "persisted", "failed", "expired",
    }
    assert valores == esperados


# ── normalize_signal ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto", ["sí", "si", "ok", "dale", "hacelo", "confirmo",
                                    "correcto", "exacto", "perfecto", "adelante", "sí eso"])
def test_normalize_signal_positivos(texto):
    from src.domain.confirmation import normalize_signal, SignalType

    assert normalize_signal(texto) == SignalType.POSITIVE


@pytest.mark.parametrize("texto", ["no", "cancelá", "cancela", "rechazo",
                                    "no confirmo", "no era eso", "eso no", "para", "stop"])
def test_normalize_signal_negativos(texto):
    from src.domain.confirmation import normalize_signal, SignalType

    assert normalize_signal(texto) == SignalType.NEGATIVE


@pytest.mark.parametrize("texto", ["mmm", "puede ser", "creo que sí", "después",
                                    "más o menos", "tal vez", "no sé"])
def test_normalize_signal_ambiguos(texto):
    from src.domain.confirmation import normalize_signal, SignalType

    assert normalize_signal(texto) == SignalType.AMBIGUOUS


def test_normalize_signal_desconocido():
    from src.domain.confirmation import normalize_signal, SignalType

    assert normalize_signal("blah blah") == SignalType.UNKNOWN


def test_normalize_signal_case_insensitive():
    from src.domain.confirmation import normalize_signal, SignalType

    assert normalize_signal("OK") == SignalType.POSITIVE
    assert normalize_signal("NO") == SignalType.NEGATIVE
    assert normalize_signal("  sí  ") == SignalType.POSITIVE


# ── is_expired ────────────────────────────────────────────────────────────────

def test_is_expired_vencido():
    from src.domain.confirmation import is_expired

    hace_31_minutos = datetime.now(tz=timezone.utc) - timedelta(minutes=31)
    assert is_expired(hace_31_minutos) is True


def test_is_expired_no_vencido():
    from src.domain.confirmation import is_expired

    hace_5_minutos = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
    assert is_expired(hace_5_minutos) is False


def test_is_expired_exactamente_en_limite():
    from src.domain.confirmation import is_expired, CONFIRMATION_TIMEOUT_MINUTES

    assert CONFIRMATION_TIMEOUT_MINUTES == 30

    base     = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    justo_30 = datetime(2026, 3, 10, 12, 30, 0, tzinfo=timezone.utc)
    # 30 minutos exactos NO está expirado (> no >=)
    assert is_expired(base, now=justo_30) is False


def test_is_expired_con_now_explicito():
    from src.domain.confirmation import is_expired

    base = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)
    now_ok  = datetime(2026, 3, 10, 12, 25, 0, tzinfo=timezone.utc)
    now_exp = datetime(2026, 3, 10, 12, 31, 0, tzinfo=timezone.utc)

    assert is_expired(base, now=now_ok) is False
    assert is_expired(base, now=now_exp) is True
