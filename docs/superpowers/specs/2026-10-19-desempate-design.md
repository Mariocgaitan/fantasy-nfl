# Desempate por total esperado del equipo — diseño

> 2026-10-19. Rama `desempate` (desde `main`, independiente de `prob-ganar`).
> Este documento es también el **registro de la regla congelada**: la sección 3 no se
> cambia después de leer 2025.

## 1. Por qué

Cuando dos jugadores que pueden ocupar el mismo lugar de la alineación tienen
proyecciones de ESPN casi iguales, el reporte elige al de mayor proyección. Con menos de
1 punto de diferencia eso es una moneda al aire: en 2023–2024 la proyección más alta
acertó al que hizo más puntos el **51.0 %** de las veces. Ejemplo real: semana 5 de 2026,
Parker Washington (14.1) titular sobre Christian Watson (13.8); Watson hizo 32.3 en la banca.

Mario quiere un **criterio para decidir entre dos jugadores además de su proyección**.

### Exploración (2023–2024, desarrollo; 2025 sin tocar)

La idea original de Mario fue una caminata aleatoria con sesgo alrededor de la proyección
de ESPN: estimar, por jugador, la probabilidad de quedar por arriba o por abajo. Se exploró
sobre 2 520 filas de jugadores relevantes (los que podrían ser titulares en una liga de 8,
semanas 3–17):

- Base: superan a ESPN el 50 % (QB), 46 % (WR, TE) y 42 % (RB) de las veces.
- El sesgo **no persiste** por jugador: haber superado a ESPN antes no predice superarlo
  después (47–49 % en todos los tramos). Tampoco la tendencia de snaps o balones.
- Un clasificador con todas las variables del modelo v2 no le gana a la base (AUC 0.55).
- La única señal: el **total esperado del equipo según las apuestas** (`pts_equipo`):
  40 % arriba en el quintil más bajo, 53 % en el más alto.

Prueba de desempate: todos los pares de jugadores de la misma posición y semana con
proyecciones a ≤ 1.0 punto (7 211 pares). Nueve criterios; solo uno con IC95 por encima
del 50 %:

| Criterio | Acierta | IC95 |
|---|---|---|
| **Mayor `pts_equipo`** | **53.9 %** | [52.2, 55.6] |
| Mayor proyección ESPN | 51.0 % | [49.7, 52.3] |
| Los otros siete (rival, rol, racha, regularidad, promedio) | 49–51 % | incluyen el 50 % |

Seguimiento 2026, semanas NFL 1–6 (1 267 pares): **52.0 %**, IC95 [49.2, 54.9].

**Lo que importa son los pares en conflicto** (ESPN prefiere a uno y el total de equipo al
otro): en los demás el desempate elige lo mismo que ESPN y no cambia nada. Ahí se ve si vale
la pena contradecir a ESPN, y por eso la regla congelada (sección 3) mide solo esos pares.
Gana el de menor proyección y mayor total de equipo:

| Diferencia de proyección | 2023–2024 |
|---|---|
| 0–0.5 | 53.4 % |
| 0.5–1.0 | 52.4 % |
| 1.0–1.5 | 48.4 % |
| 1.5–2.0 | 47.9 % |
| 2.0–3.0 | 46.3 % |
| **≤ 1.0 (la regla)** | **52.9 %**, IC95 [50.8, 55.2], 3 498 pares |
| ≤ 2.0 | 50.8 %, IC95 [48.6, 53.1] |

Por eso el umbral es 1.0: de 1 a 2 puntos ESPN ya sabe más (Mario preguntó por 2; se
descartó con esta tabla). **En 2026, semanas 1–6, en conflicto: 48.1 %**, IC95 [45.8, 50.0],
615 pares: hasta ahora la regla pierde contra ESPN. Se probaron 9 criterios y se eligió el
mejor, así que la confirmación en datos no vistos es obligatoria.

Los scripts de exploración no se versionan (quedaron en el scratchpad de la sesión); la
sección 3 es la definición que manda.

## 2. Objetivos, no objetivos, anti-objetivos

**Objetivos**
1. El reporte marca como **empate** las decisiones de alineación con ≤ 1.0 punto de
   diferencia y muestra el total esperado del equipo de cada jugador.
2. Una **prueba única sobre 2025** decide si el desempate manda.
3. Si pasa, el reporte desempata solo y lo dice en una línea.
4. Un comando de **seguimiento en 2026** que repite la misma medición.

**No objetivos**
- No cambia la proyección de ningún jugador. Tras un intercambio por desempate, el total
  esperado de la alineación es la suma honesta de los que quedan (vía `_armar`), así que
  puede bajar hasta 1.0 punto por intercambio.
- No toca agencia libre, intercambios ni el modelo v2 (`src/fantasy/modelo/` queda
  intacto: lo protege la huella de la validación en vivo; ver `docs/ESTADO.md`).
- No sustituye a la probabilidad de ganar (`prob-ganar`), que sigue su propio camino.
  Esta rama se construye sobre `main` y no integra nada de `prob-ganar`. Cuando se junten,
  si las dos pasan su prueba de 2025, **manda la probabilidad de ganar** en las decisiones
  parejas (mide el partido completo contra el rival real). El desempate queda como dato
  mostrado y como respaldo cuando la probabilidad de ganar no haya pasado. Esa integración
  es trabajo de la rama que se fusione después.

**Anti-objetivos (sería un fracaso aunque funcione)**
- Cambiar la regla de la sección 3 después de haber visto 2025, o correr 2025 dos veces.
- Que el desempate meta a un jugador en duda o lesionado en lugar de uno sano.
- Que el reporte desempate antes de que la prueba de 2025 pase.

## 3. La regla congelada (registro)

**Datos.** Filas de `variables.desde_crudos_v2(crudos, temporada)` (las mismas que usó la
exploración; `pts_equipo` sin línea queda en el valor neutro 22.0, como en el modelo v2),
con `real` no nulo y `proy_espn > 0`, semanas **3–17**. Por cada semana se toman los
relevantes con `evaluar.relevantes` (top 12 QB, 30 RB, 30 WR, 12 TE por `proy_espn`),
**aplicado temporada por temporada**.

**Pares.** Todas las combinaciones de dos jugadores de la misma semana y posición con
`0 < |proy_espn_a − proy_espn_b| ≤ 1.0`, `real_a ≠ real_b`, `pts_equipo_a ≠ pts_equipo_b`
y **en conflicto**: el de mayor `proy_espn` tiene menor `pts_equipo`.

**Acierto.** El par es acierto si el jugador con mayor `pts_equipo` (el de menor
proyección) hizo más puntos reales.

**Intervalo.** Bootstrap percentil del 95 % remuestreando **semanas** con reemplazo (cada
semana aporta sus aciertos y su número de pares), **2 000** remuestreos, semilla **0**.

**Pasa** si el acierto global > 0.5 **y** el límite inferior del IC95 > 0.5. No hay
condición por posición (decisión de diseño: la ventaja es chica y por posición no hay
muestra suficiente; se reporta por posición solo como dato).

**Corrida única.** Se corre una sola vez sobre 2025 y el resultado decide (decisión de
Mario, 2026-10-19: "manda en cuanto pase 2025"). 2025 se usó antes para el modelo de
puntos (decisión 20) y está reservada una vez para la varianza (decisión 25, rama
`prob-ganar`); ninguna de esas corridas midió este desempate, así que la prueba sigue limpia.

## 4. Qué se construye

### 4.1 Medición (`src/fantasy/desempate/`, módulo nuevo)

Una función pura que, dada la tabla de filas de una temporada, devuelve: acierto global,
IC95, número de pares, número de semanas, acierto y pares por posición, y acierto por
semana. Implementa exactamente la sección 3. Las constantes (`UMBRAL = 1.0`,
`SEMANAS = range(3, 18)`, `REMUESTREOS = 2000`, `SEMILLA = 0`) viven en ese módulo.

### 4.2 Prueba única 2025

Comando `fantasy desempate-validar --sellado-final`, con el patrón de
`modelo/validacion.validar_sellado`:

- Se niega si ya existe `validacion/2025_desempate.json`, si el repo tiene cambios sin
  commit o si `src/fantasy/desempate/` cambió desde el registro.
- **Registro previo:** `fantasy desempate-registrar` guarda en
  `validacion/registro_desempate.json` el commit y la huella (sha256) de los archivos de
  `src/fantasy/desempate/`. La prueba exige que coincidan.
- Todas las verificaciones van antes de bajar 2025. 2025 se baja como en la corrida
  sellada del modelo (`historico.bajar_espn_historico(2025, permitir_sellada=True)` +
  nflverse 2025 con la ingesta existente).
- Guarda `validacion/2025_desempate.json`: resultado de 4.1, `paso`, commit, huella, fecha.
- **Solo Mario autoriza correrla.** El plan llega hasta dejarla lista; la sesión le pide
  el visto bueno antes de ejecutarla.

### 4.3 Reporte

Para cada titular movible (no bloqueado) se busca la **mejor alternativa de la banca** que
pueda ocupar su lugar (misma posición; RB/WR/TE para el FLEX), no bloqueada, sana
(`lesion == "ACTIVE"`) y con `esperado > 0`. Si `|esperado_titular − esperado_alternativa|
≤ 1.0` y el titular también está sano, la decisión es un **empate**.

- **Casi empates** (diferencia entre 1.0 y 2.0): se muestran solo como dato, sin
  desempatar nunca.
- **Siempre** (pase o no la prueba): el reporte muestra el empate en la sección de la
  alineación con los dos nombres, sus proyecciones y el total esperado de su equipo
  (formato ilustrativo: "Empate: Washington 14.1 (su equipo espera X) · Watson 13.8 (su
  equipo espera Y)").
- **Si `validacion/2025_desempate.json` tiene `paso: true`:** si la alternativa tiene mayor
  `pts_equipo`, se intercambian. Una sola pasada sobre los lugares en el orden de la
  alineación; cada jugador participa en a lo más un intercambio. El intercambio aparece en
  "Qué hacer" como parte del cambio de alineación, con la razón en una línea.
- **Si no pasó o no se ha corrido:** el reporte no cambia la alineación; el empate se
  muestra como dato para que Mario decida.
- Orden respecto a las reglas existentes: `optima` → desempate → `aplicar_regla_duda` →
  `reemplazos`. Como el desempate solo mueve jugadores sanos, la regla de duda sigue
  igual.
- Si a alguno de los dos le falta la línea (no hay `juegos` o su partido no aparece), el
  empate se muestra con "sin línea" y no se desempata.
- Aplica a los tres reportes (martes, viernes, domingo); las líneas se leen de
  `crudos["juegos"]` con `contexto.lineas`, como ya hace el modelo v2 en vivo.

### 4.4 Seguimiento 2026

Comando `fantasy desempate-vivo` que aplica 4.1 a la temporada 2026 y escribe
`validacion/2026_desempate_vivo.json` (se sobrescribe en cada corrida). Es **informativo**:
no apaga ni enciende el desempate.

- **Datos:** los mismos que baja el reporte (`bajar_espn` + `bajar_nflverse` +
  `nflverse.bajar_juegos`), que es como se obtuvo el 52.0 % de la sección 1. La población
  es menor que la histórica (plantillas + top libres), pero los relevantes son casi todos
  jugadores con dueño.
- **Equipo de cada jugador:** `desde_crudos_v2(crudos, 2026, equipo_desde_espn=True)`. Con
  el equipo previo de nflverse, la semana 1 quedaría toda en el valor neutro y se perdería.
  Costo aceptado: un jugador cambiado de equipo a mitad de temporada queda con su equipo
  actual en las semanas anteriores.
- **Semanas:** todas las semanas NFL terminadas, desde la 1. La regla no usa la historia
  del jugador, así que para 2026 no se exige empezar en la 3.

## 5. Restricciones

- Cero costo; sin dependencias nuevas (numpy, pandas ya están).
- Pruebas con TDD, como el resto del repo. La suite completa tiene que seguir en verde.
- Nada se ejecuta en ESPN: el reporte solo recomienda.
- No editar `src/fantasy/modelo/` (huella del modelo v2 congelado).
- Rama `desempate` + PR; Mario fusiona o pide fusionar.

## 6. Salvedades conocidas

- Las proyecciones históricas de semanas pasadas son las que ESPN guarda ahora (supuesto
  ya aceptado en la decisión 18). Las líneas históricas de nflverse son cercanas al cierre;
  en vivo el martes son más tempranas. El reporte del domingo es el más parecido a lo medido.
- La ventaja esperada es chica (~4 aciertos más por cada 100 empates). En una temporada,
  Mario tiene pocos empates por semana: el valor está en no tirar la moneda a ciegas.

## 7. Documentación al terminar

- `PROYECTO.md`: nueva decisión **26** (la 25 la usa la rama `prob-ganar`; si esa rama no
  se fusiona antes, se conserva el número 26 y se anota el hueco).
- `docs/ESTADO.md`: fase nueva, resultado de 2025 cuando exista, cómo correr el seguimiento.
- `README.md`: una línea sobre los empates en el reporte.

## 8. Decisiones que tomé yo (Claude), para que Mario las revise

- Umbral de empate de 1.0 punto en el reporte, igual que en la prueba; los casi empates
  (1.0–2.0) solo se muestran.
- En vivo el empate se mide con `esperado` (proyección × probabilidad de jugar), que es lo
  que ya usa la alineación; en la prueba histórica, con `proy_espn`.
- El desempate solo considera jugadores sanos y se aplica antes de la regla de duda.
- Sin condición por posición en el criterio de pase.
- El seguimiento 2026 es informativo y no apaga el desempate.
- El seguimiento 2026 usa los datos del reporte y el equipo actual de ESPN, para poder
  contar la semana 1.
- Tras un intercambio por desempate, el total de la alineación se muestra con la suma real.
- Si `prob-ganar` y el desempate pasan los dos, manda `prob-ganar` en las decisiones parejas.
