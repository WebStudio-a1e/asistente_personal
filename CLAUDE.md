# CLAUDE.md — asistente_personal v2.1

## 1) Propósito

Asistente personal individual por WhatsApp. Sistema multiagente construido con LangGraph.

Dominios: tareas en kanban, ideas/notas, agenda/recordatorios, contabilidad, reporting administrativo.

Opera en español, zona horaria `America/Montevideo`.
Ningún agente persiste datos sin confirmación explícita del usuario.
El `reporting_agent` es solo lectura, nunca persiste.

---

## 2) Agentes del sistema

| Agente             | Dominio                         | Fuente de verdad              | LLM               |
|--------------------|---------------------------------|-------------------------------|-------------------|
| `orchestrator`     | Clasifica y rutea               | —                             | `LLM_ORCHESTRATOR`|
| `tasks_agent`      | Tareas / Kanban                 | Google Sheets (tareas)        | `LLM_TASKS`       |
| `ideas_agent`      | Ideas / Notas                   | Google Docs                   | `LLM_IDEAS`       |
| `agenda_agent`     | Agenda / Recordatorios          | Google Calendar               | `LLM_AGENDA`      |
| `accounting_agent` | Ingresos / Egresos              | Google Sheets (contabilidad)  | `LLM_ACCOUNTING`  |
| `reporting_agent`  | Consultas complejas (solo lectura) | Todos los dominios          | `LLM_REPORTING`   |
| `confirmation_node`| Confirmación previa             | —                             | —                 |
| `persist_node`     | Escritura en fuente de verdad   | —                             | —                 |

---

## 3) Documentos canónicos

Todo lo que no está commiteado en estas rutas no existe:

- `docs/PRD_PROYECTO_ACTIVO.md`
- `docs/AcceptanceCriteria.md`
- `docs/ThreatModel.md`
- `docs/DataHandling.md`
- `docs/DECISION_FREEZE.md`
- `docs/START_HERE.md`
- `state_machine.yaml`
- `WORKPLAN.yaml`
- `.env.example`

---

## 4) Regla de oro — orden de arranque

**El proyecto es container-first.**
El orden correcto de FASE_1A es:

```
T-001  → estructura base + requirements.txt + Dockerfile + docker-compose.yml
         docker compose up --build levanta antes de escribir una línea funcional
T-002  → src/config.py
T-003  → src/main.py + /health
T-004  → smoke tests dentro del contenedor
```

**Regla dura:** T-001 no está done hasta que `docker compose up --build` funciona.
No se empieza T-002/T-003 sin T-001 done.
No se empieza lógica funcional (agentes, grafo, conectores) sin FASE_1A cerrada.

**Prerequisitos para iniciar T-001** (ya deben estar commiteados):
- `docs/PRD_PROYECTO_ACTIVO.md` ✓
- `CLAUDE.md` ✓
- `WORKPLAN.yaml` ✓
- `.env.example` ✓

Si falta cualquiera → **BLOCKED**.

---

## 5) Regla sistémica: confirmación previa

```
mensaje → orchestrator → agente especializado → confirmation_node → persist_node
```

**Timeout:** 30 minutos desde que se envía la propuesta. Si vence → `expired` → no persiste.

**reporting_agent:** nunca pasa por `confirmation_node`. Lee y responde directo.

**Multi-intención:** el orquestador descompone en `pending_actions` y el sistema confirma cada una por separado.

---

## 6) Grafo LangGraph

```python
StateGraph(AgentState)
  .add_node("orchestrator",       orchestrator_node)
  .add_node("tasks_agent",        tasks_agent_node)
  .add_node("ideas_agent",        ideas_agent_node)
  .add_node("agenda_agent",       agenda_agent_node)
  .add_node("accounting_agent",   accounting_agent_node)
  .add_node("reporting_agent",    reporting_agent_node)
  .add_node("confirmation_node",  confirmation_node)
  .add_node("persist_node",       persist_node)
```

**Checkpointer:** `SqliteSaver` — persiste `AgentState` entre mensajes del mismo `thread_id` (= número de WhatsApp).

**AgentState campos:**
- `message`, `intent`, `domain`, `payload`
- `confirmation_status`: detected | proposed | awaiting_confirmation | confirmed | rejected | persisted | failed | expired
- `pending_actions` (multi-intención)
- `agent_response`, `conversation_history`
- `idempotency_key`, `error`

---

## 7) LLMs por agente — configuración

| Variable env       | Default             |
|--------------------|---------------------|
| `LLM_ORCHESTRATOR` | claude-sonnet-4-6   |
| `LLM_TASKS`        | gpt-4o              |
| `LLM_IDEAS`        | claude-sonnet-4-6   |
| `LLM_AGENDA`       | gemini-2.0-flash    |
| `LLM_ACCOUNTING`   | gpt-4o              |
| `LLM_REPORTING`    | claude-sonnet-4-6   |

Cambiar el LLM de un agente = cambiar una variable de entorno. Sin tocar código.

---

## 8) Intenciones válidas

`task` | `idea` | `agenda` | `accounting` | `query` | `unknown`

---

## 9) Regla de clasificación

**Paso A — orchestrator:** clasifica intención y dominio.
**Paso B — agente especializado:** extrae payload estructurado.

Si la intención es ambigua, multi-dominio, el payload está incompleto o la confianza es baja:
→ pedir aclaración. No derivar a persistencia.

---

## 10) Política de edición y borrado

| Dominio       | Editar                  | Borrar                                        |
|---------------|-------------------------|-----------------------------------------------|
| Tareas        | Sí, con confirmación    | Sí — físico en Sheets + log en SQLite         |
| Ideas         | Sí, con confirmación    | Sí — físico en Docs + log en SQLite           |
| Agenda        | Sí, con confirmación    | No se borra — se cancela → `cancelled`        |
| Contabilidad  | Sí + `correction_note`  | **PROHIBIDO** — sin herramienta de borrado    |

---

## 11) SQLite — dos roles distintos

**Rol 1 — Checkpointer LangGraph (automático):**
SqliteSaver persiste `AgentState` entre mensajes del mismo hilo.

**Rol 2 — Soporte operativo (tablas propias):**

| Tabla                  | Contenido                            | Retención |
|------------------------|--------------------------------------|-----------|
| `inbound_messages`     | Mensajes recibidos de Twilio         | 90 días   |
| `conversation_state`   | Estado conversacional activo         | 90 días   |
| `confirmation_requests`| Propuestas esperando confirmación    | 90 días   |
| `processed_events`     | Idempotencia de webhooks             | 30 días   |
| `reminder_jobs`        | Estado de jobs del scheduler         | 90 días   |
| `audit_logs`           | Acciones ejecutadas y rechazadas     | 90 días   |

**SQLite nunca es fuente funcional de verdad.**
Conflicto → Sheets / Docs / Calendar gana siempre.

---

## 12) Idempotencia

1. `provider event id` de Twilio si existe.
2. Fallback: hash normalizado de remitente + timestamp + body.
3. Consultar `processed_events` antes de invocar el grafo.
4. Si ya existe → ignorar. Si no → registrar y procesar.

---

## 13) Scheduler

APScheduler in-process. Revisión cada 15 minutos.
Solo válido con **una única instancia activa**.
Recordatorios vencidos durante caída → `missed`. Sin reenvío retroactivo.

---

## 14) Stack congelado

Python 3.11+ · FastAPI · LangGraph · langchain-core · langchain-anthropic · langchain-openai · langchain-google-genai · anthropic · openai · google-generativeai · twilio · gspread · google-api-python-client · google-auth · APScheduler · SQLite · Docker Compose · pytest · ruff

---

## 15) Reglas de sesión

1. Leer `docs/START_HERE.md`, `CLAUDE.md` y `WORKPLAN.yaml`
2. Identificar fase actual y próxima tarea `READY`
3. **Una sola tarea atómica por vez**
4. Mostrar diff y criterio de done al cerrar
5. No saltar tareas bloqueadas
6. No adelantar lógica funcional antes de cerrar la base

---

## 16) Anti-patterns — prohibidos

- Pedir o ejecutar dos tareas juntas
- Empezar features antes de que `docker compose up` funcione
- Commitear sin tests pasando
- Persistir sin pasar por `confirmation_node`
- Hardcodear LLM en código
- Mezclar SQLite con fuente funcional de verdad
- Ignorar webhooks duplicados
- Instalar dependencias fuera del stack congelado
- Dejar `CLAUDE.md` desactualizado al cerrar sesión

---

## 17) Estado actual del proyecto

**Fase activa:** FASE_1B — Grafo base y contratos de dominio
**Próxima tarea READY:** T-014 — AgentState (`src/graph/state.py`)

**FASE_1A — cerrada:**
- [x] T-001  carpetas + `requirements.txt` + `Dockerfile` + `docker compose up --build` funciona
- [x] T-002  `src/config.py` carga todos los LLMs y variables
- [x] T-003  `GET /health` responde 200 desde host en http://localhost:8000/health
- [x] T-004  pytest smoke pasa dentro del contenedor

**Completado en bootstrap:**
- [x] T-005  CLAUDE.md
- [x] T-006  WORKPLAN.yaml
- [x] T-007  AcceptanceCriteria.md
- [x] T-008  ThreatModel.md
- [x] T-009  DataHandling.md
- [x] T-010  DECISION_FREEZE.md
- [x] T-011  state_machine.yaml
- [x] T-012  START_HERE.md
- [x] T-013  .env.example

**Gate de salida FASE_1B — pendiente:**
- [ ] T-014  `src/graph/state.py` — AgentState TypedDict
- [ ] T-015  `src/graph/llm_factory.py` — LLM factory
- [ ] T-016  `src/domain/` — intents, schemas, confirmation
- [ ] T-017  `src/storage/` — bootstrap SQLite

---

## 18) Prompts canónicos de sesión

### Primera sesión

```
Leé docs/START_HERE.md, CLAUDE.md y WORKPLAN.yaml.
Decime en qué fase estamos y cuál es la próxima tarea READY.

Ejecutá SOLO T-001.
No hagas ninguna otra tarea.
No escribas implementación funcional.
Cuando termines, mostrame el diff y el criterio de done cumplido.
```

### Sesiones FASE_1A después de T-001 (T-002 a T-004)

```
Seguimos en FASE_1A — container-first.
Leé WORKPLAN.yaml e identificá la próxima tarea READY.
Ejecutá SOLO esa tarea.

Reglas:
- no implementes features funcionales
- no saltees dependencias
- el runtime tiene que vivir en Docker Compose
- mostrá el diff y el criterio de done cumplido
```
