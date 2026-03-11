"""Tests T-019 — orchestrator_node: clasificación, ruteo, ambigüedad, multi-intención.

LLM mockeado: no requiere API keys reales.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.graph.state import AgentState


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(json_payload: dict) -> MagicMock:
    """Devuelve un LLM mock cuyo .invoke() retorna content=JSON."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps(json_payload))
    return llm


def _state(message: str) -> AgentState:
    return AgentState(
        message=message,
        intent=None,
        domain=None,
        payload=None,
        confirmation_status=None,
        pending_actions=[],
        agent_response=None,
        conversation_history=[],
        idempotency_key=None,
        error=None,
    )


def _run(message: str, llm_response: dict) -> dict:
    from src.agents.orchestrator import orchestrator_node

    with patch("src.agents.orchestrator.get_llm", return_value=_mock_llm(llm_response)):
        return orchestrator_node(_state(message))


# ── Clasificación de intención y dominio ──────────────────────────────────────


class TestClasificacion:
    def test_intent_task(self):
        result = _run("agregar tarea", {"intent": "task", "domain": "tasks",
                                         "agent_response": None, "pending_actions": []})
        assert result["intent"] == "task"
        assert result["domain"] == "tasks"

    def test_intent_idea(self):
        result = _run("nueva idea", {"intent": "idea", "domain": "ideas",
                                      "agent_response": None, "pending_actions": []})
        assert result["intent"] == "idea"
        assert result["domain"] == "ideas"

    def test_intent_agenda(self):
        result = _run("agendar reunión", {"intent": "agenda", "domain": "agenda",
                                           "agent_response": None, "pending_actions": []})
        assert result["intent"] == "agenda"
        assert result["domain"] == "agenda"

    def test_intent_accounting(self):
        result = _run("gasté 500 en comida", {"intent": "accounting", "domain": "accounting",
                                               "agent_response": None, "pending_actions": []})
        assert result["intent"] == "accounting"
        assert result["domain"] == "accounting"

    def test_intent_query_maps_to_reporting_domain(self):
        result = _run("cuánto gasté este mes", {"intent": "query", "domain": "reporting",
                                                  "agent_response": None, "pending_actions": []})
        assert result["intent"] == "query"
        assert result["domain"] == "reporting"

    def test_intent_unknown(self):
        result = _run("blah blah", {"intent": "unknown", "domain": "unknown",
                                     "agent_response": "¿Qué querés hacer?",
                                     "pending_actions": []})
        assert result["intent"] == "unknown"
        assert result["domain"] == "unknown"


# ── Ambigüedad — pide aclaración ──────────────────────────────────────────────


class TestAmbiguedad:
    def test_ambiguous_sets_agent_response(self):
        result = _run("ayuda", {"intent": "unknown", "domain": "unknown",
                                 "agent_response": "¿En qué te puedo ayudar?",
                                 "pending_actions": []})
        assert result["intent"] == "unknown"
        assert result["agent_response"] is not None
        assert len(result["agent_response"]) > 0

    def test_ambiguous_pending_actions_is_empty(self):
        result = _run("no sé", {"intent": "unknown", "domain": "unknown",
                                 "agent_response": "¿Podés ser más específico?",
                                 "pending_actions": []})
        assert result["pending_actions"] == []

    def test_no_clarification_for_clear_intent(self):
        result = _run("crear tarea comprar pan", {"intent": "task", "domain": "tasks",
                                                   "agent_response": None,
                                                   "pending_actions": []})
        assert result["agent_response"] is None


# ── Multi-intención → pending_actions ─────────────────────────────────────────


class TestMultiIntencion:
    def test_multi_intent_populates_pending_actions(self):
        result = _run(
            "agregar tarea y anotar idea",
            {
                "intent": "task",
                "domain": "tasks",
                "agent_response": None,
                "pending_actions": [
                    {"intent": "task",  "domain": "tasks", "message": "agregar tarea"},
                    {"intent": "idea",  "domain": "ideas", "message": "anotar idea"},
                ],
            },
        )
        assert len(result["pending_actions"]) == 2

    def test_multi_intent_preserves_primary_intent(self):
        result = _run(
            "registrar gasto y agendar reunion",
            {
                "intent": "accounting",
                "domain": "accounting",
                "agent_response": None,
                "pending_actions": [
                    {"intent": "accounting", "domain": "accounting", "message": "registrar gasto"},
                    {"intent": "agenda",     "domain": "agenda",     "message": "agendar reunion"},
                ],
            },
        )
        assert result["intent"] == "accounting"
        assert result["domain"] == "accounting"

    def test_multi_intent_each_action_has_intent_domain_message(self):
        result = _run(
            "dos acciones",
            {
                "intent": "task",
                "domain": "tasks",
                "agent_response": None,
                "pending_actions": [
                    {"intent": "task", "domain": "tasks",  "message": "accion 1"},
                    {"intent": "idea", "domain": "ideas",  "message": "accion 2"},
                ],
            },
        )
        for action in result["pending_actions"]:
            assert "intent" in action
            assert "domain" in action
            assert "message" in action


# ── Ruteo — domain correcto según intent ──────────────────────────────────────


class TestRuteo:
    @pytest.mark.parametrize("intent,expected_domain", [
        ("task",       "tasks"),
        ("idea",       "ideas"),
        ("agenda",     "agenda"),
        ("accounting", "accounting"),
        ("query",      "reporting"),
        ("unknown",    "unknown"),
    ])
    def test_domain_matches_intent(self, intent, expected_domain):
        response = {
            "intent": intent,
            "domain": expected_domain,
            "agent_response": "aclaración" if intent == "unknown" else None,
            "pending_actions": [],
        }
        result = _run("mensaje de prueba", response)
        assert result["domain"] == expected_domain


# ── Resiliencia — parse errors ─────────────────────────────────────────────────


class TestResiliencia:
    def test_invalid_json_returns_unknown(self):
        from src.agents.orchestrator import orchestrator_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="esto no es json")
        with patch("src.agents.orchestrator.get_llm", return_value=llm):
            result = orchestrator_node(_state("test"))
        assert result["intent"] == "unknown"
        assert result["domain"] == "unknown"
        assert result["agent_response"] is not None

    def test_empty_content_returns_unknown(self):
        from src.agents.orchestrator import orchestrator_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="")
        with patch("src.agents.orchestrator.get_llm", return_value=llm):
            result = orchestrator_node(_state("test"))
        assert result["intent"] == "unknown"

    def test_markdown_fences_are_stripped(self):
        from src.agents.orchestrator import orchestrator_node

        payload = {"intent": "task", "domain": "tasks",
                   "agent_response": None, "pending_actions": []}
        content = f"```json\n{json.dumps(payload)}\n```"
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=content)
        with patch("src.agents.orchestrator.get_llm", return_value=llm):
            result = orchestrator_node(_state("test"))
        assert result["intent"] == "task"

    def test_result_always_has_required_keys(self):
        from src.agents.orchestrator import orchestrator_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="{}")
        with patch("src.agents.orchestrator.get_llm", return_value=llm):
            result = orchestrator_node(_state("test"))
        for key in ("intent", "domain", "agent_response", "pending_actions"):
            assert key in result

    def test_llm_is_called_with_message(self):
        from src.agents.orchestrator import orchestrator_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(
            content=json.dumps({"intent": "task", "domain": "tasks",
                                "agent_response": None, "pending_actions": []})
        )
        with patch("src.agents.orchestrator.get_llm", return_value=llm):
            orchestrator_node(_state("mi mensaje específico"))
        llm.invoke.assert_called_once()
        call_args = llm.invoke.call_args[0][0]
        # El mensaje del usuario debe estar en el prompt
        assert any("mi mensaje específico" in str(part) for part in call_args)
