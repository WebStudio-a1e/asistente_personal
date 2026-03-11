"""Tests T-025 — accounting_agent + sheets_accounting.

Sin credenciales reales: todas las llamadas a LLM y Google APIs están mockeadas.
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(payload: dict) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps(payload))
    return llm


def _mock_client(ws: MagicMock) -> MagicMock:
    client = MagicMock()
    client.open_by_key.return_value.worksheet.return_value = ws
    return client


def _make_ws(rows: list[list[str]] | None = None) -> MagicMock:
    """Worksheet mock con filas configurables."""
    ws = MagicMock()
    ws.get_all_values.return_value = rows or [
        ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"]
    ]
    ws.find.return_value = None
    return ws


# ── accounting_agent_node ─────────────────────────────────────────────────────


class TestAccountingAgentNode:
    def test_retorna_payload_con_campos_canonicos(self):
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "create",
            "entry_id": None,
            "type": "income",
            "category": "Freelance",
            "amount": 1500.00,
            "note": "Pago proyecto X",
            "balance": None,
            "correction_note": None,
            "agent_response": "Voy a registrar el ingreso.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "cobré 1500 por proyecto X"})

        assert result["payload"]["operation"] == "create"
        assert result["payload"]["type"] == "income"
        assert result["payload"]["category"] == "Freelance"
        assert result["payload"]["amount"] == 1500.00
        assert result["payload"]["note"] == "Pago proyecto X"

    def test_genera_entry_id_si_llm_devuelve_null(self):
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "create",
            "entry_id": None,
            "type": "expense",
            "category": "Comida",
            "amount": 200,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "gasté 200 en comida"})

        assert len(result["payload"]["entry_id"]) == 36  # UUID

    def test_default_type_expense(self):
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "create",
            "entry_id": None,
            "type": None,
            "category": None,
            "amount": None,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "algo"})

        assert result["payload"]["type"] == "expense"

    def test_confirmation_status_es_detected(self):
        from src.agents.accounting_agent import accounting_agent_node
        from src.domain.confirmation import ConfirmationStatus

        llm_data = {
            "operation": "create",
            "entry_id": None,
            "type": "expense",
            "category": "Transporte",
            "amount": 100,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "taxi 100"})

        assert result["confirmation_status"] == ConfirmationStatus.DETECTED

    def test_delete_convertido_a_read(self):
        """Si el LLM devuelve 'delete', el agente lo convierte a 'read'."""
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "delete",
            "entry_id": "entry-abc",
            "type": None,
            "category": None,
            "amount": None,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "No puedo borrar movimientos contables.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "borra el gasto abc"})

        assert result["payload"]["operation"] == "read"

    def test_update_propaga_correction_note(self):
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "update",
            "entry_id": "e-123",
            "type": "expense",
            "category": "Comida",
            "amount": 250,
            "note": "Almuerzo",
            "balance": None,
            "correction_note": "El monto original era incorrecto",
            "agent_response": "Corrijo el movimiento.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "corrige gasto e-123 a 250"})

        assert result["payload"]["correction_note"] == "El monto original era incorrecto"

    def test_parse_error_usa_defaults(self):
        from src.agents.accounting_agent import accounting_agent_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="no es json")

        with patch("src.agents.accounting_agent.get_llm", return_value=llm):
            result = accounting_agent_node({"message": "algo"})

        assert result["payload"]["operation"] == "create"
        assert result["payload"]["type"] == "expense"

    def test_markdown_fence_stripping(self):
        from src.agents.accounting_agent import accounting_agent_node

        inner = {
            "operation": "create",
            "entry_id": None,
            "type": "income",
            "category": "Salario",
            "amount": 3000,
            "note": "Mes de junio",
            "balance": None,
            "correction_note": None,
            "agent_response": "Registrando ingreso.",
        }
        fenced = f"```json\n{json.dumps(inner)}\n```"
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=fenced)

        with patch("src.agents.accounting_agent.get_llm", return_value=llm):
            result = accounting_agent_node({"message": "salario 3000"})

        assert result["payload"]["type"] == "income"
        assert result["payload"]["amount"] == 3000

    def test_source_es_whatsapp(self):
        from src.agents.accounting_agent import accounting_agent_node

        llm_data = {
            "operation": "create",
            "entry_id": None,
            "type": "expense",
            "category": "X",
            "amount": 100,
            "note": None,
            "balance": None,
            "correction_note": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = accounting_agent_node({"message": "gasto 100"})

        assert result["payload"]["source"] == "whatsapp"

    def test_usa_llm_accounting(self):
        from src.agents.accounting_agent import accounting_agent_node

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

        with patch("src.agents.accounting_agent.get_llm", return_value=_mock_llm(llm_data)) as mock_get:
            accounting_agent_node({"message": "cuánto gasté"})
            mock_get.assert_called_once_with("accounting")


# ── sheets_accounting — conversión de tipos ───────────────────────────────────


class TestTipoConversiones:
    def test_to_canonical_income(self):
        from src.connectors.sheets_accounting import to_canonical_type
        assert to_canonical_type("Ingreso") == "income"

    def test_to_canonical_expense(self):
        from src.connectors.sheets_accounting import to_canonical_type
        assert to_canonical_type("Egreso") == "expense"

    def test_to_canonical_fallback_expense(self):
        from src.connectors.sheets_accounting import to_canonical_type
        assert to_canonical_type("Desconocido") == "expense"

    def test_to_sheet_income(self):
        from src.connectors.sheets_accounting import to_sheet_type
        assert to_sheet_type("income") == "Ingreso"

    def test_to_sheet_expense(self):
        from src.connectors.sheets_accounting import to_sheet_type
        assert to_sheet_type("expense") == "Egreso"

    def test_to_sheet_fallback_egreso(self):
        from src.connectors.sheets_accounting import to_sheet_type
        assert to_sheet_type("desconocido") == "Egreso"


# ── sheets_accounting — read_entries ─────────────────────────────────────────


class TestReadEntries:
    def test_retorna_lista_de_movimientos(self):
        from src.connectors.sheets_accounting import read_entries

        ws = _make_ws(rows=[
            ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"],
            ["e1", "2024-06-01", "Ingreso", "Salario", "3000", "Junio", "3000", ""],
            ["e2", "2024-06-02", "Egreso", "Comida", "150", "Almuerzo", "2850", ""],
        ])
        result = read_entries(_mock_client(ws), "SHEET_ID")
        assert len(result) == 2
        assert result[0]["id"] == "e1"
        assert result[0]["type"] == "income"
        assert result[0]["amount"] == Decimal("3000")
        assert result[1]["type"] == "expense"

    def test_retorna_lista_vacia_sin_datos(self):
        from src.connectors.sheets_accounting import read_entries

        ws = _make_ws()
        result = read_entries(_mock_client(ws), "SHEET_ID")
        assert result == []

    def test_balance_none_si_columna_vacia(self):
        from src.connectors.sheets_accounting import read_entries

        ws = _make_ws(rows=[
            ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"],
            ["e1", "2024-06-01", "Egreso", "X", "100", "", "", ""],
        ])
        result = read_entries(_mock_client(ws), "SHEET_ID")
        assert result[0]["balance"] is None

    def test_correction_note_none_si_columna_vacia(self):
        from src.connectors.sheets_accounting import read_entries

        ws = _make_ws(rows=[
            ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"],
            ["e1", "2024-06-01", "Ingreso", "X", "500", "Nota", "500", ""],
        ])
        result = read_entries(_mock_client(ws), "SHEET_ID")
        assert result[0]["correction_note"] is None

    def test_ignora_filas_sin_id(self):
        from src.connectors.sheets_accounting import read_entries

        ws = _make_ws(rows=[
            ["ID", "Fecha", "Tipo", "Categoría", "Monto", "Nota", "Balance", "Correction_Note"],
            ["", "2024-06-01", "Egreso", "X", "100", "", "", ""],
            ["e1", "2024-06-02", "Ingreso", "Y", "200", "", "", ""],
        ])
        result = read_entries(_mock_client(ws), "SHEET_ID")
        assert len(result) == 1
        assert result[0]["id"] == "e1"


# ── sheets_accounting — write_entry ──────────────────────────────────────────


class TestWriteEntry:
    def test_llama_append_row(self):
        from src.connectors.sheets_accounting import write_entry

        ws = _make_ws()
        write_entry(_mock_client(ws), "SHEET_ID", {
            "id": "e-new",
            "date": "2024-06-01T10:00:00-03:00",
            "type": "income",
            "category": "Freelance",
            "amount": Decimal("1500"),
            "note": "Proyecto",
            "balance": None,
            "correction_note": None,
        })
        ws.append_row.assert_called_once()

    def test_row_incluye_tipo_sheet(self):
        from src.connectors.sheets_accounting import write_entry

        ws = _make_ws()
        write_entry(_mock_client(ws), "SHEET_ID", {
            "id": "e1",
            "type": "income",
            "category": "Salario",
            "amount": 3000,
            "note": "Mes",
        })
        row = ws.append_row.call_args.args[0]
        assert row[2] == "Ingreso"  # tipo en formato sheet

    def test_row_incluye_id_y_categoria(self):
        from src.connectors.sheets_accounting import write_entry

        ws = _make_ws()
        write_entry(_mock_client(ws), "SHEET_ID", {
            "id": "e-test",
            "type": "expense",
            "category": "Transporte",
            "amount": 200,
            "note": None,
        })
        row = ws.append_row.call_args.args[0]
        assert row[0] == "e-test"
        assert row[3] == "Transporte"


# ── sheets_accounting — update_entry ─────────────────────────────────────────


class TestUpdateEntry:
    def test_retorna_true_con_correction_note(self):
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        result = update_entry(
            _mock_client(ws), "SHEET_ID", "e1",
            {"amount": 300, "correction_note": "Monto incorrecto"}
        )
        assert result is True

    def test_escribe_correction_note_en_columna_8(self):
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        update_entry(
            _mock_client(ws), "SHEET_ID", "e1",
            {"amount": 300, "correction_note": "Corrección de monto"}
        )
        # Verificar que update_cell fue llamado con columna 8 para correction_note
        calls = [c.args for c in ws.update_cell.call_args_list]
        col8_calls = [c for c in calls if c[1] == 8]
        assert len(col8_calls) == 1
        assert col8_calls[0][2] == "Corrección de monto"

    def test_retorna_false_sin_correction_note(self):
        """Edición rechazada si correction_note está ausente."""
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        result = update_entry(
            _mock_client(ws), "SHEET_ID", "e1",
            {"amount": 300}  # sin correction_note
        )
        assert result is False
        ws.update_cell.assert_not_called()

    def test_retorna_false_con_correction_note_vacia(self):
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        result = update_entry(
            _mock_client(ws), "SHEET_ID", "e1",
            {"amount": 300, "correction_note": "  "}
        )
        assert result is False

    def test_retorna_false_si_movimiento_no_existe(self):
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        ws.find.return_value = None

        result = update_entry(
            _mock_client(ws), "SHEET_ID", "no-existe",
            {"correction_note": "razón"}
        )
        assert result is False

    def test_actualiza_tipo(self):
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        cell = MagicMock()
        cell.row = 2
        ws.find.return_value = cell

        update_entry(
            _mock_client(ws), "SHEET_ID", "e1",
            {"type": "income", "correction_note": "Era un ingreso"}
        )
        calls = [c.args for c in ws.update_cell.call_args_list]
        col3_calls = [c for c in calls if c[1] == 3]
        assert col3_calls[0][2] == "Ingreso"

    def test_actualiza_monto(self):
        from src.connectors.sheets_accounting import update_entry

        ws = _make_ws()
        cell = MagicMock()
        cell.row = 3
        ws.find.return_value = cell

        update_entry(
            _mock_client(ws), "SHEET_ID", "e2",
            {"amount": Decimal("999"), "correction_note": "Ajuste"}
        )
        calls = [c.args for c in ws.update_cell.call_args_list]
        col5_calls = [c for c in calls if c[1] == 5]
        assert col5_calls[0][2] == "999"


# ── sheets_accounting — delete_entry PROHIBIDO ───────────────────────────────


class TestDeleteEntryProhibido:
    def test_lanza_not_implemented_error(self):
        from src.connectors.sheets_accounting import delete_entry

        with pytest.raises(NotImplementedError):
            delete_entry()

    def test_mensaje_de_error_menciona_prohibicion(self):
        from src.connectors.sheets_accounting import delete_entry

        with pytest.raises(NotImplementedError, match="[Pp]rohibido|PROHIBIDO"):
            delete_entry()

    def test_no_acepta_argumentos_y_sigue_fallando(self):
        from src.connectors.sheets_accounting import delete_entry

        with pytest.raises(NotImplementedError):
            delete_entry("client", "sheet_id", "entry_id")

    def test_no_tiene_logica_de_borrado(self):
        """Verificar que delete_entry no llama a ningún método de gspread."""
        from src.connectors.sheets_accounting import delete_entry

        ws = MagicMock()
        with pytest.raises(NotImplementedError):
            delete_entry(ws, "SHEET_ID", "e1")
        ws.delete_rows.assert_not_called()
        ws.delete_row.assert_not_called()
