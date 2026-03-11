"""Tests T-035 — Job de revisión de recordatorios.

Verifica:
- mark_missed_reminders marca 'missed' recordatorios pendientes vencidos.
- check_reminders envía recordatorios due y los marca 'sent'.
- check_reminders ignora recordatorios futuros.
- check_reminders ignora recordatorios ya procesados (sent/missed).
- Errores en Twilio no propagan excepción (el job sigue).
- register_reminder_job registra el job con intervalo de 15 minutos.
- El job usa timezone America/Montevideo.
"""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.scheduler.jobs import (
    check_reminders,
    mark_missed_reminders,
)
from src.storage.sqlite import create_tables

_MVD = ZoneInfo("America/Montevideo")


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def conn():
    """Conexión SQLite en memoria con tablas operativas creadas."""
    c = sqlite3.connect(":memory:", check_same_thread=False)
    create_tables(c)
    yield c
    c.close()


@pytest.fixture
def mock_twilio():
    client = MagicMock()
    client.messages.create.return_value = MagicMock(sid="SMtest123")
    return client


def _now() -> datetime:
    return datetime.now(tz=_MVD)


def _insert_reminder(
    conn: sqlite3.Connection,
    thread_id: str,
    event_id: str,
    scheduled_for: datetime,
    status: str = "pending",
) -> int:
    """Inserta un reminder_job y retorna su id."""
    with conn:
        cursor = conn.execute(
            "INSERT INTO reminder_jobs (thread_id, event_id, scheduled_for, status)"
            " VALUES (?, ?, ?, ?)",
            (thread_id, event_id, scheduled_for.isoformat(), status),
        )
    return cursor.lastrowid


def _status(conn: sqlite3.Connection, job_id: int) -> str:
    row = conn.execute(
        "SELECT status FROM reminder_jobs WHERE id=?", (job_id,)
    ).fetchone()
    return row[0] if row else ""


# ── mark_missed_reminders ─────────────────────────────────────────────────────


class TestMarkMissedReminders:
    def test_marca_pending_pasado_como_missed(self, conn):
        now = _now()
        past = now - timedelta(hours=1)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E1", past)
        count = mark_missed_reminders(conn, now=now)
        assert count == 1
        assert _status(conn, jid) == "missed"

    def test_no_marca_pending_futuro(self, conn):
        now = _now()
        future = now + timedelta(minutes=5)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E2", future)
        count = mark_missed_reminders(conn, now=now)
        assert count == 0
        assert _status(conn, jid) == "pending"

    def test_no_toca_recordatorios_ya_sent(self, conn):
        now = _now()
        past = now - timedelta(hours=2)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E3", past, status="sent")
        mark_missed_reminders(conn, now=now)
        assert _status(conn, jid) == "sent"

    def test_no_toca_recordatorios_ya_missed(self, conn):
        now = _now()
        past = now - timedelta(hours=3)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E4", past, status="missed")
        mark_missed_reminders(conn, now=now)
        assert _status(conn, jid) == "missed"

    def test_exactamente_igual_a_now_no_es_missed(self, conn):
        """scheduled_for == now: NO se marca missed (< estricto)."""
        now = _now()
        jid = _insert_reminder(conn, "whatsapp:+598991", "E5", now)
        mark_missed_reminders(conn, now=now)
        assert _status(conn, jid) == "pending"

    def test_multiples_pendientes_pasados(self, conn):
        now = _now()
        past = now - timedelta(minutes=30)
        ids = [
            _insert_reminder(conn, f"whatsapp:+5989{i}", f"E{i}", past)
            for i in range(3)
        ]
        count = mark_missed_reminders(conn, now=now)
        assert count == 3
        for jid in ids:
            assert _status(conn, jid) == "missed"

    def test_retorna_cero_sin_pendientes(self, conn):
        now = _now()
        count = mark_missed_reminders(conn, now=now)
        assert count == 0

    def test_usa_now_mvd_por_defecto(self, conn):
        """Sin pasar now, usa datetime actual en MVD — no lanza excepción."""
        mark_missed_reminders(conn)  # no debe lanzar


# ── check_reminders ───────────────────────────────────────────────────────────


class TestCheckReminders:
    FROM = "whatsapp:+14155238886"

    def test_envia_recordatorio_due(self, conn, mock_twilio):
        now = _now()
        due = now - timedelta(seconds=30)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E10", due)
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert jid in sent
        assert _status(conn, jid) == "sent"

    def test_no_envia_recordatorio_futuro(self, conn, mock_twilio):
        now = _now()
        future = now + timedelta(minutes=5)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E11", future)
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert jid not in sent
        assert _status(conn, jid) == "pending"

    def test_no_reenvia_recordatorio_ya_sent(self, conn, mock_twilio):
        now = _now()
        past = now - timedelta(minutes=10)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E12", past, status="sent")
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert jid not in sent

    def test_no_reenvia_recordatorio_missed(self, conn, mock_twilio):
        now = _now()
        past = now - timedelta(minutes=20)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E13", past, status="missed")
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert jid not in sent

    def test_setea_fired_at(self, conn, mock_twilio):
        now = _now()
        due = now - timedelta(seconds=10)
        jid = _insert_reminder(conn, "whatsapp:+598991", "E14", due)
        check_reminders(conn, mock_twilio, self.FROM, now=now)
        row = conn.execute(
            "SELECT fired_at FROM reminder_jobs WHERE id=?", (jid,)
        ).fetchone()
        assert row[0] is not None

    def test_mensaje_contiene_event_id(self, conn, mock_twilio):
        now = _now()
        due = now - timedelta(seconds=5)
        _insert_reminder(conn, "whatsapp:+598991", "E_reunion", due)
        check_reminders(conn, mock_twilio, self.FROM, now=now)
        call_body = mock_twilio.messages.create.call_args.kwargs["body"]
        assert "E_reunion" in call_body

    def test_envia_al_thread_id_correcto(self, conn, mock_twilio):
        now = _now()
        due = now - timedelta(seconds=5)
        _insert_reminder(conn, "whatsapp:+59899999999", "E15", due)
        check_reminders(conn, mock_twilio, self.FROM, now=now)
        call_to = mock_twilio.messages.create.call_args.kwargs["to"]
        assert call_to == "whatsapp:+59899999999"

    def test_error_twilio_no_propaga(self, conn, mock_twilio):
        """Un fallo en Twilio no debe detener el job."""
        mock_twilio.messages.create.side_effect = Exception("Twilio error")
        now = _now()
        due = now - timedelta(seconds=5)
        _insert_reminder(conn, "whatsapp:+598991", "E16", due)
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert sent == []  # no enviados pero sin excepción

    def test_multiples_due_todos_enviados(self, conn, mock_twilio):
        now = _now()
        due = now - timedelta(seconds=5)
        ids = [
            _insert_reminder(conn, f"whatsapp:+5989{i}", f"E{20 + i}", due)
            for i in range(3)
        ]
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert set(sent) == set(ids)
        for jid in ids:
            assert _status(conn, jid) == "sent"

    def test_retorna_lista_vacia_sin_due(self, conn, mock_twilio):
        now = _now()
        sent = check_reminders(conn, mock_twilio, self.FROM, now=now)
        assert sent == []

    def test_usa_now_mvd_por_defecto(self, conn, mock_twilio):
        """Sin pasar now, usa datetime actual en MVD — no lanza excepción."""
        check_reminders(conn, mock_twilio, self.FROM)


# ── register_reminder_job ─────────────────────────────────────────────────────


class TestRegisterReminderJob:
    def setup_method(self):
        import src.scheduler.jobs as mod
        if mod._scheduler is not None and mod._scheduler.running:
            mod._scheduler.shutdown(wait=False)
        mod._scheduler = None

    def teardown_method(self):
        import src.scheduler.jobs as mod
        if mod._scheduler is not None and mod._scheduler.running:
            mod._scheduler.shutdown(wait=False)
        mod._scheduler = None

    def test_registra_job_en_scheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.scheduler.jobs import register_reminder_job
        scheduler = BackgroundScheduler(timezone="America/Montevideo")
        scheduler.start()
        try:
            register_reminder_job(scheduler, ":memory:", MagicMock(), "whatsapp:+1")
            job_ids = [j.id for j in scheduler.get_jobs()]
            assert "check_reminders" in job_ids
        finally:
            scheduler.shutdown(wait=False)

    def test_job_intervalo_15_minutos(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.scheduler.jobs import register_reminder_job
        scheduler = BackgroundScheduler(timezone="America/Montevideo")
        scheduler.start()
        try:
            register_reminder_job(scheduler, ":memory:", MagicMock(), "whatsapp:+1")
            job = scheduler.get_job("check_reminders")
            assert job.trigger.interval.seconds == 15 * 60
        finally:
            scheduler.shutdown(wait=False)

    def test_register_es_idempotente(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.scheduler.jobs import register_reminder_job
        scheduler = BackgroundScheduler(timezone="America/Montevideo")
        scheduler.start()
        try:
            register_reminder_job(scheduler, ":memory:", MagicMock(), "whatsapp:+1")
            register_reminder_job(scheduler, ":memory:", MagicMock(), "whatsapp:+1")
            jobs = [j for j in scheduler.get_jobs() if j.id == "check_reminders"]
            assert len(jobs) == 1
        finally:
            scheduler.shutdown(wait=False)
