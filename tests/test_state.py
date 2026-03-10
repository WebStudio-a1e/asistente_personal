"""Tests para src/graph/state.py — T-014."""


def test_agent_state_importa():
    """AgentState importa sin errores."""
    from src.graph.state import AgentState

    assert AgentState is not None


def test_agent_state_tiene_todos_los_campos():
    """AgentState contiene todos los campos definidos en state_machine.yaml."""
    from src.graph.state import AgentState

    campos = AgentState.__annotations__

    assert "message" in campos
    assert "intent" in campos
    assert "domain" in campos
    assert "payload" in campos
    assert "confirmation_status" in campos
    assert "pending_actions" in campos
    assert "agent_response" in campos
    assert "conversation_history" in campos
    assert "idempotency_key" in campos
    assert "error" in campos


def test_agent_state_es_typed_dict():
    """AgentState es un TypedDict."""
    from src.graph.state import AgentState

    assert issubclass(AgentState, dict)


def test_agent_state_instancia_minima():
    """Se puede crear una instancia con solo message y el resto en None/vacío."""
    from src.graph.state import AgentState

    state: AgentState = {
        "message": "hola",
        "intent": None,
        "domain": None,
        "payload": None,
        "confirmation_status": None,
        "pending_actions": [],
        "agent_response": None,
        "conversation_history": [],
        "idempotency_key": None,
        "error": None,
    }

    assert state["message"] == "hola"
    assert state["pending_actions"] == []
    assert state["conversation_history"] == []


def test_agent_state_pending_actions_multi_intencion():
    """pending_actions soporta lista de dicts para multi-intención."""
    from src.graph.state import AgentState

    state: AgentState = {
        "message": "agendá reunión y anotá idea",
        "intent": None,
        "domain": None,
        "payload": None,
        "confirmation_status": None,
        "pending_actions": [
            {"intent": "agenda", "payload": {"titulo": "reunión"}},
            {"intent": "idea", "payload": {"texto": "idea"}},
        ],
        "agent_response": None,
        "conversation_history": [],
        "idempotency_key": None,
        "error": None,
    }

    assert len(state["pending_actions"]) == 2
    assert state["pending_actions"][0]["intent"] == "agenda"
    assert state["pending_actions"][1]["intent"] == "idea"
