---
status: APPROVED
version: v2.1
owner: Usuario principal
date_created: 2026-03-08
last_updated: 2026-03-10
project_tier: prototype
architecture: multiagent_langgraph
environment: container-first
canonical_paths:
  prd: docs/PRD_PROYECTO_ACTIVO.md
links:
  acceptance_criteria: docs/AcceptanceCriteria.md
  threat_model: docs/ThreatModel.md
  data_handling: docs/DataHandling.md
  decision_freeze: docs/DECISION_FREEZE.md
  workplan: WORKPLAN.yaml
  state_machine: state_machine.yaml
---

# PRD — Asistente Personal por WhatsApp (Multiagente LangGraph)

## Resumen ejecutivo

Sistema multiagente LangGraph operado por WhatsApp para organizar trabajo y vida personal. Cubre cuatro dominios: tareas en kanban, ideas y notas, agenda y recordatorios, administración contable de ingresos/egresos. Un agente de reporting responde consultas administrativas complejas cruzando múltiples dominios sin persistir.

Opera en español, zona horaria `America/Montevideo`. Toda acción persistente requiere confirmación explícita del usuario antes de ejecutarse. El entorno de desarrollo es container-first con Docker Compose.

---

## Problema / Oportunidad

El usuario necesita un sistema centralizado para tareas, agenda, ideas y finanzas personales. Hoy esos elementos se dispersan generando olvido, pérdida de ideas y baja visibilidad financiera. La oportunidad es usar WhatsApp —el canal más natural de uso diario— como interfaz principal, con confirmación previa para toda acción y un agente de reporting que permita consultas administrativas complejas.

---

## Objetivos

1. Aumentar la cantidad de tareas completadas por semana.
2. Centralizar captura de tareas, ideas, recordatorios e ingresos/egresos en WhatsApp.
3. Mantener un tablero kanban personal actualizado.
4. Conservar ideas con contexto suficiente para analizarlas y recuperarlas.
5. Gestionar agenda y recordatorios desde Google Calendar.
6. Llevar registro claro de ingresos, egresos, categorías y caja.
7. Responder consultas administrativas complejas cruzando múltiples dominios.
8. Evitar duplicados y escrituras erróneas mediante confirmación previa e idempotencia.

---

## Non-Goals

1. No atiende mensajes del público.
2. No funciona como asistente de atención al cliente.
3. No incluye CRM ni gestión comercial externa.
4. No incluye predicción financiera en el MVP.
5. No incluye facturación, impuestos ni contabilidad formal avanzada en el MVP.
6. No incluye operación multiusuario ni colaboración de equipo en el MVP.
7. No reemplaza herramientas contables profesionales.

---

## Arquitectura del sistema

### Modelo de ejecución

Grafo multiagente LangGraph. Cada mensaje de WhatsApp ingresa al grafo y fluye entre nodos especializados hasta producir una respuesta y, si corresponde, una acción persistente confirmada.

### Nodos del grafo

| Nodo                | Rol                                                                         | LLM               |
|---------------------|-----------------------------------------------------------------------------|-------------------|
| `orchestrator`      | Clasifica intención y dominio. Rutea. Gestiona multi-intención.             | `LLM_ORCHESTRATOR`|
| `tasks_agent`       | Propone payload de tarea. Herramientas: leer/proponer en Sheets.            | `LLM_TASKS`       |
| `ideas_agent`       | Propone payload de idea. Herramientas: leer/proponer en Docs.               | `LLM_IDEAS`       |
| `agenda_agent`      | Propone payload de evento. Herramientas: leer/proponer en Calendar.         | `LLM_AGENDA`      |
| `accounting_agent`  | Propone payload contable. Herramientas: leer/proponer en Sheets contab.     | `LLM_ACCOUNTING`  |
| `reporting_agent`   | Responde consultas complejas. Solo lectura. No pasa por confirmation_node.  | `LLM_REPORTING`   |
| `confirmation_node` | Envía propuesta. Espera y normaliza confirmación. Gestiona timeout 30min.   | —                 |
| `persist_node`      | Ejecuta escritura en la fuente de verdad del dominio.                       | —                 |

### AgentState — campos

```
message, intent, domain, payload,
confirmation_status, pending_actions,
agent_response, conversation_history,
idempotency_key, error
```

### Checkpointer

LangGraph `SqliteSaver` con SQLite como backend.
Persiste el `AgentState` completo entre mensajes del mismo `thread_id` (= número de WhatsApp del usuario).

### LLMs

Cada agente lee su LLM desde variable de entorno. Compatible con Claude, GPT-4o, Gemini, DeepSeek.
Cambiar el LLM de un agente no requiere modificar código.

---

## Actores

**Usuario principal:** persona única que opera el asistente.
**Agentes IA:** orquestador + 5 agentes especializados gestionados por LangGraph.
**Sistemas externos:** WhatsApp (Twilio), Google Sheets ×2, Google Docs, Google Calendar, SQLite.

---

## Flujos principales

### Flujo 1 — Acción persistente simple
1. Usuario envía mensaje.
2. Orquestador clasifica intención y dominio → deriva al agente.
3. Agente propone payload estructurado.
4. `confirmation_node` envía propuesta al usuario.
5. Usuario confirma (ventana: 30 minutos).
6. `persist_node` escribe en la fuente de verdad.

### Flujo 2 — Consulta (sin persistencia)
1. Usuario pide información.
2. Orquestador identifica `query` → deriva a `reporting_agent`.
3. `reporting_agent` lee fuentes necesarias y sintetiza respuesta.
4. Respuesta directa al usuario. Sin pasar por `confirmation_node`.

### Flujo 3 — Multi-intención
1. Mensaje contiene múltiples acciones persistentes.
2. Orquestador las descompone en `pending_actions`.
3. El sistema propone y confirma cada una por separado.
4. Cada acción solo persiste tras su confirmación individual.

### Flujo 4 — Timeout
1. Sistema envía propuesta.
2. Usuario no responde en 30 minutos.
3. Estado → `expired`. No persiste nada.

---

## Requisitos funcionales

### Canal e interacción
- **RF-001** El sistema opera por WhatsApp como único canal del MVP.
- **RF-002** El sistema interactúa en español.
- **RF-003** El sistema usa zona horaria `America/Montevideo` para agenda, recordatorios y referencias temporales.
- **RF-004** El orquestador detecta automáticamente el dominio y deriva al agente correcto.
- **RF-005** El sistema permite que el usuario indique explícitamente el tipo de registro.
- **RF-006** El sistema pide confirmación antes de registrar cualquier dato.
- **RF-007** El sistema pide confirmación antes de editar cualquier dato.
- **RF-008** El sistema pide confirmación antes de borrar tareas o ideas.
- **RF-009** El sistema no permite borrar movimientos contables.
- **RF-010** El sistema descompone mensajes multi-intención y confirma cada acción por separado.

### Agente de tareas
- **RF-011** Registra tareas en Google Sheets.
- **RF-012** Kanban con columnas: Pendiente, En progreso, Hoy, Completada.
- **RF-013** Crear tareas por chat con confirmación.
- **RF-014** Mover tareas entre columnas con confirmación.
- **RF-015** Completar tareas con confirmación.
- **RF-016** Editar tareas con confirmación.
- **RF-017** Borrar tareas con confirmación. Borrado físico en Sheets + log SQLite.
- **RF-018** Consultar tareas por estado incluyendo tareas de hoy.

### Agente de ideas
- **RF-019** Registra ideas en Google Docs.
- **RF-020** Documento maestro con secciones por tema.
- **RF-021** Propone para cada idea: tema, resumen, prioridad, estado, fecha, tags.
- **RF-022** Editar ideas con confirmación.
- **RF-023** Borrar ideas con confirmación. Borrado físico del bloque + log SQLite.
- **RF-024** Buscar y recuperar ideas por tema, tags o contenido.

### Agente de agenda
- **RF-025** Registra eventos y recordatorios en Google Calendar.
- **RF-026** Crear, editar, reprogramar y cancelar eventos con confirmación.
- **RF-027** Acepta recordatorios puntuales y recurrentes.
- **RF-028** El scheduler revisa pendientes cada 15 minutos.
- **RF-029** Envía recordatorios por WhatsApp a la hora indicada.
- **RF-030** Consultar agenda y recordatorios futuros.
- **RF-031** Cancelar un evento lo marca como `cancelled` en Calendar (no lo elimina).
- **RF-032** Recordatorios vencidos durante caída del servicio → `missed`. Sin reenvío retroactivo.

### Agente contable
- **RF-033** Registra ingresos y egresos en Google Sheets (archivo separado).
- **RF-034** Registros incluyen: tipo, categoría, monto, nota, fecha, id, balance.
- **RF-035** Editar movimientos con confirmación.
- **RF-036** Toda edición agrega `correction_note`.
- **RF-037** Consultar ingresos, egresos, categorías y caja.
- **RF-038** Resúmenes semanales de ingresos y egresos.
- **RF-039** Consultar saldo actual de caja.

### Agente de reporting
- **RF-040** Responde consultas administrativas complejas cruzando múltiples dominios.
- **RF-041** Puede comparar gastos e ingresos por categoría y período.
- **RF-042** Puede generar resúmenes semanales y mensuales de contabilidad.
- **RF-043** Puede responder sobre productividad de tareas por período.
- **RF-044** Puede sintetizar agenda + tareas en vista de "qué tengo hoy/esta semana".
- **RF-045** Accede a las fuentes en modo lectura exclusivamente. Nunca persiste.

### Integridad y trazabilidad
- **RF-046** Muestra al usuario el payload propuesto antes de persistir.
- **RF-047** No persiste si el usuario no confirma.
- **RF-048** Evita doble persistencia ante webhooks duplicados o dobles confirmaciones.
- **RF-049** Registra en SQLite estado conversacional, confirmaciones y eventos procesados sin reemplazar las fuentes de verdad.

---

## Requisitos no funcionales

- **RNF-001** Experiencia simple y operable desde WhatsApp.
- **RNF-002** Consistencia entre conversación y bases conectadas.
- **RNF-003** Responde en español claro.
- **RNF-004** Trazabilidad básica de registros, ediciones y confirmaciones.
- **RNF-005** Minimiza registros incorrectos mediante confirmación previa.
- **RNF-006** Logging básico de acciones ejecutadas, rechazadas y deduplicadas.
- **RNF-007** Acceso restringido al usuario principal.
- **RNF-008** Datos financieros y de agenda tratados como información sensible personal.
- **RNF-009** Se puede auditar cuándo un movimiento contable fue corregido.
- **RNF-010** Scheduler revisa vencimientos cada 15 minutos.
- **RNF-011** Archivos separados por dominio funcional.
- **RNF-012** Prioriza exactitud sobre automatización agresiva.
- **RNF-013** Idempotente frente a eventos duplicados de entrada.
- **RNF-014** APScheduler in-process solo válido con instancia única activa.
- **RNF-015** LLM de cada agente configurable por variable de entorno sin cambiar código.
- **RNF-016** LangGraph checkpointer usa SQLite para persistir estado entre mensajes.
- **RNF-017** El entorno de desarrollo es container-first con Docker Compose.

---

## Datos

### Retención
- Sheets / Docs / Calendar: sin purga automática en el MVP.
- SQLite `processed_events`: 30 días.
- SQLite logs, conversation_state, reminder_jobs: 90 días.

### PII / datos sensibles
- El sistema maneja datos sensibles personales y financieros básicos.
- No solicita datos extra no necesarios para la función pedida.
- Ninguna credencial se commitea en el repositorio.

---

## Métricas de éxito

**KPI principal:** aumento en la cantidad de tareas completadas por semana.

**KPIs secundarios:**
- Tareas creadas y movidas correctamente en el kanban.
- Ideas registradas y recuperadas por tema.
- Recordatorios enviados a horario.
- Disponibilidad de resumen semanal de ingresos/egresos.
- Consultas de reporting respondidas correctamente.
- Eventos duplicados absorbidos sin doble persistencia.

---

## Criterios de aceptación del sistema

1. El usuario puede registrar tarea, idea, evento e ingreso/egreso desde WhatsApp con confirmación previa.
2. El reporting_agent responde consultas administrativas complejas correctamente.
3. Ningún agente persiste sin pasar por confirmation_node.
4. Webhook duplicado no genera doble persistencia.
5. El grafo LangGraph rutea correctamente a cada agente.
6. Los recordatorios se disparan a horario en `America/Montevideo`.
7. El sistema levanta con `docker compose up` y `/health` responde 200.
8. Deploy operativo en Railway o Render.

---

## Historial de versiones

| Versión | Fecha      | Cambio                                                    |
|---------|------------|-----------------------------------------------------------|
| v1.1    | 2026-03-08 | Versión single-agent (descartada)                        |
| v2.0    | 2026-03-10 | Rediseño completo: arquitectura multiagente LangGraph     |
| v2.1    | 2026-03-10 | Container-first formalizado como decisión de arquitectura |
