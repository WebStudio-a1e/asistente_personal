# AcceptanceCriteria.md — asistente_personal v2.0

**Versión:** v2.0 | **Fecha:** 2026-03-10 | **Fuente:** docs/PRD_PROYECTO_ACTIVO.md

---

## Convención

Campos por AC: `id` | `source_requirement` | `domain` | `description` | `verification_type` | `status`

Tipos: `unit` | `integration` | `e2e` | `manual`
Estados: `pending` | `in_progress` | `passed` | `failed` | `blocked`

---

## 1) Canal e interacción

### AC-CORE-001
- source_requirement: RF-001
- domain: core
- description: El sistema usa WhatsApp como único canal del MVP.
- verification_type: e2e
- status: pending

### AC-CORE-002
- source_requirement: RF-002
- domain: core
- description: El sistema responde siempre en español.
- verification_type: e2e
- status: pending

### AC-CORE-003
- source_requirement: RF-003
- domain: core
- description: El sistema interpreta fechas y horas usando America/Montevideo en todos los dominios.
- verification_type: integration
- status: pending

### AC-CORE-004
- source_requirement: RF-006, RF-007, RF-008, RF-047
- domain: core
- description: Ningún agente persiste datos sin pasar por confirmation_node.
- verification_type: e2e
- status: pending

### AC-CORE-005
- source_requirement: RF-010
- domain: core
- description: El sistema descompone mensajes multi-intención en propuestas separadas y confirma cada una individualmente.
- verification_type: e2e
- status: pending

---

## 2) Grafo multiagente

### AC-GRAPH-001
- source_requirement: PRD §Arquitectura
- domain: graph
- description: El grafo LangGraph compila y rutea correctamente a los 5 agentes especializados.
- verification_type: integration
- status: pending

### AC-GRAPH-002
- source_requirement: RNF-015
- domain: graph
- description: El LLM de cada agente es configurable por variable de entorno sin cambiar código.
- verification_type: unit
- status: pending

### AC-GRAPH-003
- source_requirement: RNF-016
- domain: graph
- description: El LangGraph checkpointer (SqliteSaver) persiste el AgentState entre mensajes del mismo thread_id.
- verification_type: integration
- status: pending

### AC-GRAPH-004
- source_requirement: RF-004
- domain: graph
- description: El orquestador pide aclaración cuando la intención es ambigua o el dominio es incierto, sin derivar a persistencia.
- verification_type: unit
- status: pending

---

## 3) Agente de tareas

### AC-TASK-001
- source_requirement: RF-011, RF-013
- domain: tasks
- description: El usuario puede crear una tarea por WhatsApp y verla registrada en Google Sheets con confirmación previa.
- verification_type: e2e
- status: pending

### AC-TASK-002
- source_requirement: RF-012
- domain: tasks
- description: El kanban usa exactamente estas columnas: Pendiente, En progreso, Hoy, Completada.
- verification_type: integration
- status: pending

### AC-TASK-003
- source_requirement: RF-014, RF-015, RF-016
- domain: tasks
- description: El usuario puede mover, completar y editar tareas con confirmación previa.
- verification_type: e2e
- status: pending

### AC-TASK-004
- source_requirement: RF-017
- domain: tasks
- description: El usuario puede borrar tareas con confirmación previa. El borrado es físico en Sheets con log en SQLite.
- verification_type: e2e
- status: pending

### AC-TASK-005
- source_requirement: RF-018
- domain: tasks
- description: El usuario puede consultar tareas por estado incluyendo tareas de hoy.
- verification_type: integration
- status: pending

---

## 4) Agente de ideas

### AC-IDEA-001
- source_requirement: RF-019, RF-020
- domain: ideas
- description: El sistema guarda ideas en Google Docs en un documento maestro con secciones.
- verification_type: integration
- status: pending

### AC-IDEA-002
- source_requirement: RF-021
- domain: ideas
- description: Antes de guardar, el agente propone: tema, resumen, prioridad, estado, fecha y tags.
- verification_type: e2e
- status: pending

### AC-IDEA-003
- source_requirement: RF-022, RF-023
- domain: ideas
- description: El usuario puede editar y borrar ideas con confirmación previa. El borrado es físico en Docs con log en SQLite.
- verification_type: e2e
- status: pending

### AC-IDEA-004
- source_requirement: RF-024
- domain: ideas
- description: El usuario puede recuperar ideas por tema, tags o contenido.
- verification_type: integration
- status: pending

---

## 5) Agente de agenda

### AC-AGENDA-001
- source_requirement: RF-025, RF-026
- domain: agenda
- description: El usuario puede crear, editar y reprogramar eventos con confirmación previa.
- verification_type: e2e
- status: pending

### AC-AGENDA-002
- source_requirement: RF-031
- domain: agenda
- description: Cancelar un evento lo marca como cancelled en Google Calendar (no lo elimina).
- verification_type: integration
- status: pending

### AC-AGENDA-003
- source_requirement: RF-027
- domain: agenda
- description: El sistema acepta eventos puntuales y recurrentes.
- verification_type: integration
- status: pending

### AC-AGENDA-004
- source_requirement: RF-028, RF-029
- domain: agenda
- description: El scheduler revisa pendientes cada 15 minutos y envía recordatorios por WhatsApp a horario en America/Montevideo.
- verification_type: e2e
- status: pending

### AC-AGENDA-005
- source_requirement: RF-032
- domain: agenda
- description: Los recordatorios vencidos durante una caída del servicio se marcan como missed sin reenvío retroactivo.
- verification_type: integration
- status: pending

### AC-AGENDA-006
- source_requirement: RF-030
- domain: agenda
- description: El usuario puede consultar agenda y recordatorios futuros.
- verification_type: integration
- status: pending

---

## 6) Agente contable

### AC-ACC-001
- source_requirement: RF-033, RF-034
- domain: accounting
- description: El usuario puede registrar ingresos y egresos con tipo, categoría, monto, nota, id, fecha y balance.
- verification_type: e2e
- status: pending

### AC-ACC-002
- source_requirement: RF-035, RF-036
- domain: accounting
- description: El usuario puede editar un movimiento contable con confirmación previa y la edición deja correction_note.
- verification_type: e2e
- status: pending

### AC-ACC-003
- source_requirement: RF-009
- domain: accounting
- description: El sistema no permite borrar movimientos contables. El accounting_agent no tiene herramienta de borrado.
- verification_type: e2e
- status: pending

### AC-ACC-004
- source_requirement: RF-037, RF-038, RF-039
- domain: accounting
- description: El usuario puede consultar ingresos, egresos, categorías, saldo actual y resúmenes semanales.
- verification_type: integration
- status: pending

---

## 7) Agente de reporting

### AC-REP-001
- source_requirement: RF-040, RF-041
- domain: reporting
- description: El reporting_agent responde consultas complejas cruzando datos de múltiples dominios.
- verification_type: integration
- status: pending

### AC-REP-002
- source_requirement: RF-041, RF-042
- domain: reporting
- description: El agente puede comparar gastos/ingresos por categoría y período, y generar resúmenes semanales y mensuales.
- verification_type: integration
- status: pending

### AC-REP-003
- source_requirement: RF-043
- domain: reporting
- description: El agente puede responder sobre productividad de tareas por período.
- verification_type: integration
- status: pending

### AC-REP-004
- source_requirement: RF-044
- domain: reporting
- description: El agente puede sintetizar agenda y tareas en una vista de qué hay para hoy o esta semana.
- verification_type: integration
- status: pending

### AC-REP-005
- source_requirement: RF-045
- domain: reporting
- description: El reporting_agent nunca persiste datos. No tiene herramientas de escritura. No pasa por confirmation_node.
- verification_type: unit
- status: pending

---

## 8) Idempotencia y trazabilidad

### AC-IDEMP-001
- source_requirement: RF-048, RNF-013
- domain: idempotency
- description: Un webhook duplicado de Twilio no genera doble persistencia.
- verification_type: integration
- status: pending

### AC-IDEMP-002
- source_requirement: RF-048
- domain: idempotency
- description: Una doble confirmación del mismo evento no genera doble escritura.
- verification_type: integration
- status: pending

### AC-IDEMP-003
- source_requirement: RF-049
- domain: sqlite
- description: SQLite registra acciones ejecutadas y rechazadas sin actuar como fuente funcional de verdad.
- verification_type: integration
- status: pending

### AC-IDEMP-004
- source_requirement: docs/DECISION_FREEZE.md
- domain: idempotency
- description: La clave de idempotencia usa provider event id cuando existe; fallback a hash(remitente+timestamp+body).
- verification_type: unit
- status: pending

---

## 9) Confirmación y timeout

### AC-CONF-001
- source_requirement: docs/DECISION_FREEZE.md
- domain: confirmation
- description: El timeout de confirmación es de 30 minutos. Si vence, el estado es expired y no se persiste nada.
- verification_type: integration
- status: pending

---

## 10) Exclusiones del MVP

### AC-SCOPE-001
- source_requirement: Non-Goals
- domain: scope
- description: El sistema no atiende mensajes del público, no soporta multiusuario y no implementa predicción financiera.
- verification_type: manual
- status: pending

---

## 11) Criterios de cierre del MVP

### AC-REL-001
- source_requirement: PRD §Criterios de aceptación
- domain: release
- description: Los 5 agentes especializados funcionan correctamente en el grafo LangGraph.
- verification_type: e2e
- status: pending

### AC-REL-002
- source_requirement: PRD §Criterios de aceptación
- domain: release
- description: Ningún flujo crítico de persistencia ocurre sin confirmación explícita del usuario.
- verification_type: e2e
- status: pending

### AC-REL-003
- source_requirement: PRD §Criterios de aceptación
- domain: release
- description: El reporting_agent responde correctamente consultas financieras y de productividad.
- verification_type: e2e
- status: pending
