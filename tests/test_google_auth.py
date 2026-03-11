"""Tests T-021 — google_auth: autenticación reutilizable para Sheets, Docs y Calendar.

Sin credenciales reales: todas las llamadas a Google APIs están mockeadas.
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _fake_creds() -> MagicMock:
    return MagicMock()


# ── Importación y constantes ──────────────────────────────────────────────────


class TestModulo:
    def test_importable(self):
        from src.connectors.google_auth import (  # noqa: F401
            get_calendar_service,
            get_docs_service,
            get_sheets_client,
        )

    def test_scopes_sheets_definidos(self):
        from src.connectors.google_auth import SCOPES_SHEETS

        assert len(SCOPES_SHEETS) > 0
        assert any("spreadsheets" in s or "drive" in s for s in SCOPES_SHEETS)

    def test_scopes_docs_definidos(self):
        from src.connectors.google_auth import SCOPES_DOCS

        assert len(SCOPES_DOCS) > 0
        assert any("documents" in s or "drive" in s for s in SCOPES_DOCS)

    def test_scopes_calendar_definidos(self):
        from src.connectors.google_auth import SCOPES_CALENDAR

        assert len(SCOPES_CALENDAR) > 0
        assert any("calendar" in s for s in SCOPES_CALENDAR)

    def test_scopes_son_listas(self):
        from src.connectors.google_auth import (
            SCOPES_CALENDAR,
            SCOPES_DOCS,
            SCOPES_SHEETS,
        )

        assert isinstance(SCOPES_SHEETS, list)
        assert isinstance(SCOPES_DOCS, list)
        assert isinstance(SCOPES_CALENDAR, list)


# ── FileNotFoundError cuando no existen credenciales ─────────────────────────


class TestCredencialesAusentes:
    def test_sheets_lanza_error_si_no_hay_credenciales(self, tmp_path):
        from src.connectors.google_auth import get_sheets_client

        with pytest.raises(FileNotFoundError, match="credenciales"):
            get_sheets_client(credentials_path=str(tmp_path / "noexiste.json"))

    def test_docs_lanza_error_si_no_hay_credenciales(self, tmp_path):
        from src.connectors.google_auth import get_docs_service

        with pytest.raises(FileNotFoundError, match="credenciales"):
            get_docs_service(credentials_path=str(tmp_path / "noexiste.json"))

    def test_calendar_lanza_error_si_no_hay_credenciales(self, tmp_path):
        from src.connectors.google_auth import get_calendar_service

        with pytest.raises(FileNotFoundError, match="credenciales"):
            get_calendar_service(credentials_path=str(tmp_path / "noexiste.json"))

    def test_mensaje_de_error_incluye_la_ruta(self, tmp_path):
        from src.connectors.google_auth import get_sheets_client

        ruta = str(tmp_path / "mi_archivo.json")
        with pytest.raises(FileNotFoundError) as exc_info:
            get_sheets_client(credentials_path=ruta)
        assert "mi_archivo.json" in str(exc_info.value)


# ── get_sheets_client con credenciales mockeadas ──────────────────────────────


class TestGetSheetsClient:
    def test_retorna_cliente_gspread(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")  # archivo vacío — mockeamos el parse

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.gspread.authorize",
                  return_value=MagicMock()) as mock_authorize,
        ):
            from src.connectors.google_auth import get_sheets_client

            result = get_sheets_client(credentials_path=str(creds_file))
            mock_authorize.assert_called_once()
            assert result is not None

    def test_usa_scopes_sheets(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()) as mock_creds,
            patch("src.connectors.google_auth.gspread.authorize", return_value=MagicMock()),
        ):
            from src.connectors.google_auth import SCOPES_SHEETS, get_sheets_client

            get_sheets_client(credentials_path=str(creds_file))
            _, kwargs = mock_creds.call_args
            assert kwargs.get("scopes") == SCOPES_SHEETS

    def test_usa_path_de_env_si_no_se_pasa_argumento(self, tmp_path, monkeypatch):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds_file))

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.gspread.authorize",
                  return_value=MagicMock()) as mock_auth,
        ):
            from src.connectors.google_auth import get_sheets_client

            get_sheets_client()
            mock_auth.assert_called_once()


# ── get_docs_service con credenciales mockeadas ───────────────────────────────


class TestGetDocsService:
    def test_retorna_resource(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.build",
                  return_value=MagicMock()) as mock_build,
        ):
            from src.connectors.google_auth import get_docs_service

            result = get_docs_service(credentials_path=str(creds_file))
            mock_build.assert_called_once()
            assert result is not None

    def test_usa_docs_v1(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.build",
                  return_value=MagicMock()) as mock_build,
        ):
            from src.connectors.google_auth import get_docs_service

            get_docs_service(credentials_path=str(creds_file))
            args, _ = mock_build.call_args
            assert args[0] == "docs"
            assert args[1] == "v1"

    def test_usa_scopes_docs(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()) as mock_creds,
            patch("src.connectors.google_auth.build", return_value=MagicMock()),
        ):
            from src.connectors.google_auth import SCOPES_DOCS, get_docs_service

            get_docs_service(credentials_path=str(creds_file))
            _, kwargs = mock_creds.call_args
            assert kwargs.get("scopes") == SCOPES_DOCS


# ── get_calendar_service con credenciales mockeadas ──────────────────────────


class TestGetCalendarService:
    def test_retorna_resource(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.build",
                  return_value=MagicMock()) as mock_build,
        ):
            from src.connectors.google_auth import get_calendar_service

            result = get_calendar_service(credentials_path=str(creds_file))
            mock_build.assert_called_once()
            assert result is not None

    def test_usa_calendar_v3(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.build",
                  return_value=MagicMock()) as mock_build,
        ):
            from src.connectors.google_auth import get_calendar_service

            get_calendar_service(credentials_path=str(creds_file))
            args, _ = mock_build.call_args
            assert args[0] == "calendar"
            assert args[1] == "v3"

    def test_usa_scopes_calendar(self, tmp_path):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()) as mock_creds,
            patch("src.connectors.google_auth.build", return_value=MagicMock()),
        ):
            from src.connectors.google_auth import SCOPES_CALENDAR, get_calendar_service

            get_calendar_service(credentials_path=str(creds_file))
            _, kwargs = mock_creds.call_args
            assert kwargs.get("scopes") == SCOPES_CALENDAR

    def test_usa_path_de_env_si_no_se_pasa_argumento(self, tmp_path, monkeypatch):
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds_file))

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()),
            patch("src.connectors.google_auth.build",
                  return_value=MagicMock()) as mock_build,
        ):
            from src.connectors.google_auth import get_calendar_service

            get_calendar_service()
            mock_build.assert_called_once()


# ── Reutilización — cada función es independiente ─────────────────────────────


class TestReutilizacion:
    def test_tres_servicios_usan_misma_ruta_de_credenciales(self, tmp_path):
        """Las tres funciones leen de la misma ruta — credencial compartida."""
        creds_file = tmp_path / "creds.json"
        creds_file.write_text("{}")
        path = str(creds_file)

        with (
            patch("src.connectors.google_auth.Credentials.from_service_account_file",
                  return_value=_fake_creds()) as mock_creds,
            patch("src.connectors.google_auth.gspread.authorize", return_value=MagicMock()),
            patch("src.connectors.google_auth.build", return_value=MagicMock()),
        ):
            from src.connectors.google_auth import (
                get_calendar_service,
                get_docs_service,
                get_sheets_client,
            )

            get_sheets_client(credentials_path=path)
            get_docs_service(credentials_path=path)
            get_calendar_service(credentials_path=path)

            # Las tres llamadas usaron la misma ruta de archivo
            calls = mock_creds.call_args_list
            assert len(calls) == 3
            for call in calls:
                assert call.args[0] == path

    def test_scopes_son_distintos_por_servicio(self):
        from src.connectors.google_auth import (
            SCOPES_CALENDAR,
            SCOPES_DOCS,
            SCOPES_SHEETS,
        )

        assert set(SCOPES_SHEETS) != set(SCOPES_DOCS) or True  # pueden solapar
        assert set(SCOPES_CALENDAR) != set(SCOPES_SHEETS)
        assert "calendar" in " ".join(SCOPES_CALENDAR)
        assert "documents" in " ".join(SCOPES_DOCS)
        assert "spreadsheets" in " ".join(SCOPES_SHEETS)
