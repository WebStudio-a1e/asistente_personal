# ThreatModel.md — asistente_personal v2.0

**Versión:** v2.0 | **Fecha:** 2026-03-10 | **Estado:** ACTIVO

---

## 1) Alcance

Sistema multiagente LangGraph con 5 agentes especializados + orquestador + reporting. Canal WhatsApp (Twilio). Usuario único. Accede a datos financieros personales, agenda, ideas y tareas. Múltiples LLM providers (Anthropic, OpenAI, Google, DeepSeek).

---

## 2) Amenazas

### THREAT-001 — Orquestador rutea al agente equivocado

**Descripción:** El orquestador clasifica incorrectamente y deriva al agente equivocado (ej: un gasto va al tasks_agent).
**Impacto:** Payload incorrecto propuesto al usuario. Si el usuario confirma sin leer, dato erróneo persistido.
**Control principal:** Confirmación previa obligatoria — el usuario ve el payload propuesto antes de que se ejecute. Si el payload es incorrecto, lo rechaza.
**Control secundario:** Si la intención es ambigua, el orquestador pide aclaración antes de derivar.
**Estado:** MITIGADO por diseño.

### THREAT-002 — Agente escribe sin pasar por confirmation_node

**Descripción:** Un agente especializado persiste directamente sin confirmación.
**Impacto:** Datos incorrectos en Sheets, Docs o Calendar sin conocimiento del usuario.
**Control:** El grafo LangGraph fuerza el paso por `confirmation_node` para todos los agentes persistentes. El `reporting_agent` no tiene herramientas de escritura — arquitecturalmente imposible que escriba.
**Estado:** MITIGADO por arquitectura del grafo.

### THREAT-003 — Exposición de múltiples API keys

**Descripción:** Las keys de Anthropic, OpenAI, Google Gemini, DeepSeek, Twilio y Google service account quedan expuestas en el repositorio.
**Impacto:** Acceso no autorizado a todas las APIs y a los datos personales.
**Control:** Todas las credenciales en variables de entorno. `credentials/` y `.env` en `.gitignore`. Verificar con `git grep` antes de cada deploy.
**Estado:** PARCIALMENTE MITIGADO — depende de gestión correcta en deploy.

### THREAT-004 — reporting_agent alucina datos que no existen

**Descripción:** El reporting_agent genera un reporte con datos inventados en lugar de leer las fuentes reales.
**Impacto:** El usuario toma decisiones basadas en datos falsos.
**Control:** El reporting_agent accede a las fuentes reales vía herramientas de lectura. Tests de reporting verifican que las respuestas provienen de datos reales. RNF-012: el sistema prioriza exactitud sobre automatización.
**Estado:** PARCIALMENTE MITIGADO — requiere tests de hallucination en Fase 5.

### THREAT-005 — Doble procesamiento de webhooks Twilio

**Descripción:** Twilio reenvía el mismo evento y se crean dos tareas o dos movimientos contables.
**Impacto:** Datos duplicados, registros contables incorrectos.
**Control:** Dedupe check con clave de idempotencia en SQLite antes de invocar el grafo. Estrategia: `provider event id` → fallback hash.
**Estado:** MITIGADO por diseño.

### THREAT-006 — Pérdida de estado conversacional

**Descripción:** El checkpointer SQLite falla y el grafo pierde el contexto de una confirmación pendiente.
**Impacto:** Propuesta en estado `awaiting_confirmation` queda huérfana.
**Control:** Timeout de 30 minutos — si el estado no avanza, expira y no se persiste. El grafo inicia hilo limpio ante fallo del checkpointer.
**Estado:** MITIGADO por timeout.

### THREAT-007 — Scheduler multi-instancia

**Descripción:** Deploy corre múltiples instancias y APScheduler dispara recordatorios múltiples veces.
**Impacto:** Recordatorios duplicados enviados al usuario.
**Control:** Documentado como límite explícito del MVP. Instancia única obligatoria. Si el deploy requiere múltiples workers, el scheduler debe rediseñarse.
**Estado:** CONDICIONADO — válido solo con instancia única.

### THREAT-008 — Movimiento contable borrado accidentalmente

**Descripción:** Bug en accounting_agent ejecuta un borrado.
**Impacto:** Pérdida de historial financiero.
**Control:** El accounting_agent no tiene herramienta de borrado. La ausencia de la herramienta es la protección. Tests verifican que el intento de borrado falla.
**Estado:** MITIGADO por arquitectura (ausencia de herramienta).

### THREAT-009 — Prompt injection vía mensaje WhatsApp

**Descripción:** Mensaje contiene instrucciones que intentan modificar el comportamiento del orquestador o los agentes.
**Impacto:** El sistema ejecuta acciones no autorizadas.
**Control:** Los mensajes del usuario se tratan como datos, no como instrucciones del sistema. Los system prompts están definidos en código, no son modificables por el usuario.
**Estado:** PARCIALMENTE MITIGADO — requiere revisión de system prompts en Fase 2.

### THREAT-010 — Cambio de LLM introduce comportamiento diferente

**Descripción:** Se cambia el LLM de un agente y el nuevo modelo clasifica o extrae payloads de forma diferente.
**Impacto:** Clasificaciones incorrectas, payloads mal formados, experiencia degradada.
**Control:** Cambiar el LLM no requiere cambiar código. Los tests de cada agente se ejecutan contra el LLM configurado antes de deploy.
**Estado:** MITIGADO por separación de configuración y código + test suite.

---

## 3) Activos a proteger

| Activo | Clasificación | Ubicación |
|---|---|---|
| Datos financieros personales | Sensible personal | Google Sheets (contabilidad) |
| Agenda personal | Sensible personal | Google Calendar |
| Ideas y notas | Personal | Google Docs |
| Tareas personales | Personal | Google Sheets (tareas) |
| API keys (Anthropic, OpenAI, Gemini, DeepSeek, Twilio) | Crítico | `.env` (gitignored) |
| Credenciales Google service account | Crítico | `credentials/` (gitignored) |

---

## 4) Controles mínimos requeridos

| Control | Aplica a | Implementado en |
|---|---|---|
| Confirmación previa obligatoria | Toda persistencia | confirmation_node + grafo |
| reporting_agent solo lectura | Reporting | Sin herramientas de escritura |
| Secrets fuera del repo | Todas las APIs | .gitignore + .env.example |
| Timezone forzada | Agenda y scheduler | TIMEZONE=America/Montevideo |
| correction_note en ediciones contables | Contabilidad | accounting_agent + sheets_accounting.py |
| Idempotencia de webhooks | WhatsApp | SQLite processed_events + dedupe check |
| No borrado contable | Contabilidad | Sin herramienta de borrado en accounting_agent |
| Timeout de confirmación | Toda confirmación | 30 minutos en confirmation_node |
| Instancia única scheduler | Scheduler | Documentado, verificado en deploy |

---

## 5) Fuera del alcance de este modelo

- Ataques de red a nivel de infraestructura (Railway/Render).
- Seguridad de la cuenta de WhatsApp del usuario.
- Vulnerabilidades en APIs de proveedores de LLM.
- Acceso físico al dispositivo.

---

## 6) Revisión obligatoria antes de

- Agregar multiusuario.
- Cambiar de LLM provider para reporting_agent.
- Habilitar múltiples instancias del servicio.
- Publicar como producto reusable.
