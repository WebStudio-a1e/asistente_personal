# T-038 — Deploy Railway: estado y prerequisitos

**Fecha:** 2026-03-12
**Fase:** FASE_7
**Estado:** READY para deploy — BLOCKED en: acceso Railway + credenciales Google

---

## Estrategia elegida

Railway detecta y usa el `Dockerfile` existente.
`railway.json` en raíz configura el deploy sin tocar código de aplicación.

---

## Archivos tocados en T-038

| Archivo | Motivo |
|---|---|
| `railway.json` | Config de deploy: startCommand, healthcheck, replicas |
| `docs/AUDIT_REPORTS/T-038-railway-deploy.md` | Este archivo |

---

## Comando de arranque en Railway

```
uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Railway inyecta `PORT` en runtime. El `${PORT:-8000}` lo usa si está definido,
cae a 8000 como fallback. El Dockerfile mantiene `EXPOSE 8000` para
auto-detección local.

---

## Instancia única del scheduler

El scheduler (`APScheduler BackgroundScheduler`) arranca dentro del proceso
uvicorn via FastAPI lifespan. Es singleton dentro del proceso, pero no entre
procesos/réplicas.

**Solución:** `railway.json` fija `numReplicas: 1`.
Esto garantiza exactamente un proceso uvicorn corriendo en Railway,
y por lo tanto un único scheduler activo.

> Si en el futuro se necesita escalar el web layer, el scheduler debe
> extraerse a un worker separado. Para el MVP single-user esto es correcto.

---

## Variables de entorno a cargar en Railway

### Obligatorias (la app no arranca sin ellas)

```
LLM_ORCHESTRATOR=claude-sonnet-4-6
LLM_TASKS=gpt-4o
LLM_IDEAS=claude-sonnet-4-6
LLM_AGENDA=gemini-2.0-flash
LLM_ACCOUNTING=gpt-4o
LLM_REPORTING=claude-sonnet-4-6
```

### API Keys (obligatorias según LLMs elegidos)

```
ANTHROPIC_API_KEY=<clave real>
OPENAI_API_KEY=<clave real>
GOOGLE_GEMINI_API_KEY=<clave real>
```

### Twilio

```
TWILIO_ACCOUNT_SID=<sid real>
TWILIO_AUTH_TOKEN=<token real>
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886
TWILIO_WHATSAPP_TO=whatsapp:+598XXXXXXXXX
```

### Google APIs

```
GOOGLE_CREDENTIALS_PATH=credentials/google_credentials.json
GOOGLE_SHEETS_TASKS_ID=<id real>
GOOGLE_SHEETS_ACCOUNTING_ID=<id real>
GOOGLE_DOCS_IDEAS_ID=<id real>
GOOGLE_CALENDAR_ID=<id real>
```

### App

```
APP_ENV=production
TIMEZONE=America/Montevideo
LOG_LEVEL=INFO
SQLITE_DB_PATH=data/asistente_personal.db
```

---

## Credenciales Google — blocker para conectores en producción

El archivo `credentials/google_credentials.json` está en `.gitignore` y no
llega al build context de Railway. La app **arranca sin él** (`GET /health`
responde 200), pero los conectores Google fallan al llamarse.

**Para T-038 (deploy + health):** no bloquea.
**Para T-039 (smoke en producción):** bloquea.

**Solución recomendada para Railway (a implementar antes de T-039):**
Usar un Railway Volume montado en `/app/credentials/` con el JSON de
service account, o refactorizar `google_auth.py` para leer contenido JSON
desde variable de entorno `GOOGLE_CREDENTIALS_JSON` (base64). La segunda
opción es más limpia para cloud.

---

## Webhook Twilio

### Ruta exacta

```
POST /webhook
```

### URL final esperada

Una vez que Railway entregue el dominio público:

```
https://<nombre-servicio>.up.railway.app/webhook
```

Configurar en Twilio Sandbox → "When a message comes in":

```
https://<nombre-servicio>.up.railway.app/webhook
Method: HTTP POST
```

---

## Validaciones locales ejecutadas

| Verificación | Resultado |
|---|---|
| `docker compose build` | ✓ imagen construida sin errores |
| `GET /health` local | ✓ `{"status": "ok"}` |
| Puerto real de arranque | ✓ 8000 (Dockerfile CMD + railway.json startCommand) |
| Scheduler arranca | ✓ confirmado en logs de lifespan |
| `railway.json` schema | ✓ usa schema oficial railway.app |

---

## Prerequisitos exactos para completar T-038

1. **Acceso Railway:** cuenta activa + CLI o dashboard
2. **Crear proyecto Railway** y linkear este repo (o hacer `railway up`)
3. **Cargar variables de entorno** listadas arriba en Railway dashboard
4. **Verificar `GET /health`** responde 200 desde el dominio Railway público
5. **Anotar URL pública** para configurar Twilio en T-039

---

## Estado final T-038

```
READY para deploy — BLOCKED en prerequisitos externos:
  - acceso a Railway (CLI / dashboard)
  - carga de variables de entorno reales en la plataforma
  - decisión sobre credenciales Google en cloud (Railway Volume vs env var)
```
