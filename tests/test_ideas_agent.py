"""Tests T-023 — ideas_agent + docs_ideas.

Sin credenciales reales: todas las llamadas a LLM y Google APIs están mockeadas.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ── Helpers ───────────────────────────────────────────────────────────────────


def _mock_llm(payload: dict) -> MagicMock:
    """LLM mock que devuelve JSON serializado en .content."""
    llm = MagicMock()
    llm.invoke.return_value = MagicMock(content=json.dumps(payload))
    return llm


def _fake_doc(text: str) -> dict:
    """Documento Docs mínimo con texto embebido."""
    return {
        "body": {
            "content": [
                {
                    "paragraph": {
                        "elements": [
                            {
                                "startIndex": 1,
                                "textRun": {"content": text},
                            }
                        ]
                    },
                    "endIndex": len(text) + 1,
                }
            ]
        }
    }


# ── ideas_agent_node ──────────────────────────────────────────────────────────


class TestIdeasAgentNode:
    def test_retorna_payload_con_campos_canonicos(self):
        from src.agents.ideas_agent import ideas_agent_node

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "Tecnología",
            "summary": "Usar LangGraph para el asistente",
            "priority": "high",
            "tags": ["ia", "langgraph"],
            "status": "active",
            "raw_text": "Quiero usar LangGraph para construir el asistente",
            "agent_response": "Voy a registrar tu idea sobre LangGraph.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "Quiero usar LangGraph para el asistente"})

        assert result["payload"]["operation"] == "create"
        assert result["payload"]["theme"] == "Tecnología"
        assert result["payload"]["summary"] == "Usar LangGraph para el asistente"
        assert result["payload"]["priority"] == "high"
        assert result["payload"]["tags"] == ["ia", "langgraph"]
        assert result["payload"]["status"] == "active"

    def test_genera_idea_id_si_llm_devuelve_null(self):
        from src.agents.ideas_agent import ideas_agent_node

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "Test",
            "summary": "Resumen",
            "priority": None,
            "tags": [],
            "status": None,
            "raw_text": None,
            "agent_response": "Registrando.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "nueva idea"})

        assert result["payload"]["idea_id"]
        assert len(result["payload"]["idea_id"]) == 36  # UUID

    def test_defaults_priority_medium_y_status_active(self):
        from src.agents.ideas_agent import ideas_agent_node

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "X",
            "summary": None,
            "priority": None,
            "tags": None,
            "status": None,
            "raw_text": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "idea vaga"})

        assert result["payload"]["priority"] == "medium"
        assert result["payload"]["status"] == "active"
        assert result["payload"]["tags"] == []

    def test_confirmation_status_es_detected(self):
        from src.agents.ideas_agent import ideas_agent_node
        from src.domain.confirmation import ConfirmationStatus

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "T",
            "summary": "S",
            "priority": "low",
            "tags": [],
            "status": "active",
            "raw_text": "texto",
            "agent_response": "Ok.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "idea"})

        assert result["confirmation_status"] == ConfirmationStatus.DETECTED

    def test_agent_response_propagado(self):
        from src.agents.ideas_agent import ideas_agent_node

        llm_data = {
            "operation": "read",
            "idea_id": None,
            "theme": None,
            "summary": None,
            "priority": None,
            "tags": [],
            "status": None,
            "raw_text": None,
            "agent_response": "Voy a listar tus ideas.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "muéstrame las ideas"})

        assert result["agent_response"] == "Voy a listar tus ideas."

    def test_parse_error_usa_defaults(self):
        """Respuesta no-JSON → operation='create', sin crash."""
        from src.agents.ideas_agent import ideas_agent_node

        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="esto no es json")

        with patch("src.agents.ideas_agent.get_llm", return_value=llm):
            result = ideas_agent_node({"message": "algo"})

        assert result["payload"]["operation"] == "create"
        assert result["payload"]["priority"] == "medium"

    def test_markdown_fence_stripping(self):
        """Respuesta con ```json ... ``` se parsea correctamente."""
        from src.agents.ideas_agent import ideas_agent_node

        inner = {
            "operation": "delete",
            "idea_id": "abc-123",
            "theme": None,
            "summary": None,
            "priority": None,
            "tags": [],
            "status": None,
            "raw_text": None,
            "agent_response": "Borrando.",
        }
        fenced = f"```json\n{json.dumps(inner)}\n```"
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content=fenced)

        with patch("src.agents.ideas_agent.get_llm", return_value=llm):
            result = ideas_agent_node({"message": "borra idea abc-123"})

        assert result["payload"]["operation"] == "delete"
        assert result["payload"]["idea_id"] == "abc-123"

    def test_source_es_whatsapp(self):
        from src.agents.ideas_agent import ideas_agent_node

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "T",
            "summary": "S",
            "priority": "low",
            "tags": [],
            "status": "active",
            "raw_text": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)):
            result = ideas_agent_node({"message": "nueva idea"})

        assert result["payload"]["source"] == "whatsapp"

    def test_usa_llm_ideas(self):
        from src.agents.ideas_agent import ideas_agent_node

        llm_data = {
            "operation": "create",
            "idea_id": None,
            "theme": "T",
            "summary": "S",
            "priority": "low",
            "tags": [],
            "status": "active",
            "raw_text": None,
            "agent_response": "Ok.",
        }

        with patch("src.agents.ideas_agent.get_llm", return_value=_mock_llm(llm_data)) as mock_get:
            ideas_agent_node({"message": "idea"})
            mock_get.assert_called_once_with("ideas")


# ── docs_ideas — parse_ideas / format_idea_block ──────────────────────────────


class TestParseIdeas:
    def test_parsea_bloque_valido(self):
        from src.connectors.docs_ideas import parse_ideas

        text = (
            "---IDEA---\n"
            "ID: abc-1\n"
            "Tema: Tecnología\n"
            "Resumen: Usar LangGraph\n"
            "Prioridad: high\n"
            "Tags: ia, python\n"
            "Estado: active\n"
            "Creado: 2024-01-01T00:00:00+00:00\n"
            "---\n"
            "Texto completo de la idea.\n"
            "---FIN---\n"
        )
        ideas = parse_ideas(text)
        assert len(ideas) == 1
        assert ideas[0]["id"] == "abc-1"
        assert ideas[0]["theme"] == "Tecnología"
        assert ideas[0]["summary"] == "Usar LangGraph"
        assert ideas[0]["priority"] == "high"
        assert ideas[0]["tags"] == ["ia", "python"]
        assert ideas[0]["status"] == "active"
        assert "Texto completo" in ideas[0]["raw_text"]

    def test_parsea_multiples_bloques(self):
        from src.connectors.docs_ideas import parse_ideas

        text = (
            "---IDEA---\nID: id-1\nTema: A\nResumen: R1\nPrioridad: low\nTags: \nEstado: active\n---\nraw1\n---FIN---\n"
            "---IDEA---\nID: id-2\nTema: B\nResumen: R2\nPrioridad: medium\nTags: x\nEstado: archived\n---\nraw2\n---FIN---\n"
        )
        ideas = parse_ideas(text)
        assert len(ideas) == 2
        assert ideas[0]["id"] == "id-1"
        assert ideas[1]["id"] == "id-2"

    def test_ignora_bloque_sin_id(self):
        from src.connectors.docs_ideas import parse_ideas

        text = (
            "---IDEA---\n"
            "Tema: Sin ID\n"
            "---\nraw\n---FIN---\n"
        )
        ideas = parse_ideas(text)
        assert len(ideas) == 0

    def test_retorna_lista_vacia_si_no_hay_bloques(self):
        from src.connectors.docs_ideas import parse_ideas

        ideas = parse_ideas("texto sin bloques")
        assert ideas == []

    def test_bloque_sin_fin_ignorado(self):
        from src.connectors.docs_ideas import parse_ideas

        text = "---IDEA---\nID: x\nTema: T\n---\nraw\n"  # sin ---FIN---
        ideas = parse_ideas(text)
        assert ideas == []

    def test_tags_vacios(self):
        from src.connectors.docs_ideas import parse_ideas

        text = (
            "---IDEA---\nID: t1\nTema: T\nResumen: R\nPrioridad: low\nTags: \nEstado: active\n---\n\n---FIN---\n"
        )
        ideas = parse_ideas(text)
        assert ideas[0]["tags"] == []


class TestFormatIdeaBlock:
    def test_formato_incluye_delimitadores(self):
        from src.connectors.docs_ideas import format_idea_block

        idea = {
            "id": "x1",
            "theme": "Test",
            "summary": "Resumen",
            "priority": "medium",
            "tags": ["a", "b"],
            "status": "active",
            "raw_text": "texto",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        block = format_idea_block(idea)
        assert "---IDEA---" in block
        assert "---FIN---" in block
        assert "ID: x1" in block
        assert "Tema: Test" in block
        assert "Tags: a, b" in block

    def test_tags_lista_vacia(self):
        from src.connectors.docs_ideas import format_idea_block

        idea = {"id": "x2", "theme": "T", "summary": "S", "priority": "low", "tags": [], "status": "active", "raw_text": "r"}
        block = format_idea_block(idea)
        assert "Tags: \n" in block

    def test_defaults_en_campos_ausentes(self):
        from src.connectors.docs_ideas import format_idea_block

        block = format_idea_block({"id": "x3"})
        assert "Prioridad: medium" in block
        assert "Estado: active" in block


# ── docs_ideas — read_ideas ────────────────────────────────────────────────────


class TestReadIdeas:
    def test_retorna_lista_de_ideas(self):
        from src.connectors.docs_ideas import read_ideas

        text = (
            "---IDEA---\nID: i1\nTema: T\nResumen: R\nPrioridad: high\nTags: \nEstado: active\n---\nraw\n---FIN---\n"
        )
        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc(text)

        ideas = read_ideas(service, "DOC_ID")
        assert len(ideas) == 1
        assert ideas[0]["id"] == "i1"

    def test_retorna_lista_vacia_sin_bloques(self):
        from src.connectors.docs_ideas import read_ideas

        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc("sin ideas aquí")

        ideas = read_ideas(service, "DOC_ID")
        assert ideas == []


# ── docs_ideas — write_idea ────────────────────────────────────────────────────


class TestWriteIdea:
    def test_llama_batch_update_con_insert_text(self):
        from src.connectors.docs_ideas import write_idea

        doc = {
            "body": {
                "content": [
                    {
                        "paragraph": {"elements": [{"startIndex": 1, "textRun": {"content": "\n"}}]},
                        "endIndex": 2,
                    }
                ]
            }
        }
        service = MagicMock()
        service.documents().get().execute.return_value = doc

        idea = {
            "id": "w1",
            "theme": "T",
            "summary": "S",
            "priority": "low",
            "tags": [],
            "status": "active",
            "raw_text": "raw",
            "created_at": "2024-01-01T00:00:00+00:00",
        }

        write_idea(service, "DOC_ID", idea)
        service.documents().batchUpdate.assert_called_once()
        call_kwargs = service.documents().batchUpdate.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["body"]
        # Verificar que hay una request insertText
        requests = body.get("requests", [])
        assert any("insertText" in r for r in requests)


# ── docs_ideas — delete_idea ──────────────────────────────────────────────────


class TestDeleteIdea:
    def _make_conn(self):
        import sqlite3
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE audit_logs "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT, thread_id TEXT, action TEXT, "
            "domain TEXT, payload TEXT, status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
        )
        return conn

    def test_retorna_true_y_llama_batch_update(self):
        from src.connectors.docs_ideas import delete_idea

        text = (
            "---IDEA---\nID: d1\nTema: T\nResumen: R\nPrioridad: low\nTags: \nEstado: active\n---\nraw\n---FIN---\n"
        )
        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc(text)
        conn = self._make_conn()

        result = delete_idea(service, "DOC_ID", "d1", conn, thread_id="t1")
        assert result is True
        service.documents().batchUpdate.assert_called_once()

    def test_retorna_false_si_idea_no_existe(self):
        from src.connectors.docs_ideas import delete_idea

        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc("sin ideas")
        conn = self._make_conn()

        result = delete_idea(service, "DOC_ID", "no-existe", conn)
        assert result is False

    def test_registra_en_audit_logs(self):
        from src.connectors.docs_ideas import delete_idea

        text = (
            "---IDEA---\nID: a1\nTema: T\nResumen: R\nPrioridad: low\nTags: \nEstado: active\n---\nraw\n---FIN---\n"
        )
        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc(text)
        conn = self._make_conn()

        delete_idea(service, "DOC_ID", "a1", conn, thread_id="thread-99")

        rows = conn.execute("SELECT * FROM audit_logs").fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "delete_idea"  # action
        assert rows[0][3] == "ideas"        # domain

    def test_batch_update_usa_delete_content_range(self):
        from src.connectors.docs_ideas import delete_idea

        text = (
            "---IDEA---\nID: r1\nTema: T\nResumen: R\nPrioridad: low\nTags: \nEstado: active\n---\nraw\n---FIN---\n"
        )
        service = MagicMock()
        service.documents().get().execute.return_value = _fake_doc(text)
        conn = self._make_conn()

        delete_idea(service, "DOC_ID", "r1", conn)

        call_kwargs = service.documents().batchUpdate.call_args
        body = call_kwargs.kwargs.get("body") or (call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs["body"])
        requests = body.get("requests", [])
        assert any("deleteContentRange" in r for r in requests)
