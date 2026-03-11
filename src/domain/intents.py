"""Enums de intención y dominio — clasificación del orchestrator.

Intent: qué quiere hacer el usuario.
Domain: sobre qué entidad opera la acción.
"""

from enum import Enum


class Intent(str, Enum):
    TASK       = "task"
    IDEA       = "idea"
    AGENDA     = "agenda"
    ACCOUNTING = "accounting"
    QUERY      = "query"
    UNKNOWN    = "unknown"


class Domain(str, Enum):
    TASKS      = "tasks"
    IDEAS      = "ideas"
    AGENDA     = "agenda"
    ACCOUNTING = "accounting"
    REPORTING  = "reporting"
    UNKNOWN    = "unknown"
