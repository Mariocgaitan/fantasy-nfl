# Sistema de recomendación semanal — diseño

> Fecha: 2026-09-26. Fuente de requisitos: `PROYECTO.md` (decisiones 1–22).
> Este documento es el **cómo**; el **qué** y el porqué viven en `PROYECTO.md`.

## 1. Objetivo y restricciones

Recomendar cada semana alineación, agencia libre e intercambios para BanKAI
(equipo 5, liga ESPN `898754986`, PPR, 8 equipos) en la temporada 2026.

- **Cero costo** (decisión 11).
- **Nada se ejecuta en ESPN sin autorización de Mario**, acción por acción
  (decisión 4). Los reemplazos condicionales autorizados de antemano cuentan
  como autorización (decisión 7).
- **El modelo no manda sin validar** (decisiones 8, 9, 19, 20). Mientras tanto
  manda la proyección de ESPN y el modelo aparece como segunda opinión
  (decisión 15).

## 2. Fases y fechas (hora de Sídney)

| Fase | Fecha límite | Contenido |
|---|---|---|
| 0. Provisional mínima | martes 2026-09-29 19:00 | Ingesta ESPN + nflverse, instantáneas, alineación con proyección de ESPN + reglas (a) y (b), agencia libre (pedir/soltar, ganando rol), página en GitHub Pages **sin botones**, correo por Gmail (SMTP). Marcada "sin validar". La regla (b) se adelanta a esta fase porque el reporte del domingo 2026-10-04 llega antes que la fase 1 y sale casi gratis de la alineación. |
| 1. Provisional completa | martes 2026-10-06 | Intercambios y modelo como segunda opinión. |
| 2. Ejecución autorizada | semanas 6–7 | Botones → issue de GitHub → escritura en ESPN; vigilante de inactivos. |
| 3. Modelo serio | en paralelo, meta semana 8 | Backtest walk-forward (ajuste 2024, corrida única en 2025 sellado). Si pasa, el modelo manda. |

Si una fase no llega a su fecha, sale lo que esté listo y lo demás entra en la
siguiente corrida: nunca se retrasa un reporte entero por una pieza.

## 3. Arquitectura

Paquete Python `fantasy` (Python 3.12, uv, pandas, pytest, Jinja2). Sin base de
datos ni servidor. Los módulos se comunican con DataFrames de columnas fijas,
cuyos esquemas se definen como constantes en `fantasy/esquemas.py` y se validan
al entrar a cada módulo.

```
src/fantasy/
  ingesta/      espn.py, nflverse.py        → tablas crudas normalizadas
  almacen/      instantaneas.py             → lee/escribe la rama `datos`
  proyeccion/   espn.py, modelo.py, riesgo.py
  decision/     alineacion.py, agencia_libre.py, intercambios.py
  reporte/      html.py (Jinja2), correo.py (Gmail SMTP)
  ejecucion/    acciones.py, espn_escritura.py, vigilante.py     (fase 2)
  backtest/     walkforward.py, fuga.py, metricas.py             (fase 3)
  horario.py    lógica de hora de Sídney y ventanas
  cli.py        punto de entrada único
tests/
.github/workflows/
```

### 3.1 Flujo de una corrida

1. `fantasy reporte --tipo martes|viernes|domingo`
2. `horario.py` decide si en Sídney es la hora de ese reporte y si ya existe;
   si no toca o ya existe, termina sin hacer nada.
3. `ingesta` baja de ESPN liga (equipos, plantillas, configuración,
   enfrentamientos, transacciones), jugadores (proyección semanal y del resto
   de la temporada, lesiones, dueño %, ADP, comentarios) y calendario NFL, y
   de nflverse estadísticas semanales y snaps.
   Las proyecciones semanales (semanas 1–18) salen de
   `leaguedefaults/3?view=kona_player_info` con `filterIds` en lotes de 50:
   el endpoint de la liga solo da la semana en curso. Puntuación PPR estándar,
   igual que la liga.
4. `almacen` guarda la instantánea en la rama `datos`:
   `instantaneas/2026/semNN/AAAA-MM-DDTHH-MM/*.json.gz|*.csv.gz` (hora de
   Sídney). Se guardan las **respuestas crudas comprimidas**, no tablas ya
   procesadas: así un cambio en los parsers se puede volver a correr sobre
   la historia completa. La misma rama sirve la página por GitHub Pages
   (`index.html`, `reportes/`).
5. **Semana objetivo**: la `scoringPeriodId` de ESPN, salvo que ya haya
   empezado el último partido de esa semana; en ese caso es la siguiente (el
   reporte del martes es de la semana que viene aunque ESPN no haya
   avanzado).
6. `proyeccion` produce por jugador y semana: proyección que manda (ESPN en
   provisional), proyección del modelo y probabilidad de jugar.
7. `decision` produce recomendaciones.
8. `reporte` genera el HTML (publicado en GitHub Pages) y el correo resumen.

La misma orden corre local y en Actions. Con `--instantanea <ruta>` corre sin
red a partir de una instantánea guardada: así se reproduce cualquier reporte.

### 3.2 Horarios

Reportes: martes 19:00, viernes 08:00, domingo 20:00, hora de Sídney
(decisión 14). El cron de GitHub va en UTC: para cada reporte se programan las
dos horas UTC posibles (horario estándar y de verano de Sídney) y `horario.py`
filtra. Tolerancia de retraso del cron: hasta 90 min. Idempotencia: un reporte
se identifica por (semana, tipo); si ya existe en `datos`, no se repite.

**Pendiente de verificar:** la zona horaria de `waiverProcessHour = 11`, con
los primeros reclamos procesados reales. El reporte del martes no depende de
esto (el martes no se procesan waivers).

### 3.3 Instantáneas como historial

Las instantáneas conservan lo que ESPN proyectaba en cada momento. Además de
la reproducibilidad, permiten medir en vivo, sin fuga, al modelo contra ESPN en
2026.

## 4. Lógica de decisión

En provisional, "proyección" = ESPN. Semana por semana, con peso igual para
todas, incluidas las de playoffs (15–17).

### 4.1 Alineación

- **Óptima exacta** para los 7 lugares (QB, RB×2, WR×2, TE, FLEX RB/WR/TE):
  llenar cada posición con sus mejores y el FLEX con el mejor sobrante. Con
  cupos por posición y un solo comodín esto es exacto (argumento de
  intercambio); una prueba lo compara contra la enumeración completa. Los
  jugadores bloqueados (partido empezado) quedan fijos.
- **Puntaje esperado** = proyección × P(jugar). P(jugar) por estado:
  ACTIVE 1.0, QUESTIONABLE 0.75, DOUBTFUL 0.25, OUT/IR 0. Valores iniciales
  **sin validar**; se calibran con 2024–2025 en la fase 3.
- **Regla (a)**: si un jugador QUESTIONABLE o DOUBTFUL supera al mejor suplente
  ACTIVE elegible por menos de **2.0 puntos** de proyección, entra el suplente.
- **Regla (b), reemplazos condicionales**: para cada titular, el mejor suplente
  elegible **cuyo partido empiece a la misma hora o después** que el del
  titular. Si no existe, el reporte lo dice ("sin respaldo útil").

### 4.2 Agencia libre

- Un candidato solo suma **esta semana** si entra a la alineación óptima.
- **Valor** = suma, en las semanas restantes, de la mejora de la alineación
  óptima de Mario al tenerlo (esto captura los descansos), más un **seguro**
  cuando cubre una posición sin respaldo en las próximas 3 semanas: solo QB y
  TE, porque RB y WR ya se cubren entre sí por el FLEX (hoy: QB). El seguro
  vale 0.15 × sus puntos proyectados en esas 3 semanas (sin validar).
- **Ganando rol**: comparar snaps %, share de targets y acarreos de las últimas
  2 semanas contra las anteriores (nflverse), y contra el cambio de dueño % en
  ESPN. Se marcan los que suben de rol sin que suba su dueño %.
- **A quién soltar**: el de menor valor en la plantilla; nunca a un jugador
  bloqueado cuyo partido no ha terminado.

### 4.3 Intercambios

- **Búsqueda**: 1–3 jugadores de Mario por 1–2 del rival, contra los 7 rivales.
  Si una plantilla pasa de 14, se suelta a su jugador de menor valor.
- **Ganancia de Mario**: suma semana por semana de la mejora de su alineación
  óptima en lo que queda de temporada. Se ordena por esta ganancia (agresivo,
  decisión 16).
- **Aceptación del rival** (decisión 17), las dos condiciones:
  - Δ alineación del rival según ESPN ≥ −15 puntos en el resto de la temporada;
  - Δ valor de nombre ≥ −3, con valor de nombre = 100·e^(−ADP/45).
  Se recalibra con los intercambios y movimientos observados en la temporada.
- **Riesgo de veto**: se muestra (Δ ESPN del rival muy negativo = riesgo alto);
  no filtra.
- **Reglas de momento**: solo en el reporte del martes; nunca al rival de la
  semana si el intercambio se procesaría antes de sus partidos; una propuesta a
  la vez cuando comparten jugadores.

## 5. Ejecución autorizada (fase 2)

- Cada acción del reporte se guarda en `datos` con número, contenido exacto y
  validez ("hasta el inicio del partido de X").
- Botón → `issues/new` prellenado con título `AUTORIZO #N`.
- Workflow en `issues.opened`:
  1. el autor debe ser `github.repository_owner`; si no, se ignora;
  2. revalidar contra ESPN en vivo (vigencia, bloqueo, plantilla sin cambios);
     si no es válida, no ejecuta y explica por qué;
  3. ejecutar, releer ESPN para confirmar, comentar el resultado, cerrar el
     issue y avisar por correo;
  4. idempotente: una acción ejecutada no se repite.
- **Vigilante**: cada 10 min desde 100 min hasta 5 min antes de cada partido
  con reglas activas; si X está inactivo y Y no está bloqueado, hace el cambio
  y avisa.
- **Riesgo**: la escritura en ESPN no está documentada. El primer paso de la
  fase 2 es una prueba corta con las cookies de Mario (intercambiar dos
  jugadores de la banca). Si falla, el sistema se queda en recomendar.
- **Seguridad**: cookies como secretos cifrados (decisión 21), nunca impresos;
  los workflows de forks no reciben secretos; permisos mínimos del token.

## 6. Modelo y backtest (fase 3)

- **Objetivo**: puntos PPR por jugador y semana.
- **Variables**: uso (snaps %, targets, acarreos, air yards) con shrinkage,
  rival, y **la proyección semanal de ESPN** (existe antes del partido; el
  modelo aprende a corregirla).
- **Modelos** por posición: ridge primero; gradient boosting solo si mejora en
  2024.
- **Walk-forward**: para la semana w se entrena con todo lo disponible antes del
  primer partido de w. Semanas 3–17 de cada temporada.
- **Fuga**: cada fila lleva `disponible_desde`; `fuga.py` detiene la corrida si
  alguna variable usada tiene `disponible_desde` ≥ inicio del partido que se
  predice.
- **Jugadores relevantes para el MAE**: top de ESPN de esa semana antes del
  partido (12 QB, 30 RB, 30 WR, 12 TE).
- **Criterio** (decisión 19): Δ MAE (modelo − ESPN) < 0 con intervalo
  bootstrap del 95% por semanas que excluya el cero, y sin perder en ninguna
  posición.
- **2025 sellado**: el código rechaza la temporada 2025 sin la bandera
  `--sellado-final`; esa corrida escribe un registro versionado en el repo.
- **Pendientes de verificación** (decisión 18): que la proyección histórica de
  ESPN sea la previa al partido, y pedir la lista completa de jugadores para
  evitar sesgo de supervivencia.
- Si pasa, el modelo manda y ESPN queda como segunda opinión. Seguimiento
  durante la temporada: A (puntos dejados en la banca) y D (victorias, puntos a
  favor, lugar).

## 7. Manejo de errores

Principio: **nunca decidir en silencio con datos incompletos**.

| Falla | Respuesta |
|---|---|
| ESPN no responde o cambió su formato | 3 reintentos con espera creciente; validación de esquema y conteos (8 equipos, plantillas ≤ 14). Si falla: sin reporte y correo con la causa. |
| nflverse sin datos de la semana | Se usa lo último disponible y el reporte lo marca con fecha. |
| Cron no corrió | La siguiente corrida lo detecta y lo avisa; falla del workflow → correo de GitHub + correo de Gmail. |
| Cookies vencidas | Correo con los pasos para renovarlas. |
| Falla una escritura | Sin reintento ciego: releer ESPN, informar el estado real, acción pendiente. |

Cada reporte muestra la frescura de cada fuente.

## 8. Pruebas

pytest y ruff en cada push (GitHub Actions). Fixtures a partir de instantáneas
reales:

- **Alineación**: la plantilla de BanKAI de la semana 3 (instantánea del
  2026-09-25) → el óptimo coincide con la alineación que tenía Mario.
- **Reemplazos**: caso Shough (partido a las 06:25 del lunes; ningún QB libre
  juega después) → "sin respaldo útil".
- **Intercambios**: reproduce Collins + Hall + Nabers → Chase con ganancia
  positiva y aceptación válida para Smashers.
- **Horario**: reportes correctos antes y después del 2026-10-04 (cambio de
  horario en Australia) y del 2026-11-01 (en EE. UU.); sin duplicados.
- **Fuga**: una fila con `disponible_desde` futuro detiene el backtest.
- **Corrida completa sin red** desde una instantánea: produce HTML y correo.
- **Ejecución**: contra un ESPN simulado; escritura real solo en la prueba corta.

Reproducibilidad: `uv.lock`, reportes regenerables desde su instantánea,
README con arquitectura y, al final, el resultado del backtest.
