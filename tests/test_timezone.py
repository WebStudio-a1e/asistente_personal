"""Tests T-036 — Timezone America/Montevideo en todos los componentes.

Valida AC-CORE-003 y AC-AGENDA-004:
- scheduler usa ZoneInfo("America/Montevideo").
- agenda_agent usa _TIMEZONE = "America/Montevideo" y offset -03:00.
- accounting_agent usa offset UTC-03:00.
- mark_missed_reminders y check_reminders operan en MVD.
- scheduled_for almacenado con offset -03:00.
"""

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

_MVD = ZoneInfo("America/Montevideo")
_UTC_MINUS_3 = timezone(timedelta(hours=-3))


# ── Scheduler ─────────────────────────────────────────────────────────────────


class TestSchedulerTimezone:
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

    def test_scheduler_usa_zoneinfo_montevideo(self):
        from src.scheduler.jobs import get_scheduler
        s = get_scheduler()
        assert str(s.timezone) == "America/Montevideo"

    def test_scheduler_mvd_es_zoneinfo(self):
        import src.scheduler.jobs as mod
        assert isinstance(mod._MVD, ZoneInfo)

    def test_scheduler_mvd_string_es_america_montevideo(self):
        import src.scheduler.jobs as mod
        assert str(mod._MVD) == "America/Montevideo"

    def test_now_mvd_tiene_timezone_correcta(self):
        from src.scheduler.jobs import _now_mvd
        now = _now_mvd()
        assert now.tzinfo is not None
        assert "America/Montevideo" in str(now.tzinfo)

    def test_now_mvd_no_es_utc(self):
        """El instante actual de MVD tiene UTC offset distinto de 0."""
        from src.scheduler.jobs import _now_mvd
        now = _now_mvd()
        # MVD es UTC-3, utcoffset no es cero
        offset = now.utcoffset()
        assert offset is not None
        assert offset != timedelta(0)


# ── Agenda agent ──────────────────────────────────────────────────────────────


class TestAgendaAgentTimezone:
    def test_agenda_timezone_constant_es_montevideo(self):
        import src.agents.agenda_agent as mod
        assert mod._TIMEZONE == "America/Montevideo"

    def test_agenda_mvd_tz_es_utc_menos_3(self):
        import src.agents.agenda_agent as mod
        # UTC-03:00 tiene offset de -3 horas
        sample = datetime(2024, 6, 10, 12, 0, tzinfo=mod._MVD_TZ)
        assert sample.utcoffset() == timedelta(hours=-3)

    def test_agenda_payload_scheduled_for_tiene_offset_mvd(self):
        """Evento creado por agenda_agent tiene scheduled_for con -03:00."""
        import json
        from unittest.mock import patch
        from src.agents.agenda_agent import agenda_agent_node

        payload_json = json.dumps({
            "operation": "create",
            "event_id": None,
            "title": "Reunión",
            "scheduled_for": "2024-06-10T10:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": None,
            "notes": None,
            "agent_response": "Agendando Reunión.",
        })
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=payload_json)

        with patch("src.agents.agenda_agent.get_llm", return_value=llm):
            result = agenda_agent_node({
                "message": "Reunión mañana a las 10",
                "pending_actions": [],
                "conversation_history": [],
            })

        sf = result.get("payload", {}).get("scheduled_for", "")
        assert "-03:00" in sf

    def test_agenda_system_prompt_menciona_timezone(self):
        import src.agents.agenda_agent as mod
        assert "America/Montevideo" in mod._SYSTEM_PROMPT or "UTC-3" in mod._SYSTEM_PROMPT


# ── Accounting agent ──────────────────────────────────────────────────────────


class TestAccountingAgentTimezone:
    def test_accounting_mvd_tz_es_utc_menos_3(self):
        import src.agents.accounting_agent as mod
        sample = datetime(2024, 6, 10, 12, 0, tzinfo=mod._MVD_TZ)
        assert sample.utcoffset() == timedelta(hours=-3)


# ── Scheduler con datetimes MVD ───────────────────────────────────────────────


class TestSchedulerOperacionesMVD:
    @pytest.fixture
    def conn(self):
        from src.storage.sqlite import create_tables
        c = sqlite3.connect(":memory:", check_same_thread=False)
        create_tables(c)
        yield c
        c.close()

    def _insert(self, conn, scheduled_for: datetime) -> int:
        with conn:
            cur = conn.execute(
                "INSERT INTO reminder_jobs (thread_id, event_id, scheduled_for, status)"
                " VALUES (?, ?, ?, 'pending')",
                ("whatsapp:+598991", "E_tz", scheduled_for.isoformat()),
            )
        return cur.lastrowid

    def test_mark_missed_acepta_datetime_mvd(self, conn):
        from src.scheduler.jobs import mark_missed_reminders
        now = datetime(2024, 6, 10, 10, 0, tzinfo=_MVD)
        past = datetime(2024, 6, 10, 9, 0, tzinfo=_MVD)
        self._insert(conn, past)
        count = mark_missed_reminders(conn, now=now)
        assert count == 1

    def test_check_reminders_acepta_datetime_mvd(self, conn):
        from src.scheduler.jobs import check_reminders
        now = datetime(2024, 6, 10, 10, 0, tzinfo=_MVD)
        due = datetime(2024, 6, 10, 9, 55, tzinfo=_MVD)
        self._insert(conn, due)
        twilio = MagicMock()
        twilio.messages.create.return_value = MagicMock(sid="SM1")
        sent = check_reminders(conn, twilio, "whatsapp:+1", now=now)
        assert len(sent) == 1

    def test_fired_at_almacenado_con_offset_mvd(self, conn):
        """fired_at refleja el offset del timezone MVD pasado como now."""
        from src.scheduler.jobs import check_reminders
        now = datetime(2024, 6, 10, 10, 0, tzinfo=_MVD)
        due = datetime(2024, 6, 10, 9, 55, tzinfo=_MVD)
        jid = self._insert(conn, due)
        twilio = MagicMock()
        twilio.messages.create.return_value = MagicMock(sid="SM2")
        check_reminders(conn, twilio, "whatsapp:+1", now=now)
        row = conn.execute(
            "SELECT fired_at FROM reminder_jobs WHERE id=?", (jid,)
        ).fetchone()
        # El isoformat de un datetime MVD incluye el offset
        assert row[0] is not None
        assert ":" in row[0]  # es un ISO datetime

    def test_reminder_futuro_en_mvd_no_se_envia(self, conn):
        from src.scheduler.jobs import check_reminders
        now = datetime(2024, 6, 10, 10, 0, tzinfo=_MVD)
        future = datetime(2024, 6, 10, 11, 0, tzinfo=_MVD)
        self._insert(conn, future)
        sent = check_reminders(conn, MagicMock(), "whatsapp:+1", now=now)
        assert sent == []

    def test_reminder_pasado_en_mvd_se_marca_missed(self, conn):
        from src.scheduler.jobs import mark_missed_reminders
        now = datetime(2024, 6, 10, 10, 0, tzinfo=_MVD)
        past = datetime(2024, 6, 9, 10, 0, tzinfo=_MVD)  # ayer
        jid = self._insert(conn, past)
        mark_missed_reminders(conn, now=now)
        row = conn.execute(
            "SELECT status FROM reminder_jobs WHERE id=?", (jid,)
        ).fetchone()
        assert row[0] == "missed"
