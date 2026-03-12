"""Connector para Google Calendar — agenda / recordatorios.

Fuente de verdad: Google Calendar.
Cancelación: marcar como 'cancelled' — nunca eliminar el evento.
Timezone: America/Montevideo (UTC-3 permanente desde 2015).

Campos canónicos de un evento:
    id, title, scheduled_for, duration_minutes, recurrence, notes, status, source
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

TIMEZONE = "America/Montevideo"
_MVD_TZ = timezone(timedelta(hours=-3))

VALID_STATUSES = {"active", "cancelled"}

# Extended property namespace para metadatos propios
_EXT_NS = "private"
_KEY_SOURCE = "ap_source"
_KEY_STATUS = "ap_status"

_CANCELLED_PREFIX = "[CANCELADO] "


# ── Helpers ───────────────────────────────────────────────────────────────────


def _now_mvd() -> str:
    return datetime.now(tz=_MVD_TZ).isoformat()


def _to_mvd_dt(iso_str: str) -> datetime:
    """Parsea un string ISO y lo devuelve con offset UTC-3."""
    dt = datetime.fromisoformat(iso_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_MVD_TZ)
    else:
        dt = dt.astimezone(_MVD_TZ)
    return dt


def _build_event_body(event: dict[str, Any]) -> dict[str, Any]:
    """Construye el body de evento para la Calendar API."""
    start_dt = _to_mvd_dt(event["scheduled_for"])
    duration = int(event.get("duration_minutes") or 60)
    end_dt = start_dt + timedelta(minutes=duration)

    body: dict[str, Any] = {
        "summary": event.get("title", ""),
        "description": event.get("notes") or "",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE},
        "end":   {"dateTime": end_dt.isoformat(),   "timeZone": TIMEZONE},
        "extendedProperties": {
            _EXT_NS: {
                _KEY_SOURCE: event.get("source", "whatsapp"),
                _KEY_STATUS: event.get("status", "active"),
            }
        },
    }

    recurrence = event.get("recurrence")
    if recurrence:
        if not recurrence.startswith("RRULE:"):
            recurrence = f"RRULE:{recurrence}"
        body["recurrence"] = [recurrence]

    return body


def _event_to_dict(event: dict[str, Any]) -> dict[str, Any]:
    """Convierte respuesta de la Calendar API a dict canónico."""
    ext = event.get("extendedProperties", {}).get(_EXT_NS, {})

    start = event.get("start", {})
    scheduled_for = start.get("dateTime") or start.get("date", "")

    summary = event.get("summary", "")
    status = ext.get(_KEY_STATUS, "active")

    if summary.startswith(_CANCELLED_PREFIX):
        status = "cancelled"
        summary = summary[len(_CANCELLED_PREFIX):]

    recurrence_list = event.get("recurrence", [])
    recurrence = recurrence_list[0] if recurrence_list else None

    return {
        "id":            event.get("id", ""),
        "title":         summary,
        "scheduled_for": scheduled_for,
        "recurrence":    recurrence,
        "notes":         event.get("description") or None,
        "status":        status,
        "source":        ext.get(_KEY_SOURCE, "whatsapp"),
    }


# ── API pública ───────────────────────────────────────────────────────────────


def read_events(
    service,
    calendar_id: str,
    max_results: int = 50,
) -> list[dict]:
    """Lee los próximos eventos del calendario.

    Returns:
        Lista de dicts con campos canónicos.
    """
    now_utc = datetime.now(tz=timezone.utc).isoformat()
    result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=now_utc,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    items = result.get("items", [])
    return [_event_to_dict(e) for e in items]


def create_event(service, calendar_id: str, event: dict) -> str:
    """Crea un evento en el calendario.

    Args:
        event: dict con campos canónicos (title, scheduled_for, ...).

    Returns:
        ID del evento creado.
    """
    body = _build_event_body(event)
    created = (
        service.events()
        .insert(calendarId=calendar_id, body=body)
        .execute()
    )
    event_id: str = created.get("id", "")
    logger.info("create_event: evento creado — id=%s", event_id)
    return event_id


def update_event(
    service,
    calendar_id: str,
    event_id: str,
    updates: dict,
) -> bool:
    """Actualiza campos de un evento existente.

    Args:
        updates: dict con los campos a modificar.

    Returns:
        True si se actualizó, False si el evento no existe.
    """
    try:
        service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    except Exception as exc:
        logger.warning("update_event: evento no encontrado — id=%s, %s", event_id, exc)
        return False

    patch: dict[str, Any] = {}

    if updates.get("title"):
        patch["summary"] = updates["title"]

    if "notes" in updates:
        patch["description"] = updates["notes"] or ""

    if updates.get("scheduled_for"):
        start_dt = _to_mvd_dt(updates["scheduled_for"])
        duration = int(updates.get("duration_minutes") or 60)
        end_dt = start_dt + timedelta(minutes=duration)
        patch["start"] = {"dateTime": start_dt.isoformat(), "timeZone": TIMEZONE}
        patch["end"]   = {"dateTime": end_dt.isoformat(),   "timeZone": TIMEZONE}

    if "recurrence" in updates:
        recurrence = updates["recurrence"]
        if recurrence:
            if not recurrence.startswith("RRULE:"):
                recurrence = f"RRULE:{recurrence}"
            patch["recurrence"] = [recurrence]
        else:
            patch["recurrence"] = []

    if not patch:
        return True

    service.events().patch(
        calendarId=calendar_id, eventId=event_id, body=patch
    ).execute()
    logger.info("update_event: evento actualizado — id=%s", event_id)
    return True


def cancel_event(service, calendar_id: str, event_id: str) -> bool:
    """Cancela un evento marcándolo como 'cancelled'.

    Política (DataHandling.md §4 — Google Calendar):
      - Nunca eliminar. Marcar como cancelled.
      - Prefija el título con '[CANCELADO]'.
      - Actualiza extendedProperties ap_status=cancelled.

    Returns:
        True si se canceló, False si el evento no existe.
    """
    try:
        existing = (
            service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        )
    except Exception as exc:
        logger.warning("cancel_event: evento no encontrado — id=%s, %s", event_id, exc)
        return False

    summary = existing.get("summary", "")
    if not summary.startswith(_CANCELLED_PREFIX):
        summary = _CANCELLED_PREFIX + summary

    ext_source = (
        existing.get("extendedProperties", {})
        .get(_EXT_NS, {})
        .get(_KEY_SOURCE, "whatsapp")
    )

    patch: dict[str, Any] = {
        "summary": summary,
        "extendedProperties": {
            _EXT_NS: {
                _KEY_SOURCE: ext_source,
                _KEY_STATUS: "cancelled",
            }
        },
    }

    service.events().patch(
        calendarId=calendar_id, eventId=event_id, body=patch
    ).execute()
    logger.info("cancel_event: evento cancelado — id=%s", event_id)
    return True
