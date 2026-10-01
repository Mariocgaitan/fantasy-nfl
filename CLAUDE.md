# Fantasy NFL

Ficha general de este proyecto: [[fantasy-nfl]] — `../00_INDICE/fichas/fantasy-nfl.md`
Mapa de todos los proyectos: [[00_INDICE]] — `../00_INDICE/00_INDICE.md`

Léelas si necesitas contexto de cómo este proyecto se relaciona con los otros.
Son de nivel general; ante contradicción, este repo gana.

## Contrato con el índice

**Al terminar una sesión**, si ocurrió alguna de estas cuatro cosas, añade una
entrada fechada **al final** de `BUZON_INDICE.md` (créalo si no existe):

- `ESTADO:` cambió el estado del proyecto
- `HUECO RESUELTO:` determinaste algo que la ficha lista en su sección Huecos
- `LINAJE:` apareció o se aclaró una relación con otro repo
- `HITO:` fase completada, despliegue, entrega o cambio de stack

**Si no pasó nada de eso, no escribas nada.** El umbral alto es intencional.

Formato:

```
## 2026-08-03
- ESTADO: pausado -> activo. Retomado el Sprint 4.
- HUECO RESUELTO: "por qué se detuvo" -> se priorizó otro proyecto.
```

Nunca edites archivos de `00_INDICE/`: la consolidación la hace la
sesión-índice cuando Mario la pide.
<!-- ══ Arriba: sesión-índice. Abajo: territorio del proyecto. ══ -->

## Para la sesión del proyecto

**Lee `PROYECTO.md` completo antes de proponer nada.** Ahí están el objetivo, la
restricción que define el proyecto, las decisiones cerradas y las preguntas abiertas.

### Por dónde empezar

**Lee `docs/ESTADO.md` justo después de `PROYECTO.md`.** Ahí está qué fases están en
producción, el resultado de la validación sellada (no pasó), los pendientes en orden y
cómo operar el reporte. Las preguntas abiertas originales ya están todas cerradas
(decisiones 12–24).

Para trabajo nuevo: brainstorming → spec → `writing-plans` → ejecución en una rama con
PR (Mario fusiona o pide fusionar). Pregunta a Mario una cosa a la vez.

### Qué no reabrir

Las decisiones cerradas de `PROYECTO.md`, en particular:
- **Cero costo.**
- **Nada se ejecuta en ESPN sin autorización de Mario** (los reemplazos condicionales son autorización previa).
- **El modelo no manda sin pasar la validación contra ESPN.**
- **Sin parte educativa.**

### Contexto útil

- Mario vive en **Sídney**. Todos los horarios de la NFL se piensan en hora de Sídney.
- La liga es pública: `leagueId = 898754986`, Mario es el **equipo 5 (BanKAI)**.
- `prototipo_draft/` es **desechable**. Tómalo como referencia de lo que funcionó (xFP por
  uso, shrinkage, VOR, simulador de rivales, endpoints), no como base del código.
- Es **proyecto de portafolio**: pruebas, reproducibilidad y documentación cuentan.
- Mario escribe en español y no conoce la NFL. Dile qué hacer y por qué en una línea,
  sin tutoriales.
