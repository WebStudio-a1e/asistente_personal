# DataHandling.md — asistente_personal v2.0

**Versión:** v2.0 | **Fecha:** 2026-03-10 | **Estado:** ACTIVO

---

## 1) Regla principal

Nada se persiste sin confirmación explícita del usuario. Todo agente que escribe pasa obligatoriamente por `confirmation_node` antes de ejecutar la escritura.

El `reporting_agent` es de **solo lectura**. Nunca pasa por `confirmation_node`.

---

## 2) Fuentes de verdad por dominio

| Dominio | Fuente de verdad | Agente responsable |
|---|---|---|
| Tareas | Google Sheets — hoja "Tareas" | `tasks_agent` |
| Contabilidad | Google Sheets — archivo separado | `accounting_agent` |
| Ideas | Google Docs — documento maestro con secciones | `ideas_agent` |
| Agenda | Google Calendar | `agenda_agent` |
| Consultas complejas | Todos los dominios (lectura) | `reporting_agent` |
| Checkpointer LangGraph | SQLite — `SqliteSaver` | automático |
| Soporte operativo | SQLite — tablas propias | interno |

En caso de conflicto: **Google Sheets/Docs/Calendar > SQLite > memoria de conversación.**

---

## 3) Contratos funcionales mínimos

### Tarea
- id: str
- title: str
- status: pending | in_progress | today | completed
- created_at: datetime (America/Montevideo)
- updated_at: datetime (America/Montevideo)
- source: whatsapp
- notes: str | null

### Idea
- id: str
- raw_text: str
- theme: str
- summary: str
- priority: low | medium | high
- status: active | archived
- tags: list[str]
- created_at: datetime (America/Montevideo)

### Evento / Recordatorio
- id: str
- title: str
- scheduled_for: datetime (America/Montevideo)
- recurrence: str | null
- notes: str | null
- status: active | cancelled
- source: whatsapp

### Movimiento contable
- id: str
- date: datetime (America/Montevideo)
- type: income | expense
- category: str
- amount: decimal
- note: str
- balance: decimal | null
- correction_note: str | null

---

## 4) Qué guarda cada sistema

### Google Sheets — Tareas
Guarda: id, título, estado/columna, timestamps, notas.
No guarda: estado conversacional, mensajes webhook crudos.

### Google Sheets — Contabilidad
Guarda: type, category, amount, note, date, id, balance, correction_note si aplica.
No guarda: mensajes crudos, estados transitorios.

### Google Docs — Ideas
Guarda: raw_text, theme, summary, priority, status, tags, created_at.
Estructura: documento maestro con secciones por tema.

### Google Calendar — Agenda
Guarda: title, scheduled_for, recurrence, notes, status.
Timezone: America/Montevideo en todo momento.
Cancelación: marcar como `cancelled` — no eliminar el evento.

### SQLite — Rol dual

**Rol 1 — LangGraph Checkpointer (gestionado automáticamente por LangGraph):**
Persiste el `AgentState` completo entre mensajes del mismo `thread_id`. Usa las tablas internas de `SqliteSaver`.

**Rol 2 — Soporte operativo (tablas propias):**

| Tabla | Contenido | Retención |
|---|---|---|
| `inbound_messages` | Mensajes recibidos de Twilio | 90 días |
| `conversation_state` | Estado conversacional activo | 90 días |
| `confirmation_requests` | Propuestas esperando confirmación | 90 días |
| `processed_events` | Eventos procesados para idempotencia | 30 días |
| `reminder_jobs` | Estado de jobs del scheduler | 90 días |
| `audit_logs` | Log de acciones ejecutadas y rechazadas | 90 días |

**SQLite no es fuente funcional de verdad de ningún dominio.**

---

## 5) Política de edición por dominio

### Tareas
- Editar con confirmación.
- Mover entre columnas con confirmación.

### Ideas
- Editar con confirmación.

### Agenda
- Crear, editar, reprogramar y cancelar con confirmación.
- Cancelar = marcar evento como `cancelled` en Google Calendar. No eliminar.

### Contabilidad
- Editar con confirmación.
- Toda edición deja `correction_note`.

---

## 6) Política de borrado por dominio

### Tareas
- Borrado físico en Google Sheets + log en SQLite `audit_logs`.
- Requiere confirmación explícita.

### Ideas
- Borrado físico del bloque correspondiente en Google Docs + log en SQLite `audit_logs`.
- Requiere confirmación explícita.

### Agenda
- No se borra. Se cancela: estado `cancelled` en Google Calendar.
- Requiere confirmación explícita.

### Contabilidad
- **PROHIBIDO borrar movimientos contables.**
- Solo se puede corregir por edición con `correction_note`.
- El `accounting_agent` no tiene herramienta de borrado.

---

## 7) Política de corrección contable

- Crear: sí, con confirmación.
- Editar: sí, con confirmación + `correction_note` obligatoria.
- Borrar: **PROHIBIDO**.
- Trazabilidad de correcciones: registrada en SQLite `audit_logs`.

---

## 8) Confirmación y timeout

**Timeout congelado:** 30 minutos desde `proposal_sent_at`.

**Estados del flujo:**
detected → proposed → awaiting_confirmation → confirmed/rejected/expired → persisted/failed

**Si vence el timeout:**
- Estado transiciona a `expired`.
- No se persiste nada.
- El usuario debe enviar una nueva instrucción.

---

## 9) Deduplicación e idempotencia

**Estrategia de clave:**
1. Usar `provider event id` de Twilio cuando existe.
2. Fallback: hash normalizado de remitente + timestamp + body.

**Flujo antes de invocar el grafo:**
1. Generar clave de idempotencia.
2. Consultar tabla `processed_events`.
3. Si ya existe → ignorar (estado `duplicate`).
4. Si no existe → registrar clave y procesar.

Previene:
- Doble procesamiento del mismo webhook.
- Doble persistencia por doble confirmación.
- Doble disparo de recordatorios.

---

## 10) Multi-intención

Si el mensaje contiene múltiples acciones persistentes:
- El orquestador las descompone en `pending_actions` del `AgentState`.
- El sistema propone y confirma cada acción por separado.
- Ninguna acción persiste sin su confirmación individual.

---

## 11) Política del scheduler

- Revisión cada 15 minutos.
- APScheduler in-process.
- Válido solo con una única instancia activa del servicio.
- Si el deploy corre múltiples workers → el scheduler debe rediseñarse antes de publicar.
- Recordatorios vencidos durante caída del servicio → estado `missed`. Sin reenvío retroactivo.

---

## 12) Retención

| Dato | Retención |
|---|---|
| Google Sheets / Docs / Calendar | Sin purga automática en MVP |
| SQLite `processed_events` | 30 días |
| SQLite logs, conversation state, reminder_jobs | 90 días |

---

## 13) Capacidades del reporting_agent

Lee en modo read-only de:
- Google Sheets (tareas y contabilidad)
- Google Docs (ideas)
- Google Calendar (agenda)

Responde consultas como:
- "¿Cuánto gasté en comida este mes vs el mes pasado?"
- "¿Qué tareas tengo para hoy?"
- "Resumen semanal de ingresos y egresos"
- "¿Cuántas tareas completé esta semana?"
- "¿Qué tengo en la agenda esta semana?"
- "Ideas sobre X"

El `reporting_agent` **nunca persiste**. No tiene herramientas de escritura.
