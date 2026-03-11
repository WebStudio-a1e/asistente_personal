"""APScheduler — instancia única del scheduler + job de recordatorios.

Arranque:
  start_scheduler() se llama desde el lifespan de FastAPI.
  El BackgroundScheduler corre en un hilo daemon — no bloquea el event loop.

Singleton:
  get_scheduler() siempre retorna la misma instancia en el proceso.
  start_scheduler() es idempotente: si ya está corriendo no lo reinicia.

Job de recordatorios (T-035):
  register_reminder_job() — registra _run_check_reminders cada 15 minutos.
  check_reminders()       — envía recordatorios due y los marca 'sent'.
  mark_missed_reminders() — marca 'missed' los vencidos durante caída.
"""

import logging
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from src.connectors.twilio_client import send_whatsapp_message
from src.storage.sqlite import create_tables, get_connection

logger = logging.getLogger(__name__)

_MVD = ZoneInfo("America/Montevideo")
_scheduler: BackgroundScheduler | None = None


# ── Singleton ──────────────────────────────────────────────────


def get_scheduler() -> BackgroundScheduler:
    """Retorna la instancia singleton del scheduler.

    Crea el scheduler la primera vez (no lo inicia).
    Timezone fija: America/Montevideo (CLAUDE.md §1).
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="America/Montevideo")
        logger.info("scheduler: instancia creada")
    return _scheduler


def start_scheduler() -> BackgroundScheduler:
    """Inicia el scheduler si no está corriendo.

    Idempotente: llamadas sucesivas no tienen efecto si ya está running.
    Retorna la instancia para facilitar tests.
    """
    scheduler = get_scheduler()
    if not scheduler.running:
        scheduler.start()
        logger.info("scheduler: iniciado")
    else:
        logger.debug("scheduler: ya estaba corriendo, no se reinicia")
    return scheduler


def stop_scheduler() -> None:
    """Detiene el scheduler si está corriendo.

    Usa wait=False para no bloquear el shutdown de la app.
    """
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("scheduler: detenido")


# ── Helpers ────────────────────────────────────────────────────


def _now_mvd() -> datetime:
    """Retorna datetime actual en timezone America/Montevideo."""
    return datetime.now(tz=_MVD)


# ── Lógica de recordatorios ────────────────────────────────────


def mark_missed_reminders(
    conn: sqlite3.Connection,
    now: datetime | None = None,
) -> int:
    """Marca como 'missed' recordatorios pendientes cuyo plazo ya venció.

    Se llama en startup para capturar recordatorios que no pudieron enviarse
    mientras la app estaba caída (CLAUDE.md §13: sin reenvío retroactivo).

    Usa `scheduled_for < now` (estrictamente menor) para no interferir
    con recordatorios que se enviarán en el ciclo actual.

    Args:
        conn: conexión SQLite activa.
        now:  instante de referencia. Si None, usa datetime actual en MVD.

    Returns:
        Número de filas actualizadas.
    """
    if now is None:
        now = _now_mvd()
    cutoff = now.isoformat()
    with conn:
        cursor = conn.execute(
            "UPDATE reminder_jobs SET status='missed'"
            " WHERE status='pending' AND scheduled_for < ?",
            (cutoff,),
        )
    count = cursor.rowcount
    if count:
        logger.info("scheduler: %d recordatorio(s) marcado(s) como missed", count)
    return count


def check_reminders(
    conn: sqlite3.Connection,
    twilio_client,
    from_number: str,
    now: datetime | None = None,
) -> list[int]:
    """Envía recordatorios pendientes que ya son due y los marca como 'sent'.

    Args:
        conn:          conexión SQLite activa.
        twilio_client: cliente Twilio (inyectable en tests).
        from_number:   número remitente WhatsApp (ej. whatsapp:+14155238886).
        now:           instante de referencia. Si None, usa datetime actual en MVD.

    Returns:
        Lista de IDs de reminder_jobs enviados.
    """
    if now is None:
        now = _now_mvd()
    cutoff = now.isoformat()

    rows = conn.execute(
        "SELECT id, thread_id, event_id FROM reminder_jobs"
        " WHERE status='pending' AND scheduled_for <= ?",
        (cutoff,),
    ).fetchall()

    sent_ids: list[int] = []
    fired_at = now.isoformat()

    for job_id, thread_id, event_id in rows:
        try:
            send_whatsapp_message(
                twilio_client,
                body=f"Recordatorio: {event_id}",
                to=thread_id,
                from_=from_number,
            )
            with conn:
                conn.execute(
                    "UPDATE reminder_jobs SET status='sent', fired_at=? WHERE id=?",
                    (fired_at, job_id),
                )
            sent_ids.append(job_id)
            logger.info(
                "scheduler: recordatorio enviado — job_id=%s thread=%s",
                job_id,
                thread_id,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "scheduler: error enviando recordatorio job_id=%s — %s",
                job_id,
                exc,
            )

    return sent_ids


# ── Job registrado en el scheduler ────────────────────────────


def _run_check_reminders(
    db_path: str,
    twilio_client,
    from_number: str,
) -> None:
    """Función ejecutada por el scheduler cada 15 minutos.

    Abre su propia conexión SQLite para ser thread-safe.
    """
    conn = get_connection(db_path)
    create_tables(conn)
    try:
        check_reminders(conn, twilio_client, from_number)
    finally:
        conn.close()


def register_reminder_job(
    scheduler: BackgroundScheduler,
    db_path: str,
    twilio_client,
    from_number: str,
) -> None:
    """Registra el job de revisión de recordatorios cada 15 minutos.

    Usa replace_existing=True para ser idempotente.

    Args:
        scheduler:     instancia del BackgroundScheduler.
        db_path:       ruta al archivo SQLite.
        twilio_client: cliente Twilio para envíos.
        from_number:   número remitente WhatsApp.
    """
    scheduler.add_job(
        _run_check_reminders,
        "interval",
        minutes=15,
        id="check_reminders",
        replace_existing=True,
        kwargs={
            "db_path": db_path,
            "twilio_client": twilio_client,
            "from_number": from_number,
        },
    )
    logger.info("scheduler: job 'check_reminders' registrado cada 15 minutos")
