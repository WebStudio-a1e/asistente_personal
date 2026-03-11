"""Tests T-032 — reporting_agent: tipos de consulta específicos.

Cubre los 4 tipos de query definidos en done_when:
- Gastos por categoría.
- Gastos por período / resumen contable.
- "Qué tengo hoy" (agenda + tareas activas).
- Productividad de tareas (completadas vs pendientes).
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from src.agents.reporting_agent import _build_context, reporting_agent_node


# ── Helpers ───────────────────────────────────────────────────────────────────

_MVD_TZ = timezone(timedelta(hours=-3))


def _mock_llm(text: str = "Respuesta.") -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=text)
    return llm


def _run(
    message: str,
    tasks: list = None,
    ideas: list = None,
    events: list = None,
    accounting: list = None,
    llm_text: str = "Respuesta.",
) -> dict:
    with (
        patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm(llm_text)),
        patch("src.agents.reporting_agent._fetch_tasks", return_value=tasks or []),
        patch("src.agents.reporting_agent._fetch_ideas", return_value=ideas or []),
        patch("src.agents.reporting_agent._fetch_events", return_value=events or []),
        patch("src.agents.reporting_agent._fetch_accounting", return_value=accounting or []),
    ):
        return reporting_agent_node({"message": message, "pending_actions": [], "conversation_history": []})


# ── Fixtures de datos ─────────────────────────────────────────────────────────

_ACCOUNTING_ENTRIES = [
    {"id": "A1", "type": "expense", "category": "Comida",    "amount": 500.0,  "date": "2024-06-01T12:00:00-03:00", "note": "Almuerzo"},
    {"id": "A2", "type": "expense", "category": "Comida",    "amount": 300.0,  "date": "2024-06-03T12:00:00-03:00", "note": "Cena"},
    {"id": "A3", "type": "expense", "category": "Transporte","amount": 150.0,  "date": "2024-06-02T08:00:00-03:00", "note": "Bus"},
    {"id": "A4", "type": "income",  "category": "Salario",   "amount": 50000.0,"date": "2024-06-05T09:00:00-03:00", "note": "Sueldo junio"},
    {"id": "A5", "type": "expense", "category": "Comida",    "amount": 200.0,  "date": "2024-05-28T12:00:00-03:00", "note": "Almuerzo mayo"},
]

_TASKS = [
    {"id": "T1", "title": "Revisar PR",       "status": "pending"},
    {"id": "T2", "title": "Deploy a prod",    "status": "in_progress"},
    {"id": "T3", "title": "Escribir tests",   "status": "today"},
    {"id": "T4", "title": "Refactor módulo",  "status": "completed"},
    {"id": "T5", "title": "Actualizar docs",  "status": "completed"},
    {"id": "T6", "title": "Reunión equipo",   "status": "pending"},
]

_TODAY = datetime.now(tz=_MVD_TZ).strftime("%Y-%m-%d")

_EVENTS_TODAY = [
    {
        "id": "E1",
        "title": "Reunión semanal",
        "scheduled_for": f"{_TODAY}T10:00:00-03:00",
        "status": "active",
    },
    {
        "id": "E2",
        "title": "Dentista",
        "scheduled_for": f"{_TODAY}T15:00:00-03:00",
        "status": "active",
    },
]

_EVENTS_FUTURE = [
    {
        "id": "E3",
        "title": "Conferencia",
        "scheduled_for": "2099-12-01T09:00:00-03:00",
        "status": "active",
    },
]


# ── Gastos por categoría ──────────────────────────────────────────────────────


class TestGastosPorCategoria:
    def test_contexto_contiene_categorias(self):
        ctx = _build_context([], [], [], _ACCOUNTING_ENTRIES)
        assert "Comida" in ctx
        assert "Transporte" in ctx
        assert "Salario" in ctx

    def test_contexto_contiene_montos(self):
        ctx = _build_context([], [], [], _ACCOUNTING_ENTRIES)
        assert "500" in ctx
        assert "300" in ctx
        assert "150" in ctx

    def test_agent_recibe_datos_contables_en_prompt(self):
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()) as mock_get_llm,
            patch("src.agents.reporting_agent._fetch_tasks", return_value=[]),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=[]),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=_ACCOUNTING_ENTRIES),
        ):
            reporting_agent_node({"message": "¿Cuánto gasté en comida?", "pending_actions": [], "conversation_history": []})

        human_msg = mock_get_llm.return_value.invoke.call_args.args[0][1][1]
        assert "Comida" in human_msg

    def test_query_gastos_categoria_retorna_agent_response(self):
        updates = _run(
            "¿Cuánto gasté en comida este mes?",
            accounting=_ACCOUNTING_ENTRIES,
            llm_text="Gastaste $800 en Comida en junio.",
        )
        assert updates["agent_response"] == "Gastaste $800 en Comida en junio."

    def test_contexto_incluye_tipo_expense_e_income(self):
        ctx = _build_context([], [], [], _ACCOUNTING_ENTRIES)
        assert "expense" in ctx
        assert "income" in ctx


# ── Resumen contable ──────────────────────────────────────────────────────────


class TestResumenContable:
    def test_contexto_contiene_todos_los_movimientos(self):
        ctx = _build_context([], [], [], _ACCOUNTING_ENTRIES)
        for entry in _ACCOUNTING_ENTRIES:
            assert entry["note"] in ctx

    def test_query_resumen_semanal_retorna_response(self):
        updates = _run(
            "Resumime los gastos de esta semana",
            accounting=_ACCOUNTING_ENTRIES,
            llm_text="Esta semana: $950 en egresos.",
        )
        assert "agent_response" in updates
        assert updates["agent_response"] == "Esta semana: $950 en egresos."

    def test_query_resumen_mensual_retorna_response(self):
        updates = _run(
            "¿Cuánto gasté en junio?",
            accounting=_ACCOUNTING_ENTRIES,
            llm_text="En junio: $950 en egresos, $50.000 en ingresos.",
        )
        assert "agent_response" in updates

    def test_resumen_sin_datos_responde_sin_error(self):
        updates = _run("Resumime la contabilidad", accounting=[])
        assert "agent_response" in updates

    def test_contexto_vacio_no_falla(self):
        ctx = _build_context([], [], [], [])
        assert ctx == "No hay datos disponibles."


# ── Qué tengo hoy ─────────────────────────────────────────────────────────────


class TestQueTengoHoy:
    def test_contexto_contiene_eventos_de_hoy(self):
        ctx = _build_context([], [], _EVENTS_TODAY, [])
        assert "Reunión semanal" in ctx
        assert "Dentista" in ctx

    def test_contexto_contiene_tareas_activas(self):
        ctx = _build_context(_TASKS, [], [], [])
        assert "Revisar PR" in ctx
        assert "Deploy a prod" in ctx
        assert "Escribir tests" in ctx

    def test_query_hoy_retorna_response(self):
        updates = _run(
            "¿Qué tengo para hoy?",
            tasks=_TASKS,
            events=_EVENTS_TODAY,
            llm_text="Hoy tenés 2 eventos y 3 tareas activas.",
        )
        assert updates["agent_response"] == "Hoy tenés 2 eventos y 3 tareas activas."

    def test_contexto_incluye_tareas_y_agenda_juntas(self):
        ctx = _build_context(_TASKS, [], _EVENTS_TODAY, [])
        assert "TAREAS" in ctx
        assert "AGENDA" in ctx

    def test_agent_recibe_eventos_y_tareas_en_prompt(self):
        with (
            patch("src.agents.reporting_agent.get_llm", return_value=_mock_llm()) as mock_get_llm,
            patch("src.agents.reporting_agent._fetch_tasks", return_value=_TASKS),
            patch("src.agents.reporting_agent._fetch_ideas", return_value=[]),
            patch("src.agents.reporting_agent._fetch_events", return_value=_EVENTS_TODAY),
            patch("src.agents.reporting_agent._fetch_accounting", return_value=[]),
        ):
            reporting_agent_node({"message": "¿Qué tengo hoy?", "pending_actions": [], "conversation_history": []})

        human_msg = mock_get_llm.return_value.invoke.call_args.args[0][1][1]
        assert "Reunión semanal" in human_msg
        assert "Revisar PR" in human_msg

    def test_sin_eventos_ni_tareas_responde_sin_error(self):
        updates = _run("¿Qué tengo hoy?", tasks=[], events=[])
        assert "agent_response" in updates


# ── Productividad de tareas ───────────────────────────────────────────────────


class TestProductividadTareas:
    def test_contexto_incluye_tareas_completadas(self):
        ctx = _build_context(_TASKS, [], [], [])
        assert "completed" in ctx
        assert "Refactor módulo" in ctx
        assert "Actualizar docs" in ctx

    def test_contexto_incluye_tareas_pendientes(self):
        ctx = _build_context(_TASKS, [], [], [])
        assert "pending" in ctx
        assert "Revisar PR" in ctx

    def test_contexto_incluye_tareas_en_progreso(self):
        ctx = _build_context(_TASKS, [], [], [])
        assert "in_progress" in ctx
        assert "Deploy a prod" in ctx

    def test_query_productividad_retorna_response(self):
        updates = _run(
            "¿Cuántas tareas completé esta semana?",
            tasks=_TASKS,
            llm_text="Completaste 2 tareas. Tenés 3 pendientes.",
        )
        assert updates["agent_response"] == "Completaste 2 tareas. Tenés 3 pendientes."

    def test_query_productividad_con_tareas_vacias(self):
        updates = _run("¿Cuál es mi productividad?", tasks=[])
        assert "agent_response" in updates

    def test_todos_los_estados_presentes_en_contexto(self):
        ctx = _build_context(_TASKS, [], [], [])
        for status in ("pending", "in_progress", "today", "completed"):
            assert status in ctx
