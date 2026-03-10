"""Tests para src/graph/llm_factory.py — T-015.

Todos los tests usan mocks — no se instancian LLMs reales
ni se requieren API keys válidas.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.graph.llm_factory import get_llm


# ── Mapeo completo de agentes con sus modelos y clases esperadas ─────────────

_CASOS = [
    ("orchestrator", "claude-sonnet-4-6", "src.graph.llm_factory.ChatAnthropic"),
    ("tasks",        "gpt-4o",            "src.graph.llm_factory.ChatOpenAI"),
    ("ideas",        "claude-sonnet-4-6", "src.graph.llm_factory.ChatAnthropic"),
    ("agenda",       "gemini-2.0-flash",  "src.graph.llm_factory.ChatGoogleGenerativeAI"),
    ("accounting",   "gpt-4o",            "src.graph.llm_factory.ChatOpenAI"),
    ("reporting",    "claude-sonnet-4-6", "src.graph.llm_factory.ChatAnthropic"),
]


@pytest.mark.parametrize("agent,model,target", _CASOS)
def test_get_llm_retorna_clase_correcta(monkeypatch, agent, model, target):
    """get_llm retorna la clase LLM correcta para cada agente."""
    monkeypatch.setenv(f"LLM_{agent.upper()}", model)
    with patch(target) as MockLLM:
        MockLLM.return_value = MagicMock(name=f"mock_{agent}")
        result = get_llm(agent)
        assert MockLLM.called
        assert result is MockLLM.return_value


# ── Claude ────────────────────────────────────────────────────────────────────

def test_get_llm_claude_llama_con_model(monkeypatch):
    """ChatAnthropic se instancia con el model correcto."""
    monkeypatch.setenv("LLM_ORCHESTRATOR", "claude-sonnet-4-6")
    with patch("src.graph.llm_factory.ChatAnthropic") as MockClaude:
        MockClaude.return_value = MagicMock()
        get_llm("orchestrator")
        MockClaude.assert_called_once_with(model="claude-sonnet-4-6")


# ── GPT ───────────────────────────────────────────────────────────────────────

def test_get_llm_gpt_llama_con_model(monkeypatch):
    """ChatOpenAI se instancia con el model correcto."""
    monkeypatch.setenv("LLM_TASKS", "gpt-4o")
    with patch("src.graph.llm_factory.ChatOpenAI") as MockOpenAI:
        MockOpenAI.return_value = MagicMock()
        get_llm("tasks")
        MockOpenAI.assert_called_once_with(model="gpt-4o")


# ── Gemini ────────────────────────────────────────────────────────────────────

def test_get_llm_gemini_llama_con_model(monkeypatch):
    """ChatGoogleGenerativeAI se instancia con el model correcto."""
    monkeypatch.setenv("LLM_AGENDA", "gemini-2.0-flash")
    with patch("src.graph.llm_factory.ChatGoogleGenerativeAI") as MockGemini:
        MockGemini.return_value = MagicMock()
        get_llm("agenda")
        MockGemini.assert_called_once_with(model="gemini-2.0-flash")


# ── DeepSeek ──────────────────────────────────────────────────────────────────

def test_get_llm_deepseek_usa_base_url(monkeypatch):
    """deepseek-* usa ChatOpenAI con base_url apuntando a DeepSeek."""
    monkeypatch.setenv("LLM_TASKS", "deepseek-chat")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-test-key")
    with patch("src.graph.llm_factory.ChatOpenAI") as MockOpenAI:
        MockOpenAI.return_value = MagicMock()
        get_llm("tasks")
        kwargs = MockOpenAI.call_args.kwargs
        assert kwargs["model"] == "deepseek-chat"
        assert "deepseek.com" in kwargs["base_url"]


# ── Casos de error ────────────────────────────────────────────────────────────

def test_get_llm_agente_desconocido():
    """ValueError para agente no registrado."""
    with pytest.raises(ValueError, match="Agente desconocido"):
        get_llm("agente_inventado")


def test_get_llm_env_var_faltante(monkeypatch):
    """RuntimeError si la variable de entorno no está definida."""
    monkeypatch.delenv("LLM_ORCHESTRATOR", raising=False)
    with pytest.raises(RuntimeError, match="LLM_ORCHESTRATOR"):
        get_llm("orchestrator")


def test_get_llm_modelo_no_soportado(monkeypatch):
    """ValueError para prefijo de modelo no reconocido."""
    monkeypatch.setenv("LLM_ORCHESTRATOR", "llama-3-70b")
    with pytest.raises(ValueError, match="no soportado"):
        get_llm("orchestrator")
