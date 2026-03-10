"""Configuración centralizada — carga todas las variables de entorno.

Variables críticas (LLMs): el sistema no arranca si falta alguna.
Variables operativas: opcionales con defaults razonables.
"""

import os
from dataclasses import dataclass

# Variables LLM — críticas: la app no puede funcionar sin ellas
_LLM_VARS = [
    "LLM_ORCHESTRATOR",
    "LLM_TASKS",
    "LLM_IDEAS",
    "LLM_AGENDA",
    "LLM_ACCOUNTING",
    "LLM_REPORTING",
]


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Variable de entorno requerida no definida o vacía: {name}"
        )
    return value


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Config:
    # ── LLMs por agente ──────────────────────────────────────────
    llm_orchestrator: str
    llm_tasks: str
    llm_ideas: str
    llm_agenda: str
    llm_accounting: str
    llm_reporting: str

    # ── API Keys — LLM providers ─────────────────────────────────
    anthropic_api_key: str
    openai_api_key: str
    google_gemini_api_key: str
    deepseek_api_key: str

    # ── Twilio — WhatsApp ────────────────────────────────────────
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_whatsapp_number: str
    twilio_whatsapp_to: str

    # ── Google APIs ───────────────────────────────────────────────
    google_credentials_path: str
    google_sheets_tasks_id: str
    google_sheets_accounting_id: str
    google_docs_ideas_id: str
    google_calendar_id: str
    google_drive_root_folder_id: str

    # ── App ───────────────────────────────────────────────────────
    app_env: str
    app_host: str
    app_port: int
    timezone: str
    log_level: str

    # ── SQLite ────────────────────────────────────────────────────
    sqlite_db_path: str


def load_config() -> Config:
    """Carga y valida la configuración desde variables de entorno.

    Falla con RuntimeError explícito si falta alguna variable LLM crítica.
    Las demás variables son opcionales y tienen defaults razonables.
    """
    for var in _LLM_VARS:
        _require(var)

    return Config(
        # LLMs
        llm_orchestrator=_require("LLM_ORCHESTRATOR"),
        llm_tasks=_require("LLM_TASKS"),
        llm_ideas=_require("LLM_IDEAS"),
        llm_agenda=_require("LLM_AGENDA"),
        llm_accounting=_require("LLM_ACCOUNTING"),
        llm_reporting=_require("LLM_REPORTING"),
        # API Keys
        anthropic_api_key=_get("ANTHROPIC_API_KEY"),
        openai_api_key=_get("OPENAI_API_KEY"),
        google_gemini_api_key=_get("GOOGLE_GEMINI_API_KEY"),
        deepseek_api_key=_get("DEEPSEEK_API_KEY"),
        # Twilio
        twilio_account_sid=_get("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=_get("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_number=_get(
            "TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886"
        ),
        twilio_whatsapp_to=_get("TWILIO_WHATSAPP_TO"),
        # Google
        google_credentials_path=_get(
            "GOOGLE_CREDENTIALS_PATH", "credentials/google_credentials.json"
        ),
        google_sheets_tasks_id=_get("GOOGLE_SHEETS_TASKS_ID"),
        google_sheets_accounting_id=_get("GOOGLE_SHEETS_ACCOUNTING_ID"),
        google_docs_ideas_id=_get("GOOGLE_DOCS_IDEAS_ID"),
        google_calendar_id=_get("GOOGLE_CALENDAR_ID"),
        google_drive_root_folder_id=_get("GOOGLE_DRIVE_ROOT_FOLDER_ID"),
        # App
        app_env=_get("APP_ENV", "development"),
        app_host=_get("APP_HOST", "0.0.0.0"),
        app_port=int(_get("APP_PORT", "8000")),
        timezone=_get("TIMEZONE", "America/Montevideo"),
        log_level=_get("LOG_LEVEL", "INFO"),
        # SQLite
        sqlite_db_path=_get("SQLITE_DB_PATH", "data/asistente_personal.db"),
    )
