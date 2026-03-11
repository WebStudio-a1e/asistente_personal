"""Schemas Pydantic para los cuatro dominios persistentes.

Alineados con DataHandling.md §3.
Timezone: America/Montevideo en todo momento.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Task(BaseModel):
    """Tarea — fuente de verdad: Google Sheets (hoja Tareas)."""

    id: str
    title: str
    status: Literal["pending", "in_progress", "today", "completed"]
    created_at: datetime
    updated_at: datetime
    source: Literal["whatsapp"] = "whatsapp"
    notes: Optional[str] = None


class Idea(BaseModel):
    """Idea / Nota — fuente de verdad: Google Docs (documento maestro)."""

    id: str
    raw_text: str
    theme: str
    summary: str
    priority: Literal["low", "medium", "high"]
    status: Literal["active", "archived"] = "active"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class Event(BaseModel):
    """Evento / Recordatorio — fuente de verdad: Google Calendar."""

    id: str
    title: str
    scheduled_for: datetime
    recurrence: Optional[str] = None
    notes: Optional[str] = None
    status: Literal["active", "cancelled"] = "active"
    source: Literal["whatsapp"] = "whatsapp"


class AccountingEntry(BaseModel):
    """Movimiento contable — fuente de verdad: Google Sheets (contabilidad).

    PROHIBIDO borrar. Corrección solo por edición con correction_note.
    """

    id: str
    date: datetime
    type: Literal["income", "expense"]
    category: str
    amount: Decimal
    note: str
    balance: Optional[Decimal] = None
    correction_note: Optional[str] = None
