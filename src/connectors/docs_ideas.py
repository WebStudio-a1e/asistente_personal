"""Connector para Google Docs — ideas/notas.

Fuente de verdad: Google Docs, documento maestro con secciones por tema.
SQLite: solo para log de borrados en audit_logs (nunca fuente de verdad).

Formato de bloque en el documento:
    ---IDEA---
    ID: <id>
    Tema: <theme>
    Resumen: <summary>
    Prioridad: <low|medium|high>
    Tags: <tag1, tag2>
    Estado: <active|archived>
    Creado: <created_at>
    ---
    <raw_text>
    ---FIN---

Cada bloque es autónomo. El borrado elimina el bloque completo.
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ── Delimitadores ─────────────────────────────────────────────

BLOCK_START = "---IDEA---"
BLOCK_END = "---FIN---"
FIELD_SEP = "---"

VALID_PRIORITIES = {"low", "medium", "high"}
VALID_STATUSES = {"active", "archived"}


# ── Helpers de texto ──────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _extract_doc_text(doc: dict) -> str:
    """Extrae el texto completo del cuerpo del documento."""
    text_parts: list[str] = []
    for elem in doc.get("body", {}).get("content", []):
        if "paragraph" in elem:
            for pe in elem["paragraph"].get("elements", []):
                text_parts.append(pe.get("textRun", {}).get("content", ""))
    return "".join(text_parts)


def _parse_block(block_text: str) -> dict[str, Any] | None:
    """Parsea un bloque de idea. Retorna None si el bloque es inválido."""
    idea: dict[str, Any] = {"tags": [], "status": "active", "raw_text": ""}
    raw_lines: list[str] = []
    in_raw = False

    for line in block_text.splitlines():
        if line.strip() == FIELD_SEP:
            in_raw = True
            continue
        if in_raw:
            raw_lines.append(line)
            continue
        if line.startswith("ID:"):
            idea["id"] = line[3:].strip()
        elif line.startswith("Tema:"):
            idea["theme"] = line[5:].strip()
        elif line.startswith("Resumen:"):
            idea["summary"] = line[8:].strip()
        elif line.startswith("Prioridad:"):
            idea["priority"] = line[10:].strip()
        elif line.startswith("Tags:"):
            raw_tags = line[5:].strip()
            idea["tags"] = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif line.startswith("Estado:"):
            idea["status"] = line[7:].strip()
        elif line.startswith("Creado:"):
            idea["created_at"] = line[7:].strip()

    idea["raw_text"] = "\n".join(raw_lines).strip()

    if "id" not in idea or not idea["id"]:
        return None
    return idea


def parse_ideas(text: str) -> list[dict]:
    """Extrae todos los bloques de ideas del texto del documento."""
    ideas: list[dict] = []
    segments = text.split(BLOCK_START)
    for segment in segments[1:]:
        if BLOCK_END not in segment:
            continue
        block_content = segment[: segment.index(BLOCK_END)]
        idea = _parse_block(block_content.strip())
        if idea:
            ideas.append(idea)
    return ideas


def format_idea_block(idea: dict) -> str:
    """Formatea un dict de idea como bloque de texto para insertar en el documento."""
    tags_str = ", ".join(idea.get("tags") or [])
    return (
        f"\n{BLOCK_START}\n"
        f"ID: {idea.get('id', '')}\n"
        f"Tema: {idea.get('theme', '')}\n"
        f"Resumen: {idea.get('summary', '')}\n"
        f"Prioridad: {idea.get('priority', 'medium')}\n"
        f"Tags: {tags_str}\n"
        f"Estado: {idea.get('status', 'active')}\n"
        f"Creado: {idea.get('created_at', _now_utc())}\n"
        f"{FIELD_SEP}\n"
        f"{idea.get('raw_text', '')}\n"
        f"{BLOCK_END}\n"
    )


def _find_block_bounds(text: str, idea_id: str) -> tuple[int, int] | None:
    """Encuentra las posiciones (start, end) del bloque con el ID dado.

    Returns:
        (start_char, end_char) del bloque completo, o None si no existe.
    """
    search_from = 0
    while True:
        start = text.find(BLOCK_START, search_from)
        if start == -1:
            return None
        end_marker_pos = text.find(BLOCK_END, start)
        if end_marker_pos == -1:
            return None
        end = end_marker_pos + len(BLOCK_END)
        block = text[start:end]
        if f"ID: {idea_id}" in block:
            return start, end
        search_from = end


def _text_pos_to_doc_index(doc: dict, char_pos: int) -> int:
    """Convierte posición de carácter en texto plano a índice del documento Docs.

    Recorre los elementos del body acumulando longitud de texto hasta llegar
    a la posición buscada y devuelve el startIndex del elemento correspondiente
    más el offset dentro de él.
    """
    accumulated = 0
    for elem in doc.get("body", {}).get("content", []):
        if "paragraph" not in elem:
            continue
        for pe in elem["paragraph"].get("elements", []):
            chunk = pe.get("textRun", {}).get("content", "")
            chunk_len = len(chunk)
            if accumulated + chunk_len > char_pos:
                offset = char_pos - accumulated
                return pe.get("startIndex", elem.get("startIndex", 1)) + offset
            accumulated += chunk_len
    return char_pos + 1


# ── API pública ───────────────────────────────────────────────

def read_ideas(service, doc_id: str) -> list[dict]:
    """Lee todas las ideas del documento maestro.

    Returns:
        Lista de dicts con campos canónicos. Vacía si no hay bloques.
    """
    doc = service.documents().get(documentId=doc_id).execute()
    text = _extract_doc_text(doc)
    return parse_ideas(text)


def write_idea(service, doc_id: str, idea: dict) -> None:
    """Agrega un bloque de idea al final del documento.

    Args:
        idea: dict con campos canónicos (id, theme, summary, priority, tags, ...).
    """
    doc = service.documents().get(documentId=doc_id).execute()
    content = doc.get("body", {}).get("content", [])
    # Insertar antes del último \n del documento (índice final - 1)
    end_index = content[-1].get("endIndex", 2) - 1 if content else 1
    block_text = format_idea_block(idea)
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"insertText": {"location": {"index": end_index}, "text": block_text}}]},
    ).execute()


def delete_idea(
    service,
    doc_id: str,
    idea_id: str,
    conn: sqlite3.Connection,
    thread_id: str = "",
) -> bool:
    """Borra físicamente el bloque de una idea y registra en audit_logs.

    Política (DataHandling.md §6 — Ideas):
      - Borrado físico del bloque en Google Docs.
      - Log inmutable en SQLite audit_logs.

    Returns:
        True si se encontró y borró, False si no existe.
    """
    doc = service.documents().get(documentId=doc_id).execute()
    text = _extract_doc_text(doc)
    bounds = _find_block_bounds(text, idea_id)

    if bounds is None:
        logger.warning("delete_idea: idea no encontrada — id=%s", idea_id)
        return False

    char_start, char_end = bounds
    doc_start = _text_pos_to_doc_index(doc, char_start)
    doc_end = _text_pos_to_doc_index(doc, char_end)

    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": [{"deleteContentRange": {"range": {"startIndex": doc_start, "endIndex": doc_end}}}]},
    ).execute()

    _log_deletion(conn, thread_id, idea_id, text[char_start:char_end])
    return True


def _log_deletion(
    conn: sqlite3.Connection,
    thread_id: str,
    idea_id: str,
    block_text: str,
) -> None:
    """Registra el borrado en audit_logs. Falla silenciosa."""
    try:
        with conn:
            conn.execute(
                "INSERT INTO audit_logs (thread_id, action, domain, payload, status) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    thread_id,
                    "delete_idea",
                    "ideas",
                    json.dumps({"idea_id": idea_id, "block": block_text[:500]}),
                    "deleted",
                ),
            )
    except Exception as exc:  # noqa: BLE001
        logger.error("_log_deletion: error escribiendo audit_log — %s", exc)
