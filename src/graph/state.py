"""AgentState — estado compartido entre todos los nodos del grafo.

Campos alineados con state_machine.yaml v2.1.
"""

from typing import Optional

from typing_extensions import TypedDict


class AgentState(TypedDict):
    # Mensaje entrante del usuario
    message: str

    # Intención clasificada por el orchestrator
    # task | idea | agenda | accounting | query | unknown | null
    intent: Optional[str]

    # Dominio derivado de la intención
    # tasks | ideas | agenda | accounting | reporting | unknown | null
    domain: Optional[str]

    # Payload estructurado extraído por el agente especializado
    payload: Optional[dict]

    # Estado de la máquina de confirmación
    # detected | proposed | awaiting_confirmation | confirmed |
    # rejected | persisted | failed | expired | null
    confirmation_status: Optional[str]

    # Acciones pendientes para mensajes multi-intención
    pending_actions: list

    # Respuesta generada por el agente para enviar al usuario
    agent_response: Optional[str]

    # Historial de la conversación del hilo
    conversation_history: list

    # Clave de idempotencia del evento Twilio procesado
    idempotency_key: Optional[str]

    # Error capturado durante el procesamiento
    error: Optional[str]
