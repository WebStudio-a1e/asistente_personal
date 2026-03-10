# asistente_personal

Asistente personal individual por WhatsApp. Sistema multiagente construido con LangGraph.

**Versión:** v2.1 | **Metodología:** W-CVC | **Estado:** FASE_1A — container-first

---

## Arquitectura

```
WhatsApp (Twilio)
  → FastAPI /webhook
  → dedupe check (SQLite)
  → LangGraph StateGraph
      ├── orchestrator        → clasifica y rutea
      ├── tasks_agent         → Google Sheets (tareas)
      ├── ideas_agent         → Google Docs
      ├── agenda_agent        → Google Calendar
      ├── accounting_agent    → Google Sheets (contabilidad)
      ├── reporting_agent     → consultas complejas (solo lectura)
      ├── confirmation_node   → confirmación previa obligatoria
      └── persist_node        → escritura en fuente de verdad
  → Respuesta por WhatsApp
```

Cada agente usa su propio LLM configurable por variable de entorno.
Compatible con Claude, GPT-4o, Gemini y DeepSeek.

---

## Stack

| Componente      | Tecnología                          |
|-----------------|-------------------------------------|
| Backend         | Python 3.11+ + FastAPI              |
| Motor agentes   | LangGraph                           |
| Checkpointer    | LangGraph SqliteSaver (SQLite)      |
| LLMs            | Claude / GPT-4o / Gemini / DeepSeek |
| Canal           | Twilio → WhatsApp                   |
| Entorno         | Docker Compose                      |
| Deploy          | Railway o Render                    |
| Testing         | pytest                              |
| Linting         | ruff                                |

---

## Principio de arranque — container-first

El proyecto es **container-first**. Eso significa:

- Docker Desktop instalado una vez en la máquina
- `Dockerfile` y `docker-compose.yml` entran en FASE_1A, antes de cualquier lógica funcional
- el runtime del servicio vive en contenedor desde el primer día
- no se considera terminado un slice si no levanta en Docker Compose

---

## Requisitos previos

- Docker Desktop instalado y corriendo
- VS Code con extensión Dev Containers (recomendado)
- API keys: Anthropic, OpenAI, Google Gemini (según los LLMs configurados)
- Cuenta Twilio con WhatsApp Sandbox activo
- Google Sheets (×2), Google Docs y Google Calendar creados
- `credentials/google_credentials.json` de service account (no se commitea)

---

## Instalación local

```bash
git clone <repo-url>
cd asistente_personal
cp .env.example .env
# Completar los valores en .env
docker compose up --build
curl http://localhost:8000/health
```

---

## Configuración de LLMs

Cada agente lee su LLM desde `.env`. Cambiar un LLM no requiere modificar código:

```env
LLM_ORCHESTRATOR=claude-sonnet-4-6
LLM_TASKS=gpt-4o
LLM_IDEAS=claude-sonnet-4-6
LLM_AGENDA=gemini-2.0-flash
LLM_ACCOUNTING=gpt-4o
LLM_REPORTING=claude-sonnet-4-6
```

---

## Estructura del proyecto

```
src/
├── main.py                   # FastAPI app + /webhook + /health
├── config.py                 # Config centralizada
├── graph/
│   ├── graph.py              # StateGraph LangGraph
│   ├── state.py              # AgentState (TypedDict)
│   ├── llm_factory.py        # get_llm(agent_name)
│   └── confirmation_node.py
├── agents/
│   ├── orchestrator.py
│   ├── tasks_agent.py
│   ├── ideas_agent.py
│   ├── agenda_agent.py
│   ├── accounting_agent.py
│   └── reporting_agent.py
├── connectors/
│   ├── google_auth.py
│   ├── sheets_tasks.py
│   ├── sheets_accounting.py
│   ├── docs_ideas.py
│   ├── calendar_client.py
│   └── twilio_client.py
├── domain/
│   ├── intents.py
│   ├── schemas.py
│   └── confirmation.py
├── storage/
│   ├── sqlite.py
│   └── bootstrap.py
└── scheduler/
    └── jobs.py
tests/
docs/
├── PRD_PROYECTO_ACTIVO.md
├── AcceptanceCriteria.md
├── ThreatModel.md
├── DataHandling.md
├── DECISION_FREEZE.md
├── START_HERE.md
└── AUDIT_REPORTS/
credentials/   ← gitignored
data/          ← gitignored
```

---

## Flujo de desarrollo

1. Leer `docs/START_HERE.md`
2. Leer `CLAUDE.md` y `WORKPLAN.yaml`
3. Ejecutar una sola tarea atómica por vez
4. No avanzar de fase con algo roto

### Primera sesión

```bash
# Abrir VS Code en C:\dev\asistente_personal
# Abrir terminal
claude
```

Primera instrucción:

```
Leé docs/START_HERE.md, CLAUDE.md y WORKPLAN.yaml.
Decime en qué fase estamos y cuál es la próxima tarea READY.
Ejecutá SOLO T-001.
```

---

## Regla de desarrollo

Claude Code es el único writer del repo.
Una tarea atómica por vez.
Sin features antes de cerrar FASE_1A container-first.
