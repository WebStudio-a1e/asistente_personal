"""Tests T-026 — Integración agentes especializados.

Verifica que el pipeline agente → conector funciona correctamente por dominio.
Todas las llamadas a LLM y Google APIs están mockeadas.

Cobertura:
- tasks:      create, update_status, delete, read
- ideas:      create, delete, read
- agenda:     create, update, cancel, read
- accounting: create, update (con correction_note), read
- accounting: delete PROHIBIDO verificado
- accounting: correction_note obligatoria verificada
"""

import json
import sqlite3
from datetime import timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

_MVD_TZ = timezone(timedelta(hours=-3))


# ── Helpers comunes ───────────────────────────────────────────────────────────


def _mock_llm(payload: dict) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps(payload))
    return llm


def _audit_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE audit_logs "
        "(id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT, action TEXT, "
        "domain TEXT, payload TEXT, status TEXT, "
        "created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# DOMINIO: TASKS
# ══════════════════════════════════════════════════════════════════════════════


class TestTasksIntegracion:
    """tasks_agent_node → sheets_tasks — CRUD permitido."""

    def _ws(self, rows: list | None = None) -> MagicMock:
        ws = MagicMock()
        ws.get_all_values.return_value = rows or [
            ["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"]
        ]
        ws.find.return_value = None
        return ws

    def _client(self, ws: MagicMock) -> MagicMock:
        client = MagicMock()
        client.open_by_key.return_value.worksheet.return_value = ws
        return client

    # ── Create ────────────────────────────────────────────────

    def test_create_agente_produce_payload_y_conector_lo_escribe(self):
        from src.agents.tasks_agent import tasks_agent_node
        from src.connectors.sheets_tasks import write_task

        llm_data = {
            "operation": "create",
            "task_id": None,
            "title": "Preparar informe mensual",
            "status": "pending",
            "notes": None,
            "agent_response": "Creando tarea.",
        }
        ws = self._ws()

        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = tasks_agent_node({"message": "crea tarea informe mensual"})

        write_task(self._client(ws), "SHEET_ID", result["payload"])

        ws.append_row.assert_called_once()
        row = ws.append_row.call_args.args[0]
        assert row[1] == "Preparar informe mensual"
        assert row[2] == "Pendiente"

    # ── Read ──────────────────────────────────────────────────

    def test_read_agente_produce_payload_read_y_conector_lee(self):
        from src.agents.tasks_agent import tasks_agent_node
        from src.connectors.sheets_tasks import read_tasks

        llm_data = {
            "operation": "read",
            "task_id": None,
            "title": None,
            "status": None,
            "notes": None,
            "agent_response": "Listando tareas.",
        }
        ws = self._ws(rows=[
            ["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"],
            ["t1", "Tarea A", "Pendiente", "", "", "whatsapp", ""],
        ])

        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = tasks_agent_node({"message": "qué tareas tengo"})

        assert result["payload"]["operation"] == "read"
        tasks = read_tasks(self._client(ws), "SHEET_ID")
        assert len(tasks) == 1
        assert tasks[0]["id"] == "t1"
        assert tasks[0]["status"] == "pending"

    # ── Update ────────────────────────────────────────────────

    def test_update_agente_produce_payload_y_conector_actualiza(self):
        from src.agents.tasks_agent import tasks_agent_node
        from src.connectors.sheets_tasks import update_task_status

        llm_data = {
            "operation": "update",
            "task_id": "t-abc",
            "title": None,
            "status": "in_progress",
            "notes": None,
            "agent_response": "Moviendo tarea a En progreso.",
        }
        ws = self._ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = tasks_agent_node({"message": "mueve tarea t-abc a en progreso"})

        ok = update_task_status(self._client(ws), "SHEET_ID", "t-abc", result["payload"]["status"])
        assert ok is True
        calls = [c.args for c in ws.update_cell.call_args_list]
        col3 = [c for c in calls if c[1] == 3]
        assert col3[0][2] == "En progreso"

    # ── Delete ────────────────────────────────────────────────

    def test_delete_agente_produce_payload_y_conector_borra_con_audit(self):
        from src.agents.tasks_agent import tasks_agent_node
        from src.connectors.sheets_tasks import delete_task

        llm_data = {
            "operation": "delete",
            "task_id": "t-del",
            "title": None,
            "status": None,
            "notes": None,
            "agent_response": "Borrando tarea.",
        }
        ws = self._ws()
        cell = MagicMock()
        cell.row = 3
        ws.find.return_value = cell
        ws.row_values.return_value = ["t-del", "Tarea borrada", "Pendiente", "", "", "", ""]
        conn = _audit_conn()

        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = tasks_agent_node({"message": "borra tarea t-del"})

        assert result["payload"]["operation"] == "delete"
        ok = delete_task(self._client(ws), "SHEET_ID", "t-del", conn, thread_id="th-1")
        assert ok is True
        ws.delete_rows.assert_called_once_with(3)

        rows = conn.execute("SELECT action, domain FROM audit_logs").fetchall()
        assert rows[0] == ("delete_task", "tasks")


# ══════════════════════════════════════════════════════════════════════════════
# DOMINIO: IDEAS
# ══════════════════════════════════════════════════════════════════════════════


def _fake_doc(text: str) -> dict:
    return {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [{"startIndex": 1, "textRun": {"content": text}}]
                    },
                    "endIndex": len(text) + 1,
                }
            ]
        }
    }


class TestIdeasIntegracion:
    """ideas_agent_node → docs_ideas — CRUD permitido."""

    def _service(self, text: str = "", created_id: str = "") -> MagicMock:
        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc(text)
        service.documents().batchUpdate().execute.return_value = {}
        return service

    # ── Create ────────────────────────────────────────────────

    def test_create_agente_produce_payload_y_conector_inserta(self):
        from src.agents.ideas_agent import ideas_agent_node
        from src.connectors.docs_ideas import write_idea

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "Productividad",
            "summary": "Sistema de bloques de tiempo",
            "priority": "high",
            "tags": ["tiempo", "focus"],
            "status": "active",
            "raw_text": "Usar bloques de 90 minutos para trabajo profundo.",
            "agent_response": "Registrando idea.",
        }
        service = self._service()

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "anota idea sobre bloques de tiempo"})

        write_idea(service, "DOC_ID", result["payload"])
        service.documents().batchUpdate.assert_called()
        body = service.documents().batchUpdate.call_args.kwargs["body"]
        assert any("insertText" in r for r in body["requests"])

    # ── Read ──────────────────────────────────────────────────

    def test_read_agente_y_conector_retorna_ideas(self):
        from src.agents.ideas_agent import ideas_agent_node
        from src.connectors.docs_ideas import read_ideas

        llm_data = {
            "operation": "read",
            "idea_id": None,
            "theme": None,
            "summary": None,
            "priority": None,
            "tags": [],
            "status": None,
            "raw_text": None,
            "agent_response": "Listando ideas.",
        }
        doc_text = (
            "---IDEA---\nID: i1\nTema: Tech\nResumen: R\nPrioridad: low\n"
            "Tags: \nEstado: active\n---\nraw\n---FIN---\n"
        )
        service = self._service(text=doc_text)

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "muéstrame mis ideas"})

        assert result["payload"]["operation"] == "read"
        ideas = read_ideas(service, "DOC_ID")
        assert len(ideas) == 1
        assert ideas[0]["id"] == "i1"

    # ── Delete ────────────────────────────────────────────────

    def test_delete_agente_produce_payload_y_conector_borra(self):
        from src.agents.ideas_agent import ideas_agent_node
        from src.connectors.docs_ideas import delete_idea

        llm_data = {
            "operation": "delete",
            "idea_id": "i-del",
            "theme": None,
            "summary": None,
            "priority": None,
            "tags": [],
            "status": None,
            "raw_text": None,
            "agent_response": "Borrando idea.",
        }
        doc_text = (
            "---IDEA---\nID: i-del\nTema: T\nResumen: R\nPrioridad: low\n"
            "Tags: \nEstado: active\n---\nraw\n---FIN---\n"
        )
        service = self._service(text=doc_text)
        conn = _audit_conn()

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "borra idea i-del"})

        assert result["payload"]["operation"] == "delete"
        ok = delete_idea(service, "DOC_ID", "i-del", conn, thread_id="th-2")
        assert ok is True
        body = service.documents().batchUpdate.call_args.kwargs["body"]
        assert any("deleteContentRange" in r for r in body["requests"])

        rows = conn.execute("SELECT action, domain FROM audit_logs").fetchall()
        assert rows[0] == ("delete_idea", "ideas")


# ══════════════════════════════════════════════════════════════════════════════
# DOMINIO: AGENDA
# ══════════════════════════════════════════════════════════════════════════════


def _cal_service(event_id: str = "ev-1", title: str = "Reunión") -> MagicMock:
    service = MagicMock()
    service.events().insert().execute.return_value = {"id": event_id}
    service.events().list().execute.return_value = {
        "items": [
            {
                "id": event_id,
                "summary": title,
                "description": "",
                "start": {"dateTime": "2024-06-01T10:00:00-03:00"},
                "end":   {"dateTime": "2024-06-01T11:00:00-03:00"},
                "recurrence": [],
                "extendedProperties": {"private": {"ap_source": "whatsapp", "ap_status": "active"}},
            }
        ]
    }
    service.events().get().execute.return_value = {
        "id": event_id,
        "summary": title,
        "description": "",
        "extendedProperties": {"private": {"ap_source": "whatsapp", "ap_status": "active"}},
    }
    service.events().patch().execute.return_value = {}
    return service


class TestAgendaIntegracion:
    """agenda_agent_node → calendar_client — create, update, cancel, read."""

    # ── Create ────────────────────────────────────────────────

    def test_create_agente_produce_payload_y_conector_crea_evento(self):
        from src.agents.agenda_agent import agenda_agent_node
        from src.connectors.calendar_client import create_event

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "Reunión de equipo",
            "scheduled_for": "2024-06-10T09:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": None,
            "notes": None,
            "agent_response": "Creando evento.",
        }
        service = _cal_service(event_id="new-ev")

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "reunión mañana a las 9"})

        event_id = create_event(service, "primary", result["payload"])
        assert event_id == "new-ev"
        # Verificar que la última llamada a insert fue con los parámetros correctos
        last_call = service.events().insert.call_args
        assert last_call is not None
        body = last_call.kwargs["body"]
        assert body["start"]["timeZone"] == "America/Montevideo"

    # ── Read ──────────────────────────────────────────────────

    def test_read_agente_y_conector_lista_eventos(self):
        from src.agents.agenda_agent import agenda_agent_node
        from src.connectors.calendar_client import read_events

        llm_data = {
            "operation": "read",
            "event_id": None,
            "title": None,
            "scheduled_for": None,
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Listando eventos.",
        }
        service = _cal_service(event_id="ev-1", title="Dentista")

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "qué tengo esta semana"})

        assert result["payload"]["operation"] == "read"
        events = read_events(service, "primary")
        assert len(events) == 1
        assert events[0]["title"] == "Dentista"

    # ── Update ────────────────────────────────────────────────

    def test_update_agente_produce_payload_y_conector_parchea(self):
        from src.agents.agenda_agent import agenda_agent_node
        from src.connectors.calendar_client import update_event

        llm_data = {
            "operation": "update",
            "event_id": "ev-upd",
            "title": "Reunión reprogramada",
            "scheduled_for": "2024-06-12T14:00:00-03:00",
            "duration_minutes": 90,
            "recurrence": None,
            "notes": None,
            "agent_response": "Actualizando evento.",
        }
        service = _cal_service(event_id="ev-upd")

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "mueve la reunión al jueves 14hs"})

        ok = update_event(service, "primary", "ev-upd", result["payload"])
        assert ok is True
        body = service.events().patch.call_args.kwargs["body"]
        assert body["summary"] == "Reunión reprogramada"

    # ── Cancel (no delete) ────────────────────────────────────

    def test_cancel_agente_y_conector_marca_cancelado_sin_borrar(self):
        from src.agents.agenda_agent import agenda_agent_node
        from src.connectors.calendar_client import cancel_event

        llm_data = {
            "operation": "cancel",
            "event_id": "ev-can",
            "title": None,
            "scheduled_for": None,
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Cancelando evento.",
        }
        service = _cal_service(event_id="ev-can", title="Gym")

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "cancela el gym del lunes"})

        assert result["payload"]["operation"] == "cancel"
        ok = cancel_event(service, "primary", "ev-can")
        assert ok is True

        # patch llamado con args correctos, delete NO llamado
        last_patch = service.events().patch.call_args
        assert last_patch is not None
        service.events().delete.assert_not_called()

        body = last_patch.kwargs["body"]
        assert "[CANCELADO]" in body["summary"]
        assert body["extendedProperties"]["private"]["ap_status"] == "cancelled"

    # ── Recurrencia ───────────────────────────────────────────

    def test_create_evento_recurrente_incluye_rrule(self):
        from src.agents.agenda_agent import agenda_agent_node
        from src.connectors.calendar_client import create_event

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "Gym",
            "scheduled_for": "2024-06-03T07:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
            "notes": None,
            "agent_response": "Creando evento recurrente.",
        }
        service = _cal_service()

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "gym lunes miércoles viernes a las 7"})

        create_event(service, "primary", result["payload"])
        body = service.events().insert.call_args.kwargs["body"]
        assert any("RRULE:FREQ=WEEKLY" in r for r in body["recurrence"])


# ══════════════════════════════════════════════════════════════════════════════
# DOMINIO: ACCOUNTING
# ══════════════════════════════════════════════════════════════════════════════


class TestAccountingIntegracion:
    """accounting_agent_node → sheets_accounting — create, update, read.
    Borrado PROHIBIDO verificado.
    correction_note obligatoria verificada.
    """

    def _ws(self, rows: list | None = None) -> MagicMock:
        ws = MagicMock()
        ws.get_all_values.return_value = rows or [
            ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"]
        ]
        ws.find.return_value = None
        return ws

    def _client(self, ws: MagicMock) -> MagicMock:
        client = MagicMock()
        client.open_by_key.return_value.worksheet.return_value = ws
        return client

    # ── Create ────────────────────────────────────────────────

    def test_create_agente_produce_payload_y_conector_escribe(self):
        from src.agents.accounting_agent import accounting_agent_node
        from src.connectors.sheets_accounting import write_entry

        llm_data = {
            "operation": "create",
            "entry_id": None,
            "type": "income",
            "category": "Freelance",
            "amount": 2000,
            "note": "Proyecto web",
            "balance": None,
            "correction_note": None,
            "agent_response": "Registrando ingreso.",
        }
        ws = self._ws()

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "cobré 2000 por proyecto web"})

        write_entry(self._client(ws), "SHEET_ID", result["payload"])
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args.args[0]
        assert row[2] == "Ingreso"
        assert row[3] == "Freelance"
        assert row[4] == "2000"

    # ── Read ──────────────────────────────────────────────────

    def test_read_agente_y_conector_retorna_movimientos(self):
        from src.agents.accounting_agent import accounting_agent_node
        from src.connectors.sheets_accounting import read_entries

        llm_data = {
            "operation": "read",
            "entry_id": None,
            "type": None,
            "category": None,
            "amount": None,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "Listando movimientos.",
        }
        ws = self._ws(rows=[
            ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"],
            ["e1", "2024-06-01", "Ingreso", "Salario", "3000", "Mes", "3000", ""],
        ])

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "cuánto ingresé este mes"})

        assert result["payload"]["operation"] == "read"
        entries = read_entries(self._client(ws), "SHEET_ID")
        assert len(entries) == 1
        assert entries[0]["type"] == "income"
        assert entries[0]["amount"] == Decimal("3000")

    # ── Update con correction_note ────────────────────────────

    def test_update_con_correction_note_obligatoria(self):
        from src.agents.accounting_agent import accounting_agent_node
        from src.connectors.sheets_accounting import update_entry

        llm_data = {
            "operation": "update",
            "entry_id": "e-upd",
            "type": "expense",
            "category": "Comida",
            "amount": 350,
            "note": "Almuerzo corregido",
            "balance": None,
            "correction_note": "El monto original era 300, era 350",
            "agent_response": "Corrigiendo movimiento.",
        }
        ws = self._ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "corrige gasto almuerzo a 350"})

        assert result["payload"]["correction_note"] == "El monto original era 300, era 350"
        ok = update_entry(self._client(ws), "SHEET_ID", "e-upd", result["payload"])
        assert ok is True

        calls = [c.args for c in ws.update_cell.call_args_list]
        col8 = [c for c in calls if c[1] == 8]
        assert len(col8) == 1
        assert "350" in col8[0][2] or "monto" in col8[0][2].lower()

    # ── correction_note vacía → rechazo ──────────────────────

    def test_update_sin_correction_note_es_rechazado(self):
        """Edición contable sin correction_note debe fallar en el conector."""
        from src.connectors.sheets_accounting import update_entry

        ws = self._ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        ok = update_entry(
            self._client(ws), "SHEET_ID", "e1",
            {"amount": 500}  # sin correction_note
        )
        assert ok is False
        ws.update_cell.assert_not_called()

    def test_update_con_correction_note_vacia_es_rechazado(self):
        from src.connectors.sheets_accounting import update_entry

        ws = self._ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        ok = update_entry(
            self._client(ws), "SHEET_ID", "e1",
            {"amount": 500, "correction_note": "   "}
        )
        assert ok is False

    # ── Delete PROHIBIDO ──────────────────────────────────────

    def test_delete_lanza_not_implemented_error(self):
        """Intento de borrado contable siempre falla con NotImplementedError."""
        from src.connectors.sheets_accounting import delete_entry

        with pytest.raises(NotImplementedError):
            delete_entry()

    def test_delete_con_argumentos_sigue_fallando(self):
        from src.connectors.sheets_accounting import delete_entry

        ws = self._ws()
        with pytest.raises(NotImplementedError):
            delete_entry(self._client(ws), "SHEET_ID", "e1")

    def test_delete_no_llama_delete_rows(self):
        """El conector nunca toca la hoja al intentar borrar."""
        from src.connectors.sheets_accounting import delete_entry

        ws = self._ws()
        client = self._client(ws)
        with pytest.raises(NotImplementedError):
            delete_entry(client, "SHEET_ID", "e1")
        ws.delete_rows.assert_not_called()

    def test_agente_convierte_delete_a_read(self):
        """El accounting_agent_node nunca propaga operation='delete'."""
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "delete",
            "entry_id": "e-del",
            "type": None,
            "category": None,
            "amount": None,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "No puedo borrar movimientos contables.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "borra el gasto e-del"})

        assert result["payload"]["operation"] == "read"
