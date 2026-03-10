# DECISION_FREEZE.md — asistente_personal v2.1

**Versión:** v2.1 | **Fecha:** 2026-03-10 | **Estado:** CONGELADO

Estas decisiones no se cambian sin crear una nueva versión del PRD y actualizar los artefactos afectados.

---

## Producto

- tipo: asistente personal individual
- canal único: WhatsApp
- idioma: español
- zona horaria: America/Montevideo

## Arquitectura

- motor multiagente: LangGraph
- checkpointer: SqliteSaver (SQLite)
- thread_id: número de WhatsApp del usuario
- comunicación entre agentes: function calling / tool use dentro del grafo
- entorno de desarrollo: **container-first con Docker Compose**

## LLMs por agente

| Agente             | Variable env       | Default           |
|--------------------|--------------------|-------------------|
| orchestrator       | LLM_ORCHESTRATOR   | claude-sonnet-4-6 |
| tasks_agent        | LLM_TASKS          | gpt-4o            |
| ideas_agent        | LLM_IDEAS          | claude-sonnet-4-6 |
| agenda_agent       | LLM_AGENDA         | gemini-2.0-flash  |
| accounting_agent   | LLM_ACCOUNTING     | gpt-4o            |
| reporting_agent    | LLM_REPORTING      | claude-sonnet-4-6 |

Cambiar el LLM de un agente = cambiar una variable de entorno. Sin tocar código.

## Fuentes de verdad

- tareas: Google Sheets
- contabilidad: Google Sheets (archivo separado)
- ideas: Google Docs (documento maestro con secciones)
- agenda: Google Calendar
- logging / estado / idempotencia: SQLite

## Docker — regla de entorno

- el contenedor entra en FASE_1A, antes de cualquier implementación funcional
- Dockerfile y docker-compose.yml se crean en los primeros slices del repo
- el runtime del servicio vive en Docker Compose
- no se acepta dockerizar al final

## Kanban — columnas fijas

- Pendiente
- En progreso
- Hoy
- Completada

## Confirmación previa

Nada persiste sin confirmación explícita del usuario.
El `reporting_agent` está exento: solo lectura, no necesita confirmación.

## Timeout de confirmación

- valor congelado: **30 minutos** desde `proposal_sent_at`
- si vence: estado `expired`
- efecto: no persiste nada

## Tareas

- crear: sí, con confirmación
- editar: sí, con confirmación
- mover entre columnas: sí, con confirmación
- completar: sí, con confirmación
- borrar: sí, con confirmación → físico en Sheets + log en SQLite `audit_logs`

## Ideas

- crear: sí, con confirmación
- editar: sí, con confirmación
- borrar: sí, con confirmación → físico del bloque en Docs + log en SQLite `audit_logs`

## Agenda

- crear: sí, con confirmación
- editar/reprogramar: sí, con confirmación
- cancelar: sí, con confirmación → evento marcado como `cancelled` en Calendar (no se elimina)

## Contabilidad

- crear: sí, con confirmación
- editar: sí, con confirmación + `correction_note` obligatoria
- borrar: **PROHIBIDO** — el `accounting_agent` no tiene herramienta de borrado

## reporting_agent

- solo lectura: sí
- pasa por confirmation_node: NO
- puede cruzar datos de múltiples dominios: sí
- herramientas de escritura: ninguna

## Multi-intención

Si un mensaje contiene varias acciones persistentes:
- el orquestador las descompone en `pending_actions` del AgentState
- el sistema confirma cada una por separado
- no se persiste nada sin confirmación individual

## Idempotencia

- usar `provider event id` de Twilio cuando exista
- fallback: hash normalizado de remitente + timestamp + body
- no se permite doble persistencia por webhook duplicado
- no se permite doble persistencia por doble confirmación

## Scheduler

- APScheduler in-process
- revisión: cada 15 minutos
- solo válido con una única instancia activa del servicio
- si vence un recordatorio durante una caída: estado `missed`
- no hay reenvío retroactivo por defecto

## Retención

| Dato                                    | Retención              |
|-----------------------------------------|------------------------|
| Sheets / Docs / Calendar                | Sin purga automática   |
| SQLite `processed_events`              | 30 días                |
| SQLite logs, conversation_state, reminder_jobs | 90 días         |
