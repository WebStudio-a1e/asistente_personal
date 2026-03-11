"""Confirmation node — gestiona el flujo de confirmación previa a la persistencia.

Flujo (state_machine.yaml §confirmation_flow):
  agente especializado → confirmation_node → persist_node  (confirmed)
                                           → orchestrator   (rejected)
                                           → END            (expired / ambiguo sin resolver)

Estados gestionados:
  None / detected / proposed  → awaiting_confirmation  (genera propuesta)
  awaiting_confirmation       → confirmed              (señal positiva)
  awaiting_confirmation       → rejected               (señal negativa)
  awaiting_confirmation       → expired                (timeout 30 min)
  awaiting_confirmation       → awaiting_confirmation  (señal ambigua — pide aclaración)
  cualquier otro              → sin cambios            (ya resuelto)
"""

import logging
from datetime import datetime, timezone

from src.domain.confirmation import (
    ConfirmationStatus,
    SignalType,
    is_expired,
    normalize_signal,
)
from src.graph.state import AgentState

logger = logging.getLogger(__name__)

# Clave interna del payload donde se guarda el timestamp de la propuesta.
# Empieza con _ para que _build_proposal_text no la muestre al usuario.
_SENT_AT_KEY = "_proposal_sent_at"


# ── Helpers ───────────────────────────────────────────────────


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _build_proposal_text(payload: dict | None, domain: str | None) -> str:
    """Construye el texto legible de la propuesta para enviar al usuario."""
    if not payload:
        return "¿Confirmás la acción? (sí / no)"

    domain_label = domain or "acción"
    lines = [f"Propuesta ({domain_label}):"]
    for key, value in payload.items():
        if not key.startswith("_"):
            lines.append(f"  • {key}: {value}")
    lines.append("\n¿Confirmás? (sí / no)")
    return "\n".join(lines)


# ── Nodo ─────────────────────────────────────────────────────


def confirmation_node(state: AgentState) -> dict:
    """Gestiona el ciclo de vida de la confirmación.

    Primera invocación (status en None/detected/proposed):
      → genera propuesta al usuario, pasa a awaiting_confirmation.

    Segunda invocación (status == awaiting_confirmation):
      → evalúa timeout; luego normaliza señal del usuario.
      → confirmed | rejected | expired | awaiting_confirmation (pide aclaración).

    Estado ya resuelto:
      → retorna dict vacío (sin cambios).
    """
    status = state.get("confirmation_status")
    message = state.get("message", "")
    payload = dict(state.get("payload") or {})
    domain = state.get("domain")

    # ── Primera visita: generar propuesta ────────────────────
    if status in (None,
                  ConfirmationStatus.DETECTED,
                  ConfirmationStatus.PROPOSED):
        proposal_text = _build_proposal_text(payload, domain)
        payload[_SENT_AT_KEY] = _now_utc().isoformat()
        return {
            "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
            "agent_response":      proposal_text,
            "payload":             payload,
        }

    # ── Awaiting: evaluar respuesta del usuario ───────────────
    if status == ConfirmationStatus.AWAITING_CONFIRMATION:

        # Verificar timeout
        sent_at_raw = payload.get(_SENT_AT_KEY)
        if sent_at_raw:
            try:
                sent_at = datetime.fromisoformat(sent_at_raw)
                if is_expired(sent_at):
                    logger.info("confirmation_node: propuesta expirada")
                    return {
                        "confirmation_status": ConfirmationStatus.EXPIRED,
                        "agent_response": (
                            "La propuesta expiró (30 minutos sin respuesta). "
                            "Enviá tu solicitud de nuevo cuando quieras."
                        ),
                    }
            except (ValueError, TypeError) as exc:
                logger.warning("confirmation_node: _proposal_sent_at inválido — %s", exc)

        # Normalizar señal del usuario
        signal = normalize_signal(message)

        if signal == SignalType.POSITIVE:
            return {
                "confirmation_status": ConfirmationStatus.CONFIRMED,
                "agent_response":      None,
            }

        if signal == SignalType.NEGATIVE:
            return {
                "confirmation_status": ConfirmationStatus.REJECTED,
                "agent_response":      "Entendido, cancelado. ¿En qué más te puedo ayudar?",
            }

        # Ambiguo o desconocido → mantener awaiting, pedir aclaración
        return {
            "confirmation_status": ConfirmationStatus.AWAITING_CONFIRMATION,
            "agent_response": (
                "No entendí tu respuesta. "
                "¿Confirmás o cancelás la acción? (sí / no)"
            ),
        }

    # ── Estado ya resuelto: sin cambios ──────────────────────
    return {}
