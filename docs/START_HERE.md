# START_HERE.md — asistente_personal v2.1

## Qué es esto

Paquete documental oficial para arrancar `asistente_personal` bajo metodología W-CVC.
Arquitectura: sistema multiagente LangGraph.
Modo de arranque: **container-first**.

---

## Orden de lectura

1. `docs/DECISION_FREEZE.md` — todas las decisiones congeladas
2. `docs/PRD_PROYECTO_ACTIVO.md` — requisitos y arquitectura completa
3. `docs/AcceptanceCriteria.md` — qué debe pasar para que el MVP esté listo
4. `docs/DataHandling.md` — cómo se persiste, edita, borra y retiene cada dato
5. `state_machine.yaml` — grafo LangGraph + 3 máquinas de estado
6. `CLAUDE.md` — instrucciones operativas para Claude Code
7. `WORKPLAN.yaml` — tareas atómicas con orden container-first

---

## Checklist antes de empezar a codear

### Producto
- [ ] El PRD refleja exactamente el producto deseado
- [ ] La arquitectura multiagente LangGraph es la correcta
- [ ] Los LLMs por agente (DECISION_FREEZE.md) están aceptados
- [ ] El timeout de confirmación de 30 minutos es aceptable
- [ ] Las políticas de borrado por dominio están aceptadas
- [ ] La política `missed` del scheduler es aceptable
- [ ] Se va a usar una sola instancia activa del servicio

### Entorno
- [ ] Docker Desktop instalado y corriendo
- [ ] `.env` creado: `Copy-Item .env.example .env` y completar con credenciales reales
- [ ] VS Code instalado
- [ ] Ruta del repo lista: `C:\dev\asistente_personal`

### Credenciales
- [ ] `ANTHROPIC_API_KEY` disponible
- [ ] `OPENAI_API_KEY` disponible
- [ ] `GOOGLE_GEMINI_API_KEY` disponible
- [ ] `TWILIO_ACCOUNT_SID` y `TWILIO_AUTH_TOKEN` disponibles
- [ ] Google Sheets (×2) creados, IDs listos
- [ ] Google Docs (documento maestro ideas) creado, ID listo
- [ ] Google Calendar personal listo, ID listo
- [ ] `credentials/google_credentials.json` de service account disponible

---

## Regla de arranque — container-first

```
1. documentación canónica (ya está en este paquete)
2. estructura del repo   → T-001
3. requirements.txt      → T-003
4. Dockerfile            → T-004
5. docker-compose.yml    → T-005
6. src/config.py         → T-006
7. src/main.py + /health → T-007
8. smoke tests           → T-008
         ↓
   FASE_1A CERRADA
         ↓
   recién entonces: grafo, agentes, conectores
```

No se empieza lógica funcional antes de que `docker compose up` funcione.

---

## Primera sesión — instrucción exacta para Claude Code

```
Leé docs/START_HERE.md, CLAUDE.md y WORKPLAN.yaml.
Decime en qué fase estamos y cuál es la próxima tarea READY.

Ejecutá SOLO T-001.
No hagas ninguna otra tarea.
No escribas implementación funcional.
Cuando termines, mostrame el diff y el criterio de done cumplido.
```

---

## Rutas canónicas

| Artefacto           | Ruta                            |
|---------------------|---------------------------------|
| PRD                 | `docs/PRD_PROYECTO_ACTIVO.md`   |
| Acceptance Criteria | `docs/AcceptanceCriteria.md`    |
| Threat Model        | `docs/ThreatModel.md`           |
| Data Handling       | `docs/DataHandling.md`          |
| Decision Freeze     | `docs/DECISION_FREEZE.md`       |
| Start Here          | `docs/START_HERE.md`            |
| State Machine       | `state_machine.yaml`            |
| CLAUDE.md           | `CLAUDE.md`                     |
| WORKPLAN            | `WORKPLAN.yaml`                 |
| Variables           | `.env.example`                  |
| Git ignore          | `.gitignore`                    |

---

## Verificación antes de lanzar Claude Code

- [ ] El repo está en `C:\dev\asistente_personal`
- [ ] Solo están los archivos de este paquete (sin mezcla de versiones anteriores)
- [ ] `.env` creado desde `.env.example` con las credenciales reales
- [ ] Docker Desktop está corriendo
