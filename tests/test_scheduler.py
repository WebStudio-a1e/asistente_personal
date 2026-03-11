"""Tests T-034 — APScheduler integrado en app.

Verifica:
- get_scheduler() retorna siempre la misma instancia (singleton).
- start_scheduler() inicia el scheduler sin bloquear.
- start_scheduler() es idempotente.
- stop_scheduler() detiene el scheduler correctamente.
- El scheduler usa timezone America/Montevideo.
- FastAPI lifespan inicia y detiene el scheduler.
"""

from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────


def _reset_scheduler():
    """Resetea el singleton entre tests para aislar el estado."""
    import src.scheduler.jobs as mod
    if mod._scheduler is not None and mod._scheduler.running:
        mod._scheduler.shutdown(wait=False)
    mod._scheduler = None


# ── Singleton ─────────────────────────────────────────────────────────────────


class TestSingleton:
    def setup_method(self):
        _reset_scheduler()

    def teardown_method(self):
        _reset_scheduler()

    def test_get_scheduler_retorna_misma_instancia(self):
        from src.scheduler.jobs import get_scheduler
        s1 = get_scheduler()
        s2 = get_scheduler()
        assert s1 is s2

    def test_get_scheduler_crea_background_scheduler(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.scheduler.jobs import get_scheduler
        s = get_scheduler()
        assert isinstance(s, BackgroundScheduler)

    def test_get_scheduler_timezone_montevideo(self):
        from src.scheduler.jobs import get_scheduler
        s = get_scheduler()
        assert str(s.timezone) == "America/Montevideo"

    def test_get_scheduler_no_iniciado_por_defecto(self):
        from src.scheduler.jobs import get_scheduler
        s = get_scheduler()
        assert not s.running


# ── Start / Stop ──────────────────────────────────────────────────────────────


class TestStartStop:
    def setup_method(self):
        _reset_scheduler()

    def teardown_method(self):
        _reset_scheduler()

    def test_start_scheduler_inicia_el_scheduler(self):
        from src.scheduler.jobs import start_scheduler
        s = start_scheduler()
        assert s.running

    def test_start_scheduler_retorna_instancia(self):
        from apscheduler.schedulers.background import BackgroundScheduler
        from src.scheduler.jobs import start_scheduler
        s = start_scheduler()
        assert isinstance(s, BackgroundScheduler)

    def test_start_scheduler_idempotente(self):
        from src.scheduler.jobs import start_scheduler
        s1 = start_scheduler()
        s2 = start_scheduler()
        assert s1 is s2
        assert s2.running

    def test_stop_scheduler_detiene_el_scheduler(self):
        from src.scheduler.jobs import start_scheduler, stop_scheduler
        start_scheduler()
        stop_scheduler()
        from src.scheduler.jobs import get_scheduler
        assert not get_scheduler().running

    def test_stop_scheduler_sin_start_no_lanza_excepcion(self):
        from src.scheduler.jobs import stop_scheduler
        stop_scheduler()  # no debe lanzar


# ── Lifespan FastAPI ──────────────────────────────────────────────────────────


class TestLifespan:
    def setup_method(self):
        _reset_scheduler()

    def teardown_method(self):
        _reset_scheduler()

    def test_lifespan_inicia_scheduler_al_arrancar_app(self):
        from src.main import app
        from src.scheduler.jobs import get_scheduler
        with TestClient(app):
            assert get_scheduler().running

    def test_lifespan_detiene_scheduler_al_cerrar_app(self):
        from src.main import app
        from src.scheduler.jobs import get_scheduler
        with TestClient(app):
            pass  # entra y sale del contexto
        assert not get_scheduler().running

    def test_health_endpoint_disponible_con_scheduler_activo(self):
        from src.main import app
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
