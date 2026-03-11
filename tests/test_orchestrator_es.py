"""Tests T-019 — orchestrator_node: frases en español por dominio.

Verifica que el orquestador clasifica correctamente frases típicas del
usuario en español, usando respuestas LLM mockeadas representativas.

LLM mockeado: no requiere API keys reales.
"""

import json
from unittest.mock import MagicMock, patch

from src.graph.state import AgentState


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(json_payload: dict) -> MagicMock:
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


def _task_resp(**kw) -> dict:
    return {"intent": "task", "domain": "tasks", "agent_response": None,
            "pending_actions": [], **kw}


def _idea_resp(**kw) -> dict:
    return {"intent": "idea", "domain": "ideas", "agent_response": None,
            "pending_actions": [], **kw}


def _agenda_resp(**kw) -> dict:
    return {"intent": "agenda", "domain": "agenda", "agent_response": None,
            "pending_actions": [], **kw}


def _accounting_resp(**kw) -> dict:
    return {"intent": "accounting", "domain": "accounting", "agent_response": None,
            "pending_actions": [], **kw}


def _query_resp(**kw) -> dict:
    return {"intent": "query", "domain": "reporting", "agent_response": None,
            "pending_actions": [], **kw}


def _unknown_resp(clarification: str) -> dict:
    return {"intent": "unknown", "domain": "unknown",
            "agent_response": clarification, "pending_actions": []}


# ── Tareas ────────────────────────────────────────────────────────────────────


class TestFrasesTask:
    def test_agregar_tarea(self):
        r = _run("Agregá una tarea: revisar el informe", _task_resp())
        assert r["intent"] == "task" and r["domain"] == "tasks"

    def test_nueva_tarea(self):
        r = _run("Nueva tarea: llamar al cliente", _task_resp())
        assert r["intent"] == "task"

    def test_mover_tarea(self):
        r = _run("Mové la tarea 'informe' a en progreso", _task_resp())
        assert r["domain"] == "tasks"

    def test_completar_tarea(self):
        r = _run("Marcá como completada la tarea de compras", _task_resp())
        assert r["intent"] == "task"

    def test_ver_tareas(self):
        r = _run("¿Qué tareas tengo pendientes?", _task_resp())
        assert r["intent"] == "task"


# ── Ideas ─────────────────────────────────────────────────────────────────────


class TestFrasesIdea:
    def test_anotar_idea(self):
        r = _run("Anotá esta idea: aplicación de recetas", _idea_resp())
        assert r["intent"] == "idea" and r["domain"] == "ideas"

    def test_nueva_nota(self):
        r = _run("Guardá esta nota: contactar a Juan por el proyecto", _idea_resp())
        assert r["intent"] == "idea"

    def test_ver_ideas(self):
        r = _run("¿Qué ideas tengo sobre marketing?", _idea_resp())
        assert r["domain"] == "ideas"


# ── Agenda ────────────────────────────────────────────────────────────────────


class TestFrasesAgenda:
    def test_agendar_reunion(self):
        r = _run("Agendá una reunión el viernes a las 10", _agenda_resp())
        assert r["intent"] == "agenda" and r["domain"] == "agenda"

    def test_recordatorio(self):
        r = _run("Poné un recordatorio mañana a las 9 para llamar al médico", _agenda_resp())
        assert r["intent"] == "agenda"

    def test_cancelar_evento(self):
        r = _run("Cancelá la reunión del lunes", _agenda_resp())
        assert r["domain"] == "agenda"

    def test_ver_agenda(self):
        r = _run("¿Qué tengo en la agenda esta semana?", _agenda_resp())
        assert r["intent"] == "agenda"


# ── Contabilidad ──────────────────────────────────────────────────────────────


class TestFrasesAccounting:
    def test_registrar_gasto(self):
        r = _run("Gasté 1500 pesos en el supermercado", _accounting_resp())
        assert r["intent"] == "accounting" and r["domain"] == "accounting"

    def test_registrar_ingreso(self):
        r = _run("Ingresaron 50000 de factura cliente X", _accounting_resp())
        assert r["intent"] == "accounting"

    def test_ver_gastos(self):
        r = _run("¿Cuánto gasté esta semana?", _accounting_resp())
        assert r["domain"] == "accounting"


# ── Consultas complejas ───────────────────────────────────────────────────────


class TestFrasesQuery:
    def test_consulta_cruzada(self):
        r = _run("¿Cuánto gasté en comida este mes vs el mes pasado?", _query_resp())
        assert r["intent"] == "query" and r["domain"] == "reporting"

    def test_resumen_semanal(self):
        r = _run("Dame un resumen de la semana", _query_resp())
        assert r["intent"] == "query"

    def test_productividad(self):
        r = _run("¿Cuántas tareas completé esta semana?", _query_resp())
        assert r["domain"] == "reporting"


# ── Ambigüedad — aclaración en español ───────────────────────────────────────


class TestAmbiguedadEspanol:
    def test_clarification_is_string(self):
        r = _run("quiero hacer algo", _unknown_resp("¿Qué querés hacer exactamente?"))
        assert isinstance(r["agent_response"], str)

    def test_clarification_not_empty(self):
        r = _run("mmm", _unknown_resp("¿Podés contarme más?"))
        assert len(r["agent_response"]) > 0

    def test_out_of_domain_returns_unknown(self):
        r = _run("¿Cuál es la capital de Francia?",
                 _unknown_resp("Solo puedo ayudarte con tareas, ideas, agenda y contabilidad."))
        assert r["intent"] == "unknown"
        assert r["agent_response"] is not None


# ── Multi-intención en español ────────────────────────────────────────────────


class TestMultiIntencionEspanol:
    def test_tarea_y_gasto(self):
        r = _run(
            "Agregá una tarea y registrá un gasto de 200",
            {
                "intent": "task",
                "domain": "tasks",
                "agent_response": None,
                "pending_actions": [
                    {"intent": "task",       "domain": "tasks",       "message": "Agregá una tarea"},
                    {"intent": "accounting", "domain": "accounting",  "message": "registrá un gasto de 200"},
                ],
            },
        )
        assert len(r["pending_actions"]) == 2
        intents = {a["intent"] for a in r["pending_actions"]}
        assert "task" in intents
        assert "accounting" in intents

    def test_idea_y_reunion(self):
        r = _run(
            "Anotá una idea y agendá una reunión",
            {
                "intent": "idea",
                "domain": "ideas",
                "agent_response": None,
                "pending_actions": [
                    {"intent": "idea",   "domain": "ideas",  "message": "Anotá una idea"},
                    {"intent": "agenda", "domain": "agenda", "message": "agendá una reunión"},
                ],
            },
        )
        assert len(r["pending_actions"]) == 2

    def test_single_intent_has_empty_pending_actions(self):
        r = _run("Agregá tarea", _task_resp())
        assert r["pending_actions"] == []
