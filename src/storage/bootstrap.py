"""Bootstrap SQLite — crea las tablas operativas e inicializa SqliteSaver.

Idempotente: ejecutable múltiples veces sin efectos secundarios.
"""

from langgraph.checkpoint.sqlite import SqliteSaver

from src.config import load_config
from src.storage.sqlite import create_tables, get_connection


def run_bootstrap(db_path: str | None = None) -> None:
    """Crea las 6 tablas operativas y verifica que SqliteSaver es inicializable.

    Args:
        db_path: ruta al archivo SQLite. Si es None, usa SQLITE_DB_PATH de config.
    """
    if db_path is None:
        cfg = load_config()
        db_path = cfg.sqlite_db_path

    conn = get_connection(db_path)
    create_tables(conn)
    conn.close()

    with SqliteSaver.from_conn_string(db_path) as _saver:
        pass


if __name__ == "__main__":
    run_bootstrap()
