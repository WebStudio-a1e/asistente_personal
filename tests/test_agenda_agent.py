"""Tests T-024 — agenda_agent + calendar_client.

Sin credenciales reales: todas las llamadas a LLM y Calendar API están mockeadas.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, call, patch

import pytest

_MVD_TZ = timezone(timedelta(hours=-3))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(payload: dict) -> MagicMock:
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps(payload))
    return llm


def _fake_api_event(
    event_id: str = "cal-1",
    title: str = "Reunión",
    scheduled_for: str = "2024-06-01T10:00:00-03:00",
    recurrence: list | None = None,
    notes: str = "",
    source: str = "whatsapp",
    status: str = "active",
) -> dict:
    """Simula respuesta de la Calendar API."""
    return {
        "id": event_id,
        "summary": title,
        "description": notes,
        "start": {"dateTime": scheduled_for, "timeZone": "America/Montevideo"},
        "end":   {"dateTime": scheduled_for, "timeZone": "America/Montevideo"},
        "recurrence": recurrence or [],
        "extendedProperties": {
            "private": {
                "ap_source": source,
                "ap_status": status,
            }
        },
    }


def _make_service(events_list: list | None = None, created_id: str = "new-id") -> MagicMock:
    """Crea mock del servicio Calendar con respuestas configurables."""
    service = MagicMock()
    events_resource = service.events.return_value

    # list
    events_resource.list.return_value.execute.return_value = {
        "items": events_list or []
    }
    # insert
    events_resource.insert.return_value.execute.return_value = {"id": created_id}
    # get (para update/cancel)
    events_resource.get.return_value.execute.return_value = _fake_api_event()
    # patch
    events_resource.patch.return_value.execute.return_value = {}

    return service


# ── agenda_agent_node ─────────────────────────────────────────────────────────


class TestAgendaAgentNode:
    def test_retorna_payload_con_campos_canonicos(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "Reunión de equipo",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": 90,
            "recurrence": None,
            "notes": "Traer laptop",
            "agent_response": "Voy a crear el evento.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "reunión mañana a las 10"})

        assert result["payload"]["operation"] == "create"
        assert result["payload"]["title"] == "Reunión de equipo"
        assert result["payload"]["scheduled_for"] == "2024-06-01T10:00:00-03:00"
        assert result["payload"]["duration_minutes"] == 90
        assert result["payload"]["notes"] == "Traer laptop"

    def test_genera_event_id_si_llm_devuelve_null(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "Dentista",
            "scheduled_for": "2024-06-02T09:00:00-03:00",
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Creando cita.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "dentista el jueves"})

        assert len(result["payload"]["event_id"]) == 36  # UUID

    def test_default_duration_60_minutos(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "evento"})

        assert result["payload"]["duration_minutes"] == 60

    def test_confirmation_status_es_detected(self):
        from src.agents.agenda_agent import agenda_agent_node
        from src.domain.confirmation import ConfirmationStatus

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": None,
            "notes": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "evento"})

        assert result["confirmation_status"] == ConfirmationStatus.DETECTED

    def test_recurrencia_propagada(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "Gym",
            "scheduled_for": "2024-06-03T07:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
            "notes": None,
            "agent_response": "Creando evento semanal.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "gym lunes miércoles viernes"})

        assert result["payload"]["recurrence"] == "FREQ=WEEKLY;BYDAY=MO,WE,FR"

    def test_timezone_en_payload(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "read",
            "event_id": None,
            "title": None,
            "scheduled_for": None,
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Listando eventos.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "qué tengo hoy"})

        assert result["payload"]["timezone"] == "America/Montevideo"

    def test_source_es_whatsapp(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": None,
            "notes": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "evento"})

        assert result["payload"]["source"] == "whatsapp"

    def test_status_por_defecto_active(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "create",
            "event_id": None,
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": 60,
            "recurrence": None,
            "notes": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = agenda_agent_node({"message": "evento"})

        assert result["payload"]["status"] == "active"

    def test_parse_error_usa_defaults(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="no es json")

        with patch("src.agents.agenda_agent.get_llm", return_value=llm):
            result = agenda_agent_node({"message": "algo"})

        assert result["payload"]["operation"] == "create"
        assert result["payload"]["duration_minutes"] == 60

    def test_markdown_fence_stripping(self):
        from src.agents.agenda_agent import agenda_agent_node

        inner = {
            "operation": "cancel",
            "event_id": "ev-abc",
            "title": None,
            "scheduled_for": None,
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Cancelando.",
        }
        fenced = f"```json\n{json.dumps(inner)}\n```"
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=fenced)

        with patch("src.agents.agenda_agent.get_llm", return_value=llm):
            result = agenda_agent_node({"message": "cancela evento ev-abc"})

        assert result["payload"]["operation"] == "cancel"
        assert result["payload"]["event_id"] == "ev-abc"

    def test_usa_llm_agenda(self):
        from src.agents.agenda_agent import agenda_agent_node

        llm_data = {
            "operation": "read",
            "event_id": None,
            "title": None,
            "scheduled_for": None,
            "duration_minutes": None,
            "recurrence": None,
            "notes": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.agenda_agent.get_llm", return_value=_mock_llm(llm_data)) as mock_get:
            agenda_agent_node({"message": "eventos"})
            mock_get.assert_called_once_with("agenda")


# ── calendar_client — _to_mvd_dt ──────────────────────────────────────────────


class TestToMvdDt:
    def test_naive_dt_obtiene_offset_utc3(self):
        from src.connectors.calendar_client import _to_mvd_dt

        dt = _to_mvd_dt("2024-06-01T10:00:00")
        assert dt.utcoffset() == timedelta(hours=-3)

    def test_aware_dt_se_convierte_a_utc3(self):
        from src.connectors.calendar_client import _to_mvd_dt

        dt = _to_mvd_dt("2024-06-01T13:00:00+00:00")  # UTC → UTC-3 = 10:00
        assert dt.hour == 10
        assert dt.utcoffset() == timedelta(hours=-3)

    def test_ya_es_utc3_sin_cambio(self):
        from src.connectors.calendar_client import _to_mvd_dt

        dt = _to_mvd_dt("2024-06-01T10:00:00-03:00")
        assert dt.hour == 10
        assert dt.utcoffset() == timedelta(hours=-3)


# ── calendar_client — _build_event_body ───────────────────────────────────────


class TestBuildEventBody:
    def test_incluye_summary_y_times(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "Dentista",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": 30,
        })
        assert body["summary"] == "Dentista"
        assert "dateTime" in body["start"]
        assert "dateTime" in body["end"]
        assert body["start"]["timeZone"] == "America/Montevideo"

    def test_end_es_start_mas_duracion(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "duration_minutes": 90,
        })
        start = datetime.fromisoformat(body["start"]["dateTime"])
        end = datetime.fromisoformat(body["end"]["dateTime"])
        assert (end - start) == timedelta(minutes=90)

    def test_duration_default_60(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
        })
        start = datetime.fromisoformat(body["start"]["dateTime"])
        end = datetime.fromisoformat(body["end"]["dateTime"])
        assert (end - start) == timedelta(hours=1)

    def test_recurrence_agrega_rrule_prefix(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "Gym",
            "scheduled_for": "2024-06-01T07:00:00-03:00",
            "recurrence": "FREQ=WEEKLY;BYDAY=MO",
        })
        assert body["recurrence"] == ["RRULE:FREQ=WEEKLY;BYDAY=MO"]

    def test_recurrence_rrule_ya_prefijado_no_duplica(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "Gym",
            "scheduled_for": "2024-06-01T07:00:00-03:00",
            "recurrence": "RRULE:FREQ=WEEKLY",
        })
        assert body["recurrence"] == ["RRULE:FREQ=WEEKLY"]

    def test_sin_recurrence_no_incluye_campo(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
        })
        assert "recurrence" not in body

    def test_extended_properties_incluye_source_y_status(self):
        from src.connectors.calendar_client import _build_event_body

        body = _build_event_body({
            "title": "T",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
            "source": "whatsapp",
            "status": "active",
        })
        ext = body["extendedProperties"]["private"]
        assert ext["ap_source"] == "whatsapp"
        assert ext["ap_status"] == "active"


# ── calendar_client — _event_to_dict ──────────────────────────────────────────


class TestEventToDict:
    def test_mapea_campos_canonicos(self):
        from src.connectors.calendar_client import _event_to_dict

        api_event = _fake_api_event(event_id="e1", title="Reunión", scheduled_for="2024-06-01T10:00:00-03:00")
        result = _event_to_dict(api_event)
        assert result["id"] == "e1"
        assert result["title"] == "Reunión"
        assert result["status"] == "active"
        assert result["source"] == "whatsapp"

    def test_titulo_con_prefijo_cancelado_infiere_status(self):
        from src.connectors.calendar_client import _event_to_dict

        api_event = _fake_api_event(title="[CANCELADO] Reunión")
        result = _event_to_dict(api_event)
        assert result["status"] == "cancelled"
        assert result["title"] == "Reunión"

    def test_recurrence_extraida(self):
        from src.connectors.calendar_client import _event_to_dict

        api_event = _fake_api_event(recurrence=["RRULE:FREQ=WEEKLY"])
        result = _event_to_dict(api_event)
        assert result["recurrence"] == "RRULE:FREQ=WEEKLY"

    def test_sin_recurrence_devuelve_none(self):
        from src.connectors.calendar_client import _event_to_dict

        api_event = _fake_api_event(recurrence=[])
        result = _event_to_dict(api_event)
        assert result["recurrence"] is None

    def test_description_vacia_devuelve_none_en_notes(self):
        from src.connectors.calendar_client import _event_to_dict

        api_event = _fake_api_event(notes="")
        result = _event_to_dict(api_event)
        assert result["notes"] is None


# ── calendar_client — read_events ─────────────────────────────────────────────


class TestReadEvents:
    def test_retorna_lista_de_eventos(self):
        from src.connectors.calendar_client import read_events

        service = _make_service(events_list=[_fake_api_event("e1"), _fake_api_event("e2")])
        result = read_events(service, "cal@example.com")
        assert len(result) == 2
        assert result[0]["id"] == "e1"

    def test_retorna_lista_vacia_sin_eventos(self):
        from src.connectors.calendar_client import read_events

        service = _make_service(events_list=[])
        result = read_events(service, "cal@example.com")
        assert result == []

    def test_llama_list_con_time_min_y_max_results(self):
        from src.connectors.calendar_client import read_events

        service = _make_service()
        read_events(service, "primary", max_results=10)
        service.events().list.assert_called_once()
        call_kwargs = service.events().list.call_args.kwargs
        assert call_kwargs["maxResults"] == 10
        assert "timeMin" in call_kwargs


# ── calendar_client — create_event ────────────────────────────────────────────


class TestCreateEvent:
    def test_retorna_id_del_evento_creado(self):
        from src.connectors.calendar_client import create_event

        service = _make_service(created_id="nuevo-id")
        event = {
            "title": "Reunión",
            "scheduled_for": "2024-06-01T10:00:00-03:00",
        }
        result = create_event(service, "primary", event)
        assert result == "nuevo-id"

    def test_llama_insert(self):
        from src.connectors.calendar_client import create_event

        service = _make_service()
        create_event(service, "primary", {"title": "T", "scheduled_for": "2024-06-01T10:00:00-03:00"})
        service.events().insert.assert_called_once()

    def test_body_incluye_timezone_montevideo(self):
        from src.connectors.calendar_client import create_event

        service = _make_service()
        create_event(service, "primary", {"title": "T", "scheduled_for": "2024-06-01T10:00:00-03:00"})
        call_kwargs = service.events().insert.call_args.kwargs
        body = call_kwargs["body"]
        assert body["start"]["timeZone"] == "America/Montevideo"

    def test_evento_con_recurrencia(self):
        from src.connectors.calendar_client import create_event

        service = _make_service()
        create_event(service, "primary", {
            "title": "Gym",
            "scheduled_for": "2024-06-03T07:00:00-03:00",
            "recurrence": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
        })
        call_kwargs = service.events().insert.call_args.kwargs
        body = call_kwargs["body"]
        assert "RRULE:FREQ=WEEKLY" in body["recurrence"][0]


# ── calendar_client — update_event ────────────────────────────────────────────


class TestUpdateEvent:
    def test_retorna_true_al_actualizar(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        result = update_event(service, "primary", "e1", {"title": "Nuevo título"})
        assert result is True

    def test_llama_patch(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        update_event(service, "primary", "e1", {"title": "Nuevo"})
        service.events().patch.assert_called_once()

    def test_retorna_false_si_evento_no_existe(self):
        from src.connectors.calendar_client import update_event

        service = MagicMock()
        service.events().get.return_value.execute.side_effect = Exception("not found")
        result = update_event(service, "primary", "no-existe", {"title": "X"})
        assert result is False

    def test_actualiza_titulo(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        update_event(service, "primary", "e1", {"title": "Nuevo título"})
        call_kwargs = service.events().patch.call_args.kwargs
        assert call_kwargs["body"]["summary"] == "Nuevo título"

    def test_actualiza_scheduled_for(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        update_event(service, "primary", "e1", {
            "scheduled_for": "2024-07-01T15:00:00-03:00",
            "duration_minutes": 45,
        })
        call_kwargs = service.events().patch.call_args.kwargs
        body = call_kwargs["body"]
        assert "start" in body
        assert "end" in body
        start = datetime.fromisoformat(body["start"]["dateTime"])
        end = datetime.fromisoformat(body["end"]["dateTime"])
        assert (end - start) == timedelta(minutes=45)

    def test_sin_cambios_no_llama_patch(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        result = update_event(service, "primary", "e1", {})
        assert result is True
        service.events().patch.assert_not_called()

    def test_actualiza_recurrencia(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        update_event(service, "primary", "e1", {"recurrence": "FREQ=DAILY"})
        call_kwargs = service.events().patch.call_args.kwargs
        assert call_kwargs["body"]["recurrence"] == ["RRULE:FREQ=DAILY"]

    def test_elimina_recurrencia_con_none(self):
        from src.connectors.calendar_client import update_event

        service = _make_service()
        update_event(service, "primary", "e1", {"recurrence": None})
        call_kwargs = service.events().patch.call_args.kwargs
        assert call_kwargs["body"]["recurrence"] == []


# ── calendar_client — cancel_event ────────────────────────────────────────────


class TestCancelEvent:
    def test_retorna_true_al_cancelar(self):
        from src.connectors.calendar_client import cancel_event

        service = _make_service()
        result = cancel_event(service, "primary", "e1")
        assert result is True

    def test_llama_patch_no_delete(self):
        from src.connectors.calendar_client import cancel_event

        service = _make_service()
        cancel_event(service, "primary", "e1")
        service.events().patch.assert_called_once()
        service.events().delete.assert_not_called()

    def test_retorna_false_si_evento_no_existe(self):
        from src.connectors.calendar_client import cancel_event

        service = MagicMock()
        service.events().get.return_value.execute.side_effect = Exception("not found")
        result = cancel_event(service, "primary", "no-existe")
        assert result is False

    def test_prefija_titulo_con_cancelado(self):
        from src.connectors.calendar_client import cancel_event

        service = _make_service()
        # El evento existente tiene título "Reunión"
        cancel_event(service, "primary", "e1")
        call_kwargs = service.events().patch.call_args.kwargs
        assert call_kwargs["body"]["summary"].startswith("[CANCELADO]")

    def test_no_duplica_prefijo_si_ya_cancelado(self):
        from src.connectors.calendar_client import cancel_event

        service = MagicMock()
        service.events().get.return_value.execute.return_value = _fake_api_event(
            title="[CANCELADO] Reunión"
        )
        service.events().patch.return_value.execute.return_value = {}

        cancel_event(service, "primary", "e1")
        call_kwargs = service.events().patch.call_args.kwargs
        summary = call_kwargs["body"]["summary"]
        assert summary.count("[CANCELADO]") == 1

    def test_marca_ap_status_cancelled(self):
        from src.connectors.calendar_client import cancel_event

        service = _make_service()
        cancel_event(service, "primary", "e1")
        call_kwargs = service.events().patch.call_args.kwargs
        ext = call_kwargs["body"]["extendedProperties"]["private"]
        assert ext["ap_status"] == "cancelled"
