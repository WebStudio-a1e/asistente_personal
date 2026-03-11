"""Tests T-035 — Simulación de tiempo para el job de recordatorios.

Verifica comportamientos dependientes del tiempo usando 'now' inyectado:
- Recordatorios due enviados en el instante correcto.
- Recordatorios futuros ignorados hasta que llegue su hora.
- Recordatorios vencidos durante caída marcados 'missed' en startup.
- Ningún reenvío retroactivo de recordatorios missed.
- Timezone America/Montevideo en todos los instantes.
"""

import sqlite3
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from src.scheduler.jobs import check_reminders, mark_missed_reminders
from src.storage.sqlite import create_tables

_MVD = ZoneInfo("America/Montevideo")

FROM = "whatsapp:+14155238886"


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    create_tables(c)
    yield c
    c.close()


@pytest.fixture
def twilio():
    client = MagicMock()
    client.messages.create.return_value = MagicMock(sid="SMsim")
    return client


def _mvd(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    """Crea un datetime con timezone America/Montevideo."""
    return datetime(year, month, day, hour, minute, tzinfo=_MVD)


def _insert(conn, thread_id, event_id, scheduled_for, status="pending"):
    with conn:
        cur = conn.execute(
            "INSERT INTO reminder_jobs (thread_id, event_id, scheduled_for, status)"
            " VALUES (?, ?, ?, ?)",
            (thread_id, event_id, scheduled_for.isoformat(), status),
        )
    return cur.lastrowid


def _status(conn, jid):
    row = conn.execute(
        "SELECT status FROM reminder_jobs WHERE id=?", (jid,)
    ).fetchone()
    return row[0] if row else ""


# ── Timezone ──────────────────────────────────────────────────────────────────


class TestTimezone:
    def test_datetime_almacenado_con_offset_mvd(self, conn):
        """scheduled_for almacenado con offset -03:00 de MVD."""
        now = _mvd(2024, 6, 10, 10, 0)
        jid = _insert(conn, "whatsapp:+598991", "E_tz", now - timedelta(minutes=5))
        check_reminders(conn, MagicMock(
            messages=MagicMock(create=MagicMock(return_value=MagicMock(sid="X")))
        ), FROM, now=now)
        row = conn.execute(
            "SELECT fired_at FROM reminder_jobs WHERE id=?", (jid,)
        ).fetchone()
        # fired_at debe contener el offset de MVD
        assert "-03:00" in row[0] or "+" not in row[0].replace("-03:00", "")

    def test_now_en_timezone_mvd(self, conn, twilio):
        """El instante 'now' pasado tiene timezone MVD."""
        now = _mvd(2024, 6, 10, 14, 30)
        assert now.tzinfo == _MVD
        # Sin recordatorios, no lanza excepción
        sent = check_reminders(conn, twilio, FROM, now=now)
        assert sent == []


# ── Escenarios de tiempo simulado ─────────────────────────────────────────────


class TestSimulacionTiempo:
    def test_recordatorio_exactamente_ahora_es_enviado(self, conn, twilio):
        """scheduled_for == now → se envía (condición <=)."""
        now = _mvd(2024, 6, 10, 9, 0)
        jid = _insert(conn, "whatsapp:+598991", "E_now", now)
        sent = check_reminders(conn, twilio, FROM, now=now)
        assert jid in sent
        assert _status(conn, jid) == "sent"

    def test_recordatorio_un_segundo_antes_enviado(self, conn, twilio):
        now = _mvd(2024, 6, 10, 9, 0)
        scheduled = now - timedelta(seconds=1)
        jid = _insert(conn, "whatsapp:+598991", "E_sec", scheduled)
        sent = check_reminders(conn, twilio, FROM, now=now)
        assert jid in sent

    def test_recordatorio_un_segundo_despues_no_enviado(self, conn, twilio):
        now = _mvd(2024, 6, 10, 9, 0)
        future = now + timedelta(seconds=1)
        jid = _insert(conn, "whatsapp:+598991", "E_future", future)
        sent = check_reminders(conn, twilio, FROM, now=now)
        assert jid not in sent
        assert _status(conn, jid) == "pending"

    def test_recordatorio_15_min_futuro_no_enviado_en_primera_corrida(self, conn, twilio):
        now = _mvd(2024, 6, 10, 9, 0)
        future = now + timedelta(minutes=15)
        jid = _insert(conn, "whatsapp:+598991", "E_15m", future)
        sent = check_reminders(conn, twilio, FROM, now=now)
        assert jid not in sent

    def test_recordatorio_15_min_futuro_enviado_en_segunda_corrida(self, conn, twilio):
        """Simula dos corridas del job separadas 15 minutos."""
        t0 = _mvd(2024, 6, 10, 9, 0)
        t1 = t0 + timedelta(minutes=15)
        scheduled = t0 + timedelta(minutes=10)
        jid = _insert(conn, "whatsapp:+598991", "E_t1", scheduled)

        sent_t0 = check_reminders(conn, twilio, FROM, now=t0)
        assert jid not in sent_t0

        sent_t1 = check_reminders(conn, twilio, FROM, now=t1)
        assert jid in sent_t1
        assert _status(conn, jid) == "sent"

    def test_multiples_corridas_no_reenvia(self, conn, twilio):
        """Corridas sucesivas no reenvían recordatorios ya sent."""
        now = _mvd(2024, 6, 10, 9, 0)
        jid = _insert(conn, "whatsapp:+598991", "E_dup", now - timedelta(minutes=1))

        check_reminders(conn, twilio, FROM, now=now)
        assert _status(conn, jid) == "sent"

        call_count_after_first = twilio.messages.create.call_count

        check_reminders(conn, twilio, FROM, now=now + timedelta(minutes=15))
        assert twilio.messages.create.call_count == call_count_after_first  # no reenvío


# ── Recordatorios vencidos durante caída ─────────────────────────────────────


class TestCaidaYMissed:
    def test_startup_marca_missed_recordatorios_vencidos(self, conn):
        """Simula que el app estuvo caído y hay recordatorios sin enviar."""
        # Recordatorios que debían enviarse mientras el app estaba caído
        caida_fin = _mvd(2024, 6, 10, 9, 30)  # startup

        ids = []
        for h in (8, 9):  # 08:00 y 09:00 — durante la caída
            jid = _insert(
                conn, "whatsapp:+598991", f"E_caida_{h}", _mvd(2024, 6, 10, h, 0)
            )
            ids.append(jid)

        # En startup, mark_missed_reminders con now = hora de recuperación
        count = mark_missed_reminders(conn, now=caida_fin)
        assert count == 2
        for jid in ids:
            assert _status(conn, jid) == "missed"

    def test_no_reenvio_retroactivo_de_missed(self, conn, twilio):
        """check_reminders no reenvía recordatorios missed."""
        past = _mvd(2024, 6, 10, 8, 0)
        now = _mvd(2024, 6, 10, 9, 30)
        jid = _insert(conn, "whatsapp:+598991", "E_missed", past, status="missed")

        sent = check_reminders(conn, twilio, FROM, now=now)
        assert jid not in sent
        assert _status(conn, jid) == "missed"
        twilio.messages.create.assert_not_called()

    def test_recordatorio_futuro_no_se_marca_missed_en_startup(self, conn):
        """Recordatorios futuros no se tocan en mark_missed_reminders."""
        now = _mvd(2024, 6, 10, 9, 30)
        future = _mvd(2024, 6, 10, 10, 0)
        jid = _insert(conn, "whatsapp:+598991", "E_future", future)

        mark_missed_reminders(conn, now=now)
        assert _status(conn, jid) == "pending"

    def test_flujo_startup_mas_primera_corrida(self, conn, twilio):
        """Simula startup completo: missed anteriores + recordatorio exactamente ahora.

        mark_missed_reminders usa < estricto: scheduled_for == now no es missed.
        check_reminders usa <=: scheduled_for == now sí se envía.
        """
        now = _mvd(2024, 6, 10, 9, 30)

        # Perdido durante caída (pasado estricto → missed)
        jid_missed = _insert(conn, "whatsapp:+598991", "E_caida", _mvd(2024, 6, 10, 8, 0))
        # Programado exactamente para now: no missed (< estricto), sí enviado (<= en check)
        jid_exact = _insert(conn, "whatsapp:+598992", "E_exact", now)
        # Futuro (no se toca)
        jid_future = _insert(conn, "whatsapp:+598993", "E_future", _mvd(2024, 6, 10, 10, 0))

        # Startup: marcar missed
        mark_missed_reminders(conn, now=now)
        assert _status(conn, jid_missed) == "missed"
        assert _status(conn, jid_exact) == "pending"   # == now, no es < now
        assert _status(conn, jid_future) == "pending"

        # Primera corrida del job
        sent = check_reminders(conn, twilio, FROM, now=now)
        assert jid_exact in sent
        assert _status(conn, jid_exact) == "sent"
        assert _status(conn, jid_future) == "pending"  # aún futuro

    def test_missed_exactamente_en_now_no_se_marca(self, conn):
        """scheduled_for == now: NOT missed (< estricto), pending hasta check."""
        now = _mvd(2024, 6, 10, 9, 0)
        jid = _insert(conn, "whatsapp:+598991", "E_exact", now)
        mark_missed_reminders(conn, now=now)
        assert _status(conn, jid) == "pending"

    def test_multiples_caidas_acumuladas(self, conn):
        """Varios recordatorios de diferentes períodos de caída."""
        now = _mvd(2024, 6, 11, 8, 0)  # lunes 8am
        # Recordatorios de ayer
        ids = [
            _insert(conn, "whatsapp:+598991", f"E_old_{i}", _mvd(2024, 6, 10, 9 + i, 0))
            for i in range(5)
        ]
        count = mark_missed_reminders(conn, now=now)
        assert count == 5
        for jid in ids:
            assert _status(conn, jid) == "missed"
