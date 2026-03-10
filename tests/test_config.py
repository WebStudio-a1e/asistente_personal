"""Tests para src/config.py — T-002."""

import pytest


_LLM_DEFAULTS = {
    "LLM_ORCHESTRATOR": "claude-sonnet-4-6",
    "LLM_TASKS": "gpt-4o",
    "LLM_IDEAS": "claude-sonnet-4-6",
    "LLM_AGENDA": "gemini-2.0-flash",
    "LLM_ACCOUNTING": "gpt-4o",
    "LLM_REPORTING": "claude-sonnet-4-6",
}


def test_config_carga_los_6_llms(monkeypatch):
    """Config carga los 6 LLMs desde variables de entorno."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)

    from src.config import load_config

    cfg = load_config()

    assert cfg.llm_orchestrator == "claude-sonnet-4-6"
    assert cfg.llm_tasks == "gpt-4o"
    assert cfg.llm_ideas == "claude-sonnet-4-6"
    assert cfg.llm_agenda == "gemini-2.0-flash"
    assert cfg.llm_accounting == "gpt-4o"
    assert cfg.llm_reporting == "claude-sonnet-4-6"


def test_config_falla_sin_llm_critico(monkeypatch):
    """Falla con RuntimeError claro si falta LLM_ORCHESTRATOR."""
    for k in _LLM_DEFAULTS:
        monkeypatch.delenv(k, raising=False)

    from src.config import load_config

    with pytest.raises(RuntimeError, match="LLM_ORCHESTRATOR"):
        load_config()


@pytest.mark.parametrize("var", list(_LLM_DEFAULTS.keys()))
def test_config_falla_por_cada_llm_faltante(monkeypatch, var):
    """Falla explícitamente si falta cualquiera de los 6 LLMs."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv(var, raising=False)

    from src.config import load_config

    with pytest.raises(RuntimeError, match=var):
        load_config()


def test_config_carga_api_keys(monkeypatch):
    """Config carga las 4 API keys."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("GOOGLE_GEMINI_API_KEY", "gemini-test")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test")

    from src.config import load_config

    cfg = load_config()

    assert cfg.anthropic_api_key == "sk-ant-test"
    assert cfg.openai_api_key == "sk-openai-test"
    assert cfg.google_gemini_api_key == "gemini-test"
    assert cfg.deepseek_api_key == "deepseek-test"


def test_config_carga_twilio(monkeypatch):
    """Config carga las variables de Twilio."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest123")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token-test")
    monkeypatch.setenv("TWILIO_WHATSAPP_NUMBER", "whatsapp:+14155238886")
    monkeypatch.setenv("TWILIO_WHATSAPP_TO", "whatsapp:+59899000000")

    from src.config import load_config

    cfg = load_config()

    assert cfg.twilio_account_sid == "ACtest123"
    assert cfg.twilio_auth_token == "token-test"
    assert cfg.twilio_whatsapp_number == "whatsapp:+14155238886"
    assert cfg.twilio_whatsapp_to == "whatsapp:+59899000000"


def test_config_carga_google(monkeypatch):
    """Config carga las variables de Google APIs."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("GOOGLE_SHEETS_TASKS_ID", "sheet-tasks-id")
    monkeypatch.setenv("GOOGLE_SHEETS_ACCOUNTING_ID", "sheet-accounting-id")
    monkeypatch.setenv("GOOGLE_DOCS_IDEAS_ID", "docs-ideas-id")
    monkeypatch.setenv("GOOGLE_CALENDAR_ID", "calendar-id")

    from src.config import load_config

    cfg = load_config()

    assert cfg.google_sheets_tasks_id == "sheet-tasks-id"
    assert cfg.google_sheets_accounting_id == "sheet-accounting-id"
    assert cfg.google_docs_ideas_id == "docs-ideas-id"
    assert cfg.google_calendar_id == "calendar-id"


def test_config_carga_app_y_sqlite(monkeypatch):
    """Config carga variables de App y SQLite con defaults correctos."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("APP_PORT", raising=False)
    monkeypatch.delenv("TIMEZONE", raising=False)
    monkeypatch.delenv("SQLITE_DB_PATH", raising=False)

    from src.config import load_config

    cfg = load_config()

    assert cfg.app_env == "development"
    assert cfg.app_port == 8000
    assert cfg.timezone == "America/Montevideo"
    assert cfg.sqlite_db_path == "data/asistente_personal.db"


def test_config_app_port_es_int(monkeypatch):
    """APP_PORT se convierte a int correctamente."""
    for k, v in _LLM_DEFAULTS.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("APP_PORT", "9000")

    from src.config import load_config

    cfg = load_config()

    assert cfg.app_port == 9000
    assert isinstance(cfg.app_port, int)
