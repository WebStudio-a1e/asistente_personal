"""Connector para Google Sheets — tareas kanban.

Fuente de verdad: Google Sheets, hoja "Tareas".
SQLite: solo para log de borrados en audit_logs (nunca fuente de verdad).

Estructura del sheet (columnas):
    ID | Título | Estado | Creado_En | Actualizado_En | Fuente | Notas

Estados kanban (sheet ↔ canónico):
    "Pendiente"    ↔ "pending"
    "En progreso"  ↔ "in_progress"
    "Hoy"          ↔ "today"
    "Completada"   ↔ "completed"
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

import gspread

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────

SHEET_NAME = "Tareas"

HEADERS = ["ID", "Título", "Estado", "Creado_En", "Actualizado_En", "Fuente", "Notas"]

_STATUS_TO_CANONICAL: dict[str, str] = {
    "Pendiente":   "pending",
    "En progreso": "in_progress",
    "Hoy":         "today",
    "Completada":  "completed",
}

_CANONICAL_TO_STATUS: dict[str, str] = {v: k for k, v in _STATUS_TO_CANONICAL.items()}

VALID_STATUSES = set(_CANONICAL_TO_STATUS.keys())


# ── Helpers ───────────────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def to_canonical_status(sheet_status: str) -> str:
    """Convierte estado del sheet a valor canónico. Fallback: 'pending'."""
    return _STATUS_TO_CANONICAL.get(sheet_status, "pending")


def to_sheet_status(canonical: str) -> str:
    """Convierte valor canónico a etiqueta del sheet. Fallback: 'Pendiente'."""
    return _CANONICAL_TO_STATUS.get(canonical, "Pendiente")


def _row_to_dict(row: list[str]) -> dict[str, Any]:
    """Convierte fila del sheet a dict con claves canónicas."""
    padded = list(row) + [""] * max(0, 7 - len(row))
    return {
        "id":         padded[0],
        "title":      padded[1],
        "status":     to_canonical_status(padded[2]),
        "created_at": padded[3],
        "updated_at": padded[4],
        "source":     padded[5] or "whatsapp",
        "notes":      padded[6] or None,
    }


# ── Lectura ───────────────────────────────────────────────────

def read_tasks(client: gspread.Client, spreadsheet_id: str) -> list[dict]:
    """Lee todas las tareas del sheet.

    Returns:
        Lista de dicts con campos canónicos. Vacía si no hay filas de datos.
    """
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(SHEET_NAME)
    rows = ws.get_all_values()
    if len(rows) <= 1:
        return []
    return [_row_to_dict(row) for row in rows[1:] if row and row[0]]


# ── Escritura ─────────────────────────────────────────────────

def write_task(client: gspread.Client, spreadsheet_id: str, task: dict) -> None:
    """Agrega una nueva tarea como fila en el sheet.

    Args:
        task: dict con campos canónicos (id, title, status, notes, ...).
    """
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(SHEET_NAME)
    now = _now_utc()
    row = [
        task.get("id", ""),
        task.get("title", ""),
        to_sheet_status(task.get("status", "pending")),
        task.get("created_at", now),
        task.get("updated_at", now),
        task.get("source", "whatsapp"),
        task.get("notes") or "",
    ]
    ws.append_row(row, value_input_option="RAW")


def update_task_status(
    client: gspread.Client,
    spreadsheet_id: str,
    task_id: str,
    new_status: str,
) -> bool:
    """Actualiza el estado de una tarea existente en el sheet.

    Returns:
        True si se encontró y actualizó, False si no existe la tarea.
    """
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(SHEET_NAME)
    cell = ws.find(task_id, in_column=1)
    if cell is None:
        return False
    ws.update_cell(cell.row, 3, to_sheet_status(new_status))
    ws.update_cell(cell.row, 5, _now_utc())
    return True


# ── Borrado ───────────────────────────────────────────────────

def delete_task(
    client: gspread.Client,
    spreadsheet_id: str,
    task_id: str,
    conn: sqlite3.Connection,
    thread_id: str = "",
) -> bool:
    """Borra físicamente una tarea del sheet y registra en audit_logs.

    Política (DataHandling.md §6 — Tareas):
      - Borrado físico en Google Sheets.
      - Log inmutable en SQLite audit_logs.
      - SQLite nunca es fuente de verdad.

    Returns:
        True si se encontró y borró, False si no existe la tarea.
    """
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(SHEET_NAME)
    cell = ws.find(task_id, in_column=1)
    if cell is None:
        logger.warning("delete_task: tarea no encontrada — id=%s", task_id)
        return False

    row_data = ws.row_values(cell.row)
    ws.delete_rows(cell.row)

    _log_deletion(conn, thread_id, task_id, row_data)
    return True


def _log_deletion(
    conn: sqlite3.Connection,
    thread_id: str,
    task_id: str,
    row_data: list[str],
) -> None:
    """Registra el borrado en audit_logs. Falla silenciosa para no interrumpir el flujo."""
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_logs (thread_id, action, domain, payload, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    thread_id,
                    "delete_task",
                    "tasks",
                    json.dumps({"task_id": task_id, "row": row_data}),
                    "deleted",
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("_log_deletion: error escribiendo audit_log — %s", exc)
