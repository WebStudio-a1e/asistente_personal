"""Tests T-037 — Smoke tests de conectores reales.

Valida que cada conector se inicializa y responde con las credenciales
reales del entorno. Todas las operaciones son de solo lectura.

Variables requeridas (cargadas desde .env):
    GOOGLE_CREDENTIALS_PATH     — ruta al JSON de service account
    GOOGLE_SHEETS_TASKS_ID      — ID del spreadsheet de tareas
    GOOGLE_SHEETS_ACCOUNTING_ID — ID del spreadsheet de contabilidad
    GOOGLE_DOCS_IDEAS_ID        — ID del documento de ideas
    GOOGLE_CALENDAR_ID          — ID del calendario (ej. email)
    TWILIO_ACCOUNT_SID          — SID de cuenta Twilio
    TWILIO_AUTH_TOKEN           — token de autenticación Twilio
    TWILIO_WHATSAPP_NUMBER      — número remitente WhatsApp
"""

import os

_SHEETS_TASKS_ID = os.getenv("GOOGLE_SHEETS_TASKS_ID", "")
_SHEETS_ACCOUNTING_ID = os.getenv("GOOGLE_SHEETS_ACCOUNTING_ID", "")
_DOCS_IDEAS_ID = os.getenv("GOOGLE_DOCS_IDEAS_ID", "")
_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "")
_TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
_TWILIO_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")


# ── Google Sheets — Tasks ─────────────────────────────────────────────────────


class TestSheetsTasksSmoke:
    """Smoke: service account autentica y lee Google Sheets (tareas)."""

    def test_sheets_client_inicializa(self):
        from src.connectors.google_auth import get_sheets_client

        client = get_sheets_client()
        assert client is not None

    def test_read_tasks_retorna_lista(self):
        from src.connectors.google_auth import get_sheets_client
        from src.connectors.sheets_tasks import read_tasks

        client = get_sheets_client()
        tasks = read_tasks(client, _SHEETS_TASKS_ID)
        assert isinstance(tasks, list)

    def test_read_tasks_status_canonico(self):
        """Cada tarea tiene status dentro del conjunto kanban canónico."""
        from src.connectors.google_auth import get_sheets_client
        from src.connectors.sheets_tasks import VALID_STATUSES, read_tasks

        client = get_sheets_client()
        tasks = read_tasks(client, _SHEETS_TASKS_ID)
        for task in tasks:
            assert task.get("status") in VALID_STATUSES


# ── Google Sheets — Accounting ────────────────────────────────────────────────


class TestSheetsAccountingSmoke:
    """Smoke: service account autentica y lee Google Sheets (contabilidad)."""

    def test_read_entries_retorna_lista(self):
        from src.connectors.google_auth import get_sheets_client
        from src.connectors.sheets_accounting import read_entries

        client = get_sheets_client()
        entries = read_entries(client, _SHEETS_ACCOUNTING_ID)
        assert isinstance(entries, list)

    def test_read_entries_tipo_canonico(self):
        """Cada movimiento tiene tipo dentro del conjunto canónico."""
        from src.connectors.google_auth import get_sheets_client
        from src.connectors.sheets_accounting import VALID_TYPES, read_entries

        client = get_sheets_client()
        entries = read_entries(client, _SHEETS_ACCOUNTING_ID)
        for entry in entries:
            assert entry.get("type") in VALID_TYPES


# ── Google Docs — Ideas ───────────────────────────────────────────────────────


class TestDocsIdeasSmoke:
    """Smoke: service account autentica y lee Google Docs (ideas)."""

    def test_docs_service_inicializa(self):
        from src.connectors.google_auth import get_docs_service

        service = get_docs_service()
        assert service is not None

    def test_read_ideas_retorna_lista(self):
        from src.connectors.docs_ideas import read_ideas
        from src.connectors.google_auth import get_docs_service

        service = get_docs_service()
        ideas = read_ideas(service, _DOCS_IDEAS_ID)
        assert isinstance(ideas, list)

    def test_read_ideas_campos_presentes(self):
        """Cada idea tiene al menos id y theme o summary."""
        from src.connectors.docs_ideas import read_ideas
        from src.connectors.google_auth import get_docs_service

        service = get_docs_service()
        ideas = read_ideas(service, _DOCS_IDEAS_ID)
        for idea in ideas:
            assert "id" in idea
            assert "theme" in idea or "summary" in idea


# ── Google Calendar ───────────────────────────────────────────────────────────


class TestGoogleCalendarSmoke:
    """Smoke: service account autentica y lee Google Calendar."""

    def test_calendar_service_inicializa(self):
        from src.connectors.google_auth import get_calendar_service

        service = get_calendar_service()
        assert service is not None

    def test_read_events_retorna_lista(self):
        from src.connectors.calendar_client import read_events
        from src.connectors.google_auth import get_calendar_service

        service = get_calendar_service()
        events = read_events(service, _CALENDAR_ID)
        assert isinstance(events, list)

    def test_read_events_status_canonico(self):
        """Cada evento tiene status dentro del conjunto canónico."""
        from src.connectors.calendar_client import VALID_STATUSES, read_events
        from src.connectors.google_auth import get_calendar_service

        service = get_calendar_service()
        events = read_events(service, _CALENDAR_ID)
        for event in events:
            assert event.get("status") in VALID_STATUSES


# ── Twilio ────────────────────────────────────────────────────────────────────


class TestTwilioSmoke:
    """Smoke: cliente Twilio se inicializa con credenciales reales.

    No envía mensajes. Verifica que el cliente instancia correctamente
    con las variables de entorno configuradas.
    """

    def test_twilio_client_inicializa(self):
        from src.connectors.twilio_client import get_twilio_client

        client = get_twilio_client()
        assert client is not None

    def test_twilio_account_sid_coincide(self):
        """El account_sid del cliente coincide con TWILIO_ACCOUNT_SID del entorno."""
        from src.connectors.twilio_client import get_twilio_client

        client = get_twilio_client()
        assert client.account_sid == _TWILIO_SID

    def test_twilio_whatsapp_number_tiene_prefijo(self):
        """TWILIO_WHATSAPP_NUMBER tiene el prefijo 'whatsapp:'."""
        assert _TWILIO_NUMBER.startswith("whatsapp:")
