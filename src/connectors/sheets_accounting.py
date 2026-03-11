"""Connector para Google Sheets — contabilidad.

Fuente de verdad: Google Sheets, hoja "Contabilidad".
Borrado: PROHIBIDO. Solo corrección por edición con correction_note.

Estructura del sheet (columnas):
    ID | Fecha | Tipo | Categoría | Monto | Nota | Balance | Correction_Note

Tipos canónicos:
    "Ingreso"  ↔ "income"
    "Egreso"   ↔ "expense"
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import gspread

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────

SHEET_NAME = "Contabilidad"

HEADERS = ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"]

_MVD_TZ = timezone(timedelta(hours=-3))

_TYPE_TO_CANONICAL: dict[str, str] = {
    "Ingreso": "income",
    "Egreso":  "expense",
}
_CANONICAL_TO_TYPE: dict[str, str] = {v: k for k, v in _TYPE_TO_CANONICAL.items()}

VALID_TYPES = set(_CANONICAL_TO_TYPE.keys())


# ── Helpers ───────────────────────────────────────────────────


def _now_mvd() -> str:
    return datetime.now(tz=_MVD_TZ).isoformat()


def to_canonical_type(sheet_type: str) -> str:
    """Convierte tipo del sheet a valor canónico. Fallback: 'expense'."""
    return _TYPE_TO_CANONICAL.get(sheet_type, "expense")


def to_sheet_type(canonical: str) -> str:
    """Convierte valor canónico a etiqueta del sheet. Fallback: 'Egreso'."""
    return _CANONICAL_TO_TYPE.get(canonical, "Egreso")


def _row_to_dict(row: list[str]) -> dict[str, Any]:
    """Convierte fila del sheet a dict con claves canónicas."""
    padded = list(row) + [""] * max(0, 8 - len(row))
    amount_raw = padded[4]
    balance_raw = padded[6]
    try:
        amount = Decimal(amount_raw) if amount_raw else Decimal("0")
    except InvalidOperation:
        amount = Decimal("0")
    try:
        balance = Decimal(balance_raw) if balance_raw else None
    except InvalidOperation:
        balance = None
    return {
        "id":              padded[0],
        "date":            padded[1],
        "type":            to_canonical_type(padded[2]),
        "category":        padded[3],
        "amount":          amount,
        "note":            padded[5] or None,
        "balance":         balance,
        "correction_note": padded[7] or None,
    }


# ── Lectura ───────────────────────────────────────────────────


def read_entries(client: gspread.Client, spreadsheet_id: str) -> list[dict]:
    """Lee todos los movimientos contables del sheet.

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


def write_entry(client: gspread.Client, spreadsheet_id: str, entry: dict) -> None:
    """Agrega un nuevo movimiento contable como fila en el sheet.

    Args:
        entry: dict con campos canónicos (id, type, category, amount, note, ...).
    """
    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(SHEET_NAME)
    now = _now_mvd()
    row = [
        entry.get("id", ""),
        entry.get("date", now),
        to_sheet_type(entry.get("type", "expense")),
        entry.get("category", ""),
        str(entry.get("amount", "0")),
        entry.get("note") or "",
        str(entry.get("balance", "")) if entry.get("balance") is not None else "",
        entry.get("correction_note") or "",
    ]
    ws.append_row(row, value_input_option="RAW")


# ── Edición ───────────────────────────────────────────────────


def update_entry(
    client: gspread.Client,
    spreadsheet_id: str,
    entry_id: str,
    updates: dict,
) -> bool:
    """Edita un movimiento contable existente.

    Política (DataHandling.md §5 — Contabilidad):
      - correction_note es OBLIGATORIA. Si está ausente o vacía, rechaza la edición.
      - No existe herramienta de borrado.

    Returns:
        True si se encontró y editó, False si no existe o falta correction_note.
    """
    correction_note = updates.get("correction_note", "")
    if not correction_note or not str(correction_note).strip():
        logger.warning(
            "update_entry: corrección rechazada — correction_note obligatoria — id=%s",
            entry_id,
        )
        return False

    sh = client.open_by_key(spreadsheet_id)
    ws = sh.worksheet(SHEET_NAME)
    cell = ws.find(entry_id, in_column=1)
    if cell is None:
        logger.warning("update_entry: movimiento no encontrado — id=%s", entry_id)
        return False

    if updates.get("type"):
        ws.update_cell(cell.row, 3, to_sheet_type(updates["type"]))
    if updates.get("category"):
        ws.update_cell(cell.row, 4, updates["category"])
    if updates.get("amount") is not None:
        ws.update_cell(cell.row, 5, str(updates["amount"]))
    if updates.get("note") is not None:
        ws.update_cell(cell.row, 6, updates["note"])
    if updates.get("balance") is not None:
        ws.update_cell(cell.row, 7, str(updates["balance"]))

    # Siempre escribe correction_note
    ws.update_cell(cell.row, 8, str(correction_note).strip())

    logger.info("update_entry: movimiento editado — id=%s", entry_id)
    return True


# ── Borrado — PROHIBIDO ───────────────────────────────────────


def delete_entry(*_args: Any, **_kwargs: Any) -> None:
    """Borrado de movimientos contables: PROHIBIDO.

    Política (DataHandling.md §6 — Contabilidad):
      El accounting_agent no tiene herramienta de borrado.
      Solo se puede corregir por edición con correction_note.

    Raises:
        NotImplementedError: siempre.
    """
    raise NotImplementedError(
        "Borrado de movimientos contables prohibido. "
        "Use update_entry con correction_note para corregir."
    )
