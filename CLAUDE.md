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

1. **Hay prisa real.** La temporada está corriendo y la versión provisional tiene que
   estar lista para la **semana 4 o 5 de la NFL**. La semana 4 arranca el jueves
   2026-10-01 (viernes en Sídney). Empieza por el **Bloque 1** de preguntas abiertas.
2. Luego el **Bloque 2** (validación), porque sin él el modelo no puede mandar.
3. Los Bloques 3 (ejecución autorizada) y 4 (intercambios) van después.
4. Pregunta a Mario una cosa a la vez. Cuando una pregunta se cierre, súbela a
   *Decisiones cerradas* y sácala de la lista.
5. Cuando el diseño esté cerrado, usa `writing-plans` antes de tocar código.

### Qué no reabrir

Las 11 decisiones cerradas de `PROYECTO.md`, en particular:
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
