"""Smoke tests — T-004.

Verifican que el entorno base está operativo:
- GET /health responde 200
- config carga los 6 LLMs desde variables de entorno reales
- app FastAPI arranca e importa correctamente
"""

from fastapi.testclient import TestClient


def test_smoke_health_200():
    """GET /health responde 200."""
    from src.main import app

    response = TestClient(app).get("/health")
    assert response.status_code == 200


def test_smoke_health_body():
    """GET /health retorna {"status": "ok"}."""
    from src.main import app

    response = TestClient(app).get("/health")
    assert response.json() == {"status": "ok"}


def test_smoke_config_carga_6_llms():
    """Config carga los 6 LLMs desde variables de entorno reales (sin mocks)."""
    from src.config import load_config

    cfg = load_config()

    assert cfg.llm_orchestrator, "LLM_ORCHESTRATOR vacío"
    assert cfg.llm_tasks, "LLM_TASKS vacío"
    assert cfg.llm_ideas, "LLM_IDEAS vacío"
    assert cfg.llm_agenda, "LLM_AGENDA vacío"
    assert cfg.llm_accounting, "LLM_ACCOUNTING vacío"
    assert cfg.llm_reporting, "LLM_REPORTING vacío"


def test_smoke_app_arranca():
    """La app FastAPI importa y tiene los atributos esperados."""
    from src.main import app

    assert app is not None
    assert app.title == "asistente_personal"
