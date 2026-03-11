# AcceptanceCriteria.md — asistente_personal v2.0

**Versión:** v2.0 | **Fecha:** 2026-03-11 | **Fuente:** docs/PRD_PROYECTO_ACTIVO.md

---

## Convención

Campos por AC: `id` | `source_requirement` | `domain` | `description` | `verification_type` | `status`

Tipos: `unit` | `integration` | `e2e` | `manual`
Estados: `pending` | `in_progress` | `passed` | `failed` | `blocked`

Estado real al cierre de T-036:
- `passed`:      verificado por tests automatizados en el codebase actual.
- `in_progress`: agente implementado con mocks; conector real no integrado.
- `blocked`:     requiere conector real, deploy en producción, o verificación manual.

---

## 1) Canal e interacción

### AC-CORE-001
- source_requirement: RF-001
- domain: core
- description: El sistema usa WhatsApp como único canal del MVP.
- verification_type: e2e
- status: blocked
- note: Requiere Twilio real en producción (T-037/T-038).

### AC-CORE-002
- source_requirement: RF-002
- domain: core
- description: El sistema responde siempre en español.
- verification_type: e2e
- status: in_progress
- note: Orquestador y agentes responden en español (mocks). Requiere LLM real para e2e.

### AC-CORE-003
- source_requirement: RF-003
- domain: core
- description: El sistema interpreta fechas y horas usando America/Montevideo en todos los dominios.
- verification_type: integration
- status: passed
- test: tests/test_timezone.py

### AC-CORE-004
- source_requirement: RF-006, RF-007, RF-008, RF-047
- domain: core
- description: Ningún agente persiste datos sin pasar por confirmation_node.
- verification_type: e2e
- status: passed
- test: tests/test_confirmation_integrity.py, tests/test_full_flow.py

### AC-CORE-005
- source_requirement: RF-010
- domain: core
- description: El sistema descompone mensajes multi-intención en propuestas separadas y confirma cada una individualmente.
- verification_type: e2e
- status: passed
- test: tests/test_edge_cases.py (TestMultiIntencion)

---

## 2) Grafo multiagente

### AC-GRAPH-001
- source_requirement: PRD §Arquitectura
- domain: graph
- description: El grafo LangGraph compila y rutea correctamente a los 5 agentes especializados.
- verification_type: integration
- status: passed
- test: tests/test_graph_reporting.py (TestRoutingOrquestador), tests/test_graph_base.py

### AC-GRAPH-002
- source_requirement: RNF-015
- domain: graph
- description: El LLM de cada agente es configurable por variable de entorno sin cambiar código.
- verification_type: unit
- status: passed
- test: tests/test_llm_factory.py

### AC-GRAPH-003
- source_requirement: RNF-016
- domain: graph
- description: El LangGraph checkpointer (SqliteSaver) persiste el AgentState entre mensajes del mismo thread_id.
- verification_type: integration
- status: passed
- test: tests/test_graph_reporting.py (test_sqlitesaver_persiste_estado_entre_queries)

### AC-GRAPH-004
- source_requirement: RF-004
- domain: graph
- description: El orquestador pide aclaración cuando la intención es ambigua o el dominio es incierto, sin derivar a persistencia.
- verification_type: unit
- status: passed
- test: tests/test_orchestrator.py, tests/test_orchestrator_es.py

---

## 3) Agente de tareas

### AC-TASK-001
- source_requirement: RF-011, RF-013
- domain: tasks
- description: El usuario puede crear una tarea por WhatsApp y verla registrada en Google Sheets con confirmación previa.
- verification_type: e2e
- status: in_progress
- note: tasks_agent + confirmation_node implementados y testeados con mocks. sheets_tasks sin integración real (T-037).

### AC-TASK-002
- source_requirement: RF-012
- domain: tasks
- description: El kanban usa exactamente estas columnas: Pendiente, En progreso, Hoy, Completada.
- verification_type: integration
- status: passed
- test: tests/test_e2e.py (test_tasks_agent_status_kanban_valido), tests/test_tasks_agent.py

### AC-TASK-003
- source_requirement: RF-014, RF-015, RF-016
- domain: tasks
- description: El usuario puede mover, completar y editar tareas con confirmación previa.
- verification_type: e2e
- status: in_progress
- note: tasks_agent implementa update/read. Conector Sheets real pendiente (T-037).

### AC-TASK-004
- source_requirement: RF-017
- domain: tasks
- description: El usuario puede borrar tareas con confirmación previa. El borrado es físico en Sheets con log en SQLite.
- verification_type: e2e
- status: in_progress
- note: tasks_agent implementa delete. Conector Sheets real pendiente (T-037).

### AC-TASK-005
- source_requirement: RF-018
- domain: tasks
- description: El usuario puede consultar tareas por estado incluyendo tareas de hoy.
- verification_type: integration
- status: passed
- test: tests/test_tasks_agent.py, tests/test_reporting_queries.py (TestQueTengoHoy)

---

## 4) Agente de ideas

### AC-IDEA-001
- source_requirement: RF-019, RF-020
- domain: ideas
- description: El sistema guarda ideas en Google Docs en un documento maestro con secciones.
- verification_type: integration
- status: in_progress
- note: ideas_agent implementado con mocks. Conector Docs real pendiente (T-037).

### AC-IDEA-002
- source_requirement: RF-021
- domain: ideas
- description: Antes de guardar, el agente propone: tema, resumen, prioridad, estado, fecha y tags.
- verification_type: e2e
- status: in_progress
- note: ideas_agent propone campos canónicos. Flujo con Twilio real pendiente (T-037).

### AC-IDEA-003
- source_requirement: RF-022, RF-023
- domain: ideas
- description: El usuario puede editar y borrar ideas con confirmación previa. El borrado es físico en Docs con log en SQLite.
- verification_type: e2e
- status: in_progress
- note: ideas_agent implementa update/delete. Conector Docs real pendiente (T-037).

### AC-IDEA-004
- source_requirement: RF-024
- domain: ideas
- description: El usuario puede recuperar ideas por tema, tags o contenido.
- verification_type: integration
- status: in_progress
- note: ideas_agent implementa read. Conector Docs real pendiente (T-037).

---

## 5) Agente de agenda

### AC-AGENDA-001
- source_requirement: RF-025, RF-026
- domain: agenda
- description: El usuario puede crear, editar y reprogramar eventos con confirmación previa.
- verification_type: e2e
- status: in_progress
- note: agenda_agent implementado con mocks. Conector Calendar real pendiente (T-037).

### AC-AGENDA-002
- source_requirement: RF-031
- domain: agenda
- description: Cancelar un evento lo marca como cancelled en Google Calendar (no lo elimina).
- verification_type: integration
- status: in_progress
- note: agenda_agent usa operation=cancel (no delete). Conector Calendar real pendiente (T-037).

### AC-AGENDA-003
- source_requirement: RF-027
- domain: agenda
- description: El sistema acepta eventos puntuales y recurrentes.
- verification_type: integration
- status: in_progress
- note: agenda_agent acepta campo recurrence (RRULE). Conector Calendar real pendiente (T-037).

### AC-AGENDA-004
- source_requirement: RF-028, RF-029
- domain: agenda
- description: El scheduler revisa pendientes cada 15 minutos y envía recordatorios por WhatsApp a horario en America/Montevideo.
- verification_type: e2e
- status: passed
- test: tests/test_scheduler_job.py (TestRegisterReminderJob), tests/test_scheduler_simulation.py, tests/test_timezone.py

### AC-AGENDA-005
- source_requirement: RF-032
- domain: agenda
- description: Los recordatorios vencidos durante una caída del servicio se marcan como missed sin reenvío retroactivo.
- verification_type: integration
- status: passed
- test: tests/test_scheduler_simulation.py (TestCaidaYMissed)

### AC-AGENDA-006
- source_requirement: RF-030
- domain: agenda
- description: El usuario puede consultar agenda y recordatorios futuros.
- verification_type: integration
- status: in_progress
- note: agenda_agent implementa read. Conector Calendar real pendiente (T-037).

---

## 6) Agente contable

### AC-ACC-001
- source_requirement: RF-033, RF-034
- domain: accounting
- description: El usuario puede registrar ingresos y egresos con tipo, categoría, monto, nota, id, fecha y balance.
- verification_type: e2e
- status: in_progress
- note: accounting_agent implementado con mocks. Conector Sheets real pendiente (T-037).

### AC-ACC-002
- source_requirement: RF-035, RF-036
- domain: accounting
- description: El usuario puede editar un movimiento contable con confirmación previa y la edición deja correction_note.
- verification_type: e2e
- status: in_progress
- note: accounting_agent requiere correction_note en update. Conector Sheets real pendiente (T-037).

### AC-ACC-003
- source_requirement: RF-009
- domain: accounting
- description: El sistema no permite borrar movimientos contables. El accounting_agent no tiene herramienta de borrado.
- verification_type: e2e
- status: passed
- test: tests/test_confirmation_integrity.py (TestAccountingNoBorrado), tests/test_e2e.py (TestFlujoAccounting)

### AC-ACC-004
- source_requirement: RF-037, RF-038, RF-039
- domain: accounting
- description: El usuario puede consultar ingresos, egresos, categorías, saldo actual y resúmenes semanales.
- verification_type: integration
- status: passed
- test: tests/test_reporting_queries.py (TestGastosPorCategoria, TestResumenContable)

---

## 7) Agente de reporting

### AC-REP-001
- source_requirement: RF-040, RF-041
- domain: reporting
- description: El reporting_agent responde consultas complejas cruzando datos de múltiples dominios.
- verification_type: integration
- status: passed
- test: tests/test_e2e.py (test_reporting_consulta_cruzada_todos_dominios), tests/test_reporting_queries.py

### AC-REP-002
- source_requirement: RF-041, RF-042
- domain: reporting
- description: El agente puede comparar gastos/ingresos por categoría y período, y generar resúmenes semanales y mensuales.
- verification_type: integration
- status: passed
- test: tests/test_reporting_queries.py (TestGastosPorCategoria, TestResumenContable)

### AC-REP-003
- source_requirement: RF-043
- domain: reporting
- description: El agente puede responder sobre productividad de tareas por período.
- verification_type: integration
- status: passed
- test: tests/test_reporting_queries.py (TestProductividadTareas)

### AC-REP-004
- source_requirement: RF-044
- domain: reporting
- description: El agente puede sintetizar agenda y tareas en una vista de qué hay para hoy o esta semana.
- verification_type: integration
- status: passed
- test: tests/test_reporting_queries.py (TestQueTengoHoy)

### AC-REP-005
- source_requirement: RF-045
- domain: reporting
- description: El reporting_agent nunca persiste datos. No tiene herramientas de escritura. No pasa por confirmation_node.
- verification_type: unit
- status: passed
- test: tests/test_confirmation_integrity.py (TestReportingAgentSoloLectura), tests/test_reporting_agent.py (TestFetchersSoloLectura)

---

## 8) Idempotencia y trazabilidad

### AC-IDEMP-001
- source_requirement: RF-048, RNF-013
- domain: idempotency
- description: Un webhook duplicado de Twilio no genera doble persistencia.
- verification_type: integration
- status: passed
- test: tests/test_idempotency.py (TestWebhookIdempotencia)

### AC-IDEMP-002
- source_requirement: RF-048
- domain: idempotency
- description: Una doble confirmación del mismo evento no genera doble escritura.
- verification_type: integration
- status: passed
- test: tests/test_idempotency.py (TestDobleConfirmacion)

### AC-IDEMP-003
- source_requirement: RF-049
- domain: sqlite
- description: SQLite registra acciones ejecutadas y rechazadas sin actuar como fuente funcional de verdad.
- verification_type: integration
- status: in_progress
- note: Tablas audit_logs y processed_events creadas. Escritura en audit_logs pendiente de persist_node real.

### AC-IDEMP-004
- source_requirement: docs/DECISION_FREEZE.md
- domain: idempotency
- description: La clave de idempotencia usa provider event id cuando existe; fallback a hash(remitente+timestamp+body).
- verification_type: unit
- status: passed
- test: tests/test_webhook.py (TestIdempotencyKey)

---

## 9) Confirmación y timeout

### AC-CONF-001
- source_requirement: docs/DECISION_FREEZE.md
- domain: confirmation
- description: El timeout de confirmación es de 30 minutos. Si vence, el estado es expired y no se persiste nada.
- verification_type: integration
- status: passed
- test: tests/test_edge_cases.py (TestTimeoutExpira), tests/test_confirmation_node.py

---

## 10) Exclusiones del MVP

### AC-SCOPE-001
- source_requirement: Non-Goals
- domain: scope
- description: El sistema no atiende mensajes del público, no soporta multiusuario y no implementa predicción financiera.
- verification_type: manual
- status: blocked
- note: Verificación manual en producción (T-039).

---

## 11) Criterios de cierre del MVP

### AC-REL-001
- source_requirement: PRD §Criterios de aceptación
- domain: release
- description: Los 5 agentes especializados funcionan correctamente en el grafo LangGraph.
- verification_type: e2e
- status: in_progress
- note: 5 agentes implementados y testeados con mocks. reporting_agent wired en graph.py; otros 4 pendientes de wiring real y conectores (T-037).

### AC-REL-002
- source_requirement: PRD §Criterios de aceptación
- domain: release
- description: Ningún flujo crítico de persistencia ocurre sin confirmación explícita del usuario.
- verification_type: e2e
- status: passed
- test: tests/test_confirmation_integrity.py, tests/test_full_flow.py, tests/test_edge_cases.py

### AC-REL-003
- source_requirement: PRD §Criterios de aceptación
- domain: release
- description: El reporting_agent responde correctamente consultas financieras y de productividad.
- verification_type: e2e
- status: passed
- test: tests/test_reporting_queries.py, tests/test_graph_reporting.py
