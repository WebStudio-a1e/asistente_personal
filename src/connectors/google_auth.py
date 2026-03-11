"""Autenticación Google — service account reutilizable para Sheets, Docs y Calendar.

Todas las funciones leen el mismo archivo de credenciales (GOOGLE_CREDENTIALS_PATH).
Las credenciales son de tipo service account (JSON descargado desde Google Cloud Console).

Uso:
    from src.connectors.google_auth import get_sheets_client, get_docs_service, get_calendar_service

    client   = get_sheets_client()          # gspread.Client
    docs     = get_docs_service()           # Resource de Google Docs API v1
    calendar = get_calendar_service()       # Resource de Google Calendar API v3
"""

import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

# ── Scopes por servicio ───────────────────────────────────────

SCOPES_SHEETS: list[str] = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

SCOPES_DOCS: list[str] = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

SCOPES_CALENDAR: list[str] = [
    "https://www.googleapis.com/auth/calendar",
]


# ── Helper interno ────────────────────────────────────────────

def _default_credentials_path() -> str:
    return os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials/google_credentials.json")


def _load_credentials(credentials_path: str, scopes: list[str]) -> Credentials:
    """Carga las credenciales de service account desde el archivo JSON.

    Raises:
        FileNotFoundError: si el archivo de credenciales no existe.
    """
    path = Path(credentials_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Archivo de credenciales Google no encontrado: {credentials_path}\n"
            "Copiá el JSON de tu service account a esa ruta antes de usar los conectores."
        )
    return Credentials.from_service_account_file(str(path), scopes=scopes)


# ── API pública ───────────────────────────────────────────────

def get_sheets_client(credentials_path: str | None = None) -> gspread.Client:
    """Retorna un cliente gspread autenticado para Google Sheets.

    Args:
        credentials_path: ruta al JSON de service account.
                          Si es None usa GOOGLE_CREDENTIALS_PATH.

    Returns:
        gspread.Client listo para abrir spreadsheets.

    Raises:
        FileNotFoundError: si el archivo de credenciales no existe.
    """
    path = credentials_path or _default_credentials_path()
    creds = _load_credentials(path, SCOPES_SHEETS)
    return gspread.authorize(creds)


def get_docs_service(credentials_path: str | None = None):
    """Retorna un Resource de Google Docs API v1 autenticado.

    Args:
        credentials_path: ruta al JSON de service account.
                          Si es None usa GOOGLE_CREDENTIALS_PATH.

    Returns:
        googleapiclient Resource para Google Docs API v1.

    Raises:
        FileNotFoundError: si el archivo de credenciales no existe.
    """
    path = credentials_path or _default_credentials_path()
    creds = _load_credentials(path, SCOPES_DOCS)
    return build("docs", "v1", credentials=creds)


def get_calendar_service(credentials_path: str | None = None):
    """Retorna un Resource de Google Calendar API v3 autenticado.

    Args:
        credentials_path: ruta al JSON de service account.
                          Si es None usa GOOGLE_CREDENTIALS_PATH.

    Returns:
        googleapiclient Resource para Google Calendar API v3.

    Raises:
        FileNotFoundError: si el archivo de credenciales no existe.
    """
    path = credentials_path or _default_credentials_path()
    creds = _load_credentials(path, SCOPES_CALENDAR)
    return build("calendar", "v3", credentials=creds)
