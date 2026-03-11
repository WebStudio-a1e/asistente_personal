"""Tests T-022 — tasks_agent y sheets_tasks.

Cubre:
- sheets_tasks: lectura, escritura, actualización, borrado + audit_log, mapeo de estados
- tasks_agent_node: payload correcto, confirmation_status=detected, operaciones
"""

import json
import sqlite3
from unittest.mock import MagicMock, call, patch

import pytest

from src.graph.state import AgentState
from src.storage.sqlite import create_tables, get_connection


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = get_connection(db_path)
    create_tables(conn)
    return conn


def _mock_ws(rows: list[list[str]] | None = None) -> MagicMock:
    """Worksheet mock con get_all_values, find, update_cell, delete_rows, append_row."""
    ws = MagicMock()
    ws.get_all_values.return_value = rows or []
    ws.find.return_value = None
    return ws


def _mock_client(ws: MagicMock) -> MagicMock:
    sh = MagicMock()
    sh.worksheet.return_value = ws
    client = MagicMock()
    client.open_by_key.return_value = sh
    return client


def _agent_state(message: str = "agregar tarea") -> AgentState:
    return AgentState(
        message=message,
        intent="task",
        domain="tasks",
        payload=None,
        confirmation_status=None,
        pending_actions=[],
        agent_response=None,
        conversation_history=[],
        idempotency_key=None,
        error=None,
    )


# ── Mapeo de estados ──────────────────────────────────────────────────────────


class TestMapeoEstados:
    def test_pendiente_to_pending(self):
        from src.connectors.sheets_tasks import to_canonical_status
        assert to_canonical_status("Pendiente") == "pending"

    def test_en_progreso_to_in_progress(self):
        from src.connectors.sheets_tasks import to_canonical_status
        assert to_canonical_status("En progreso") == "in_progress"

    def test_hoy_to_today(self):
        from src.connectors.sheets_tasks import to_canonical_status
        assert to_canonical_status("Hoy") == "today"

    def test_completada_to_completed(self):
        from src.connectors.sheets_tasks import to_canonical_status
        assert to_canonical_status("Completada") == "completed"

    def test_unknown_falls_back_to_pending(self):
        from src.connectors.sheets_tasks import to_canonical_status
        assert to_canonical_status("Desconocido") == "pending"

    def test_pending_to_pendiente(self):
        from src.connectors.sheets_tasks import to_sheet_status
        assert to_sheet_status("pending") == "Pendiente"

    def test_in_progress_to_en_progreso(self):
        from src.connectors.sheets_tasks import to_sheet_status
        assert to_sheet_status("in_progress") == "En progreso"

    def test_today_to_hoy(self):
        from src.connectors.sheets_tasks import to_sheet_status
        assert to_sheet_status("today") == "Hoy"

    def test_completed_to_completada(self):
        from src.connectors.sheets_tasks import to_sheet_status
        assert to_sheet_status("completed") == "Completada"

    @pytest.mark.parametrize("canonical", ["pending", "in_progress", "today", "completed"])
    def test_roundtrip_canonical_to_sheet_to_canonical(self, canonical):
        from src.connectors.sheets_tasks import to_canonical_status, to_sheet_status
        assert to_canonical_status(to_sheet_status(canonical)) == canonical


# ── read_tasks ────────────────────────────────────────────────────────────────


class TestReadTasks:
    def test_empty_sheet_returns_empty_list(self):
        from src.connectors.sheets_tasks import read_tasks
        ws = _mock_ws([["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"]])
        client = _mock_client(ws)
        assert read_tasks(client, "sheet-id") == []

    def test_no_rows_returns_empty_list(self):
        from src.connectors.sheets_tasks import read_tasks
        ws = _mock_ws([])
        client = _mock_client(ws)
        assert read_tasks(client, "sheet-id") == []

    def test_returns_list_of_dicts(self):
        from src.connectors.sheets_tasks import read_tasks
        rows = [
            ["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"],
            ["t-001", "Revisar informe", "Pendiente", "2026-01-01", "2026-01-01", "whatsapp", ""],
        ]
        ws = _mock_ws(rows)
        client = _mock_client(ws)
        result = read_tasks(client, "sheet-id")
        assert len(result) == 1
        assert result[0]["id"] == "t-001"
        assert result[0]["title"] == "Revisar informe"
        assert result[0]["status"] == "pending"

    def test_maps_all_kanban_statuses(self):
        from src.connectors.sheets_tasks import read_tasks
        rows = [
            ["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"],
            ["t-001", "T1", "Pendiente",   "2026-01-01", "2026-01-01", "whatsapp", ""],
            ["t-002", "T2", "En progreso", "2026-01-01", "2026-01-01", "whatsapp", ""],
            ["t-003", "T3", "Hoy",         "2026-01-01", "2026-01-01", "whatsapp", ""],
            ["t-004", "T4", "Completada",  "2026-01-01", "2026-01-01", "whatsapp", ""],
        ]
        ws = _mock_ws(rows)
        client = _mock_client(ws)
        result = read_tasks(client, "sheet-id")
        statuses = [r["status"] for r in result]
        assert statuses == ["pending", "in_progress", "today", "completed"]

    def test_skips_rows_without_id(self):
        from src.connectors.sheets_tasks import read_tasks
        rows = [
            ["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"],
            ["", "Sin ID", "Pendiente", "", "", "", ""],
            ["t-001", "Con ID", "Hoy", "", "", "", ""],
        ]
        ws = _mock_ws(rows)
        client = _mock_client(ws)
        result = read_tasks(client, "sheet-id")
        assert len(result) == 1
        assert result[0]["id"] == "t-001"

    def test_uses_correct_spreadsheet_id(self):
        from src.connectors.sheets_tasks import read_tasks
        ws = _mock_ws([])
        client = _mock_client(ws)
        read_tasks(client, "my-spreadsheet-id")
        client.open_by_key.assert_called_once_with("my-spreadsheet-id")


# ── write_task ────────────────────────────────────────────────────────────────


class TestWriteTask:
    def test_calls_append_row(self):
        from src.connectors.sheets_tasks import write_task
        ws = _mock_ws()
        client = _mock_client(ws)
        write_task(client, "sheet-id", {
            "id": "t-001", "title": "Nueva tarea", "status": "pending",
            "notes": None, "source": "whatsapp",
        })
        ws.append_row.assert_called_once()

    def test_converts_status_to_sheet_format(self):
        from src.connectors.sheets_tasks import write_task
        ws = _mock_ws()
        client = _mock_client(ws)
        write_task(client, "sheet-id", {
            "id": "t-001", "title": "Tarea", "status": "in_progress",
        })
        row_written = ws.append_row.call_args[0][0]
        assert row_written[2] == "En progreso"

    def test_all_kanban_statuses_written_correctly(self):
        from src.connectors.sheets_tasks import write_task
        statuses = [
            ("pending", "Pendiente"),
            ("in_progress", "En progreso"),
            ("today", "Hoy"),
            ("completed", "Completada"),
        ]
        for canonical, expected_sheet in statuses:
            ws = _mock_ws()
            client = _mock_client(ws)
            write_task(client, "sheet-id", {"id": "t", "title": "T", "status": canonical})
            row = ws.append_row.call_args[0][0]
            assert row[2] == expected_sheet, f"fallo para {canonical}"

    def test_row_has_seven_columns(self):
        from src.connectors.sheets_tasks import write_task
        ws = _mock_ws()
        client = _mock_client(ws)
        write_task(client, "sheet-id", {
            "id": "t-001", "title": "Tarea", "status": "pending",
        })
        row = ws.append_row.call_args[0][0]
        assert len(row) == 7


# ── update_task_status ────────────────────────────────────────────────────────


class TestUpdateTaskStatus:
    def test_returns_true_if_task_found(self):
        from src.connectors.sheets_tasks import update_task_status
        cell = MagicMock(row=2)
        ws = _mock_ws()
        ws.find.return_value = cell
        client = _mock_client(ws)
        assert update_task_status(client, "sheet-id", "t-001", "today") is True

    def test_returns_false_if_task_not_found(self):
        from src.connectors.sheets_tasks import update_task_status
        ws = _mock_ws()
        ws.find.return_value = None
        client = _mock_client(ws)
        assert update_task_status(client, "sheet-id", "t-999", "today") is False

    def test_updates_status_column(self):
        from src.connectors.sheets_tasks import update_task_status
        cell = MagicMock(row=3)
        ws = _mock_ws()
        ws.find.return_value = cell
        client = _mock_client(ws)
        update_task_status(client, "sheet-id", "t-001", "completed")
        # Columna 3 = Estado
        update_calls = ws.update_cell.call_args_list
        assert any(c[0][1] == 3 and c[0][2] == "Completada" for c in update_calls)

    def test_updates_updated_at_column(self):
        from src.connectors.sheets_tasks import update_task_status
        cell = MagicMock(row=3)
        ws = _mock_ws()
        ws.find.return_value = cell
        client = _mock_client(ws)
        update_task_status(client, "sheet-id", "t-001", "pending")
        # Columna 5 = Actualizado_En
        update_calls = ws.update_cell.call_args_list
        assert any(c[0][1] == 5 for c in update_calls)


# ── delete_task ───────────────────────────────────────────────────────────────


class TestDeleteTask:
    def test_returns_true_if_task_found(self, tmp_db):
        from src.connectors.sheets_tasks import delete_task
        cell = MagicMock(row=2)
        ws = _mock_ws()
        ws.find.return_value = cell
        ws.row_values.return_value = ["t-001", "Tarea", "Pendiente", "", "", "", ""]
        client = _mock_client(ws)
        assert delete_task(client, "sheet-id", "t-001", tmp_db) is True

    def test_returns_false_if_task_not_found(self, tmp_db):
        from src.connectors.sheets_tasks import delete_task
        ws = _mock_ws()
        ws.find.return_value = None
        client = _mock_client(ws)
        assert delete_task(client, "sheet-id", "t-999", tmp_db) is False

    def test_calls_delete_rows(self, tmp_db):
        from src.connectors.sheets_tasks import delete_task
        cell = MagicMock(row=2)
        ws = _mock_ws()
        ws.find.return_value = cell
        ws.row_values.return_value = ["t-001", "Tarea", "Pendiente", "", "", "", ""]
        client = _mock_client(ws)
        delete_task(client, "sheet-id", "t-001", tmp_db)
        ws.delete_rows.assert_called_once_with(2)

    def test_logs_to_audit_logs(self, tmp_db):
        from src.connectors.sheets_tasks import delete_task
        cell = MagicMock(row=2)
        ws = _mock_ws()
        ws.find.return_value = cell
        ws.row_values.return_value = ["t-001", "Tarea borrada", "Hoy", "", "", "", ""]
        client = _mock_client(ws)
        delete_task(client, "sheet-id", "t-001", tmp_db, thread_id="thread-x")
        rows = tmp_db.execute("SELECT * FROM audit_logs WHERE action='delete_task'").fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "delete_task"   # action
        assert rows[0][3] == "tasks"          # domain
        assert rows[0][5] == "deleted"        # status

    def test_audit_log_contains_task_id(self, tmp_db):
        from src.connectors.sheets_tasks import delete_task
        cell = MagicMock(row=2)
        ws = _mock_ws()
        ws.find.return_value = cell
        ws.row_values.return_value = ["t-42", "Tarea", "Pendiente", "", "", "", ""]
        client = _mock_client(ws)
        delete_task(client, "sheet-id", "t-42", tmp_db)
        row = tmp_db.execute("SELECT payload FROM audit_logs").fetchone()
        payload = json.loads(row[0])
        assert payload["task_id"] == "t-42"

    def test_no_deletion_if_not_found_no_audit_log(self, tmp_db):
        from src.connectors.sheets_tasks import delete_task
        ws = _mock_ws()
        ws.find.return_value = None
        client = _mock_client(ws)
        delete_task(client, "sheet-id", "t-999", tmp_db)
        rows = tmp_db.execute("SELECT * FROM audit_logs").fetchall()
        assert len(rows) == 0


# ── tasks_agent_node ──────────────────────────────────────────────────────────


def _mock_llm(payload: dict) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps(payload))
    return llm


class TestTasksAgentNode:
    def test_sets_confirmation_status_detected(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "Tarea", "status": "pending",
                    "task_id": None, "notes": None, "agent_response": "Voy a crear la tarea"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("agregar tarea"))
        assert result["confirmation_status"] == "detected"

    def test_sets_payload_with_required_fields(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "Mi tarea", "status": "pending",
                    "task_id": None, "notes": None, "agent_response": "ok"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("crear tarea"))
        payload = result["payload"]
        for key in ("operation", "task_id", "title", "status", "source", "created_at", "updated_at"):
            assert key in payload

    def test_operation_create(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "Nueva tarea", "status": "pending",
                    "task_id": None, "notes": None, "agent_response": "Crear"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("agregar tarea: revisar el informe"))
        assert result["payload"]["operation"] == "create"

    def test_operation_update(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "update", "title": None, "status": "completed",
                    "task_id": "t-001", "notes": None, "agent_response": "Actualizar"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("marcá la tarea t-001 como completada"))
        assert result["payload"]["operation"] == "update"
        assert result["payload"]["status"] == "completed"

    def test_operation_delete(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "delete", "title": None, "status": None,
                    "task_id": "t-005", "notes": None, "agent_response": "Borrar"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("borrá la tarea t-005"))
        assert result["payload"]["operation"] == "delete"
        assert result["payload"]["task_id"] == "t-005"

    def test_operation_read(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "read", "title": None, "status": None,
                    "task_id": None, "notes": None, "agent_response": "Listar"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("¿qué tareas tengo pendientes?"))
        assert result["payload"]["operation"] == "read"

    def test_source_is_always_whatsapp(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "T", "status": "pending",
                    "task_id": None, "notes": None, "agent_response": "ok"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("tarea"))
        assert result["payload"]["source"] == "whatsapp"

    def test_task_id_generated_if_null(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "Tarea nueva", "status": "pending",
                    "task_id": None, "notes": None, "agent_response": "ok"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("nueva tarea"))
        assert result["payload"]["task_id"]  # no vacío
        assert len(result["payload"]["task_id"]) > 0

    def test_agent_response_propagated(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "T", "status": "pending",
                    "task_id": None, "notes": None,
                    "agent_response": "Voy a crear la tarea 'T'"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("crear tarea T"))
        assert result["agent_response"] == "Voy a crear la tarea 'T'"

    def test_parse_error_still_returns_valid_payload(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="esto no es json")
        with patch("src.agents.tasks_agent.get_llm", return_value=llm):
            result = tasks_agent_node(_agent_state("tarea"))
        assert "payload" in result
        assert result["confirmation_status"] == "detected"

    def test_llm_receives_message(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "T", "status": "pending",
                    "task_id": None, "notes": None, "agent_response": "ok"}
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=json.dumps(llm_resp))
        with patch("src.agents.tasks_agent.get_llm", return_value=llm):
            tasks_agent_node(_agent_state("mensaje de prueba específico"))
        call_args = llm.invoke.call_args[0][0]
        assert any("mensaje de prueba específico" in str(part) for part in call_args)

    def test_status_defaults_to_pending_if_missing(self):
        from src.agents.tasks_agent import tasks_agent_node
        llm_resp = {"operation": "create", "title": "T",
                    "task_id": None, "notes": None, "agent_response": "ok"}
        with patch("src.agents.tasks_agent.get_llm", return_value=_mock_llm(llm_resp)):
            result = tasks_agent_node(_agent_state("tarea sin estado"))
        assert result["payload"]["status"] == "pending"
