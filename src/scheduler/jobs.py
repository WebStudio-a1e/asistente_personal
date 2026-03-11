"""APScheduler — instancia única del scheduler.

Arranque:
  start_scheduler() se llama desde el lifespan de FastAPI.
  El BackgroundScheduler corre en un hilo daemon — no bloquea el event loop.

Singleton:
  get_scheduler() siempre retorna la misma instancia en el proceso.
  start_scheduler() es idempotente: si ya está corriendo no lo reinicia.
"""

import logging

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


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
