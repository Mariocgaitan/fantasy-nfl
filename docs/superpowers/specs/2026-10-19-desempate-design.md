# Desempate por total esperado del equipo — diseño

> 2026-10-19. Rama `desempate` (desde `main`, independiente de `prob-ganar`).
> Versión reducida: el reporte marca empates; no desempata. La sección 3 deja registrada
> la regla por si se retoma la prueba de 2025.

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

## 2. Alcance: versión reducida (decisión de Mario, 2026-10-19)

Con la medición en pares en conflicto, 2026 va en contra (48.1 %). Lo más probable es que
2025 no pase, así que **no se gasta la prueba de 2025 ahora** y el reporte **no desempata**.
Se construye solo lo que sirve de todos modos: saber cuándo una decisión es una moneda al
aire.

**Objetivos**
1. El reporte marca como **empate** las decisiones de alineación con ≤ 1.0 punto de
   diferencia y como **casi empate** las de 1.0 a 2.0, con el total esperado del equipo de
   cada jugador como dato.

**No objetivos**
- No cambia la alineación, ni la proyección de nadie, ni los puntos esperados.
- No corre la prueba de 2025 ni construye su comando (sección 3 queda registrada para
  después). No hay comando de seguimiento 2026 en esta rama.
- No toca agencia libre, intercambios ni el modelo v2 (`src/fantasy/modelo/` queda
  intacto: lo protege la huella de la validación en vivo; ver `docs/ESTADO.md`).
- No integra nada de `prob-ganar`; esta rama sale de `main`.

**Anti-objetivos**
- Que la marca sugiera al jugador del mayor total de equipo como "mejor": es un dato, no
  una recomendación, porque la regla no está validada.
- Gastar 2025 o cambiar la sección 3 sin que Mario retome la prueba.

## 3. La regla registrada (para una prueba futura)

Si Mario retoma el desempate (por ejemplo, si al final de 2026 la regla se recupera en
vivo), esta es la definición congelada. 2025 sigue sin tocar para esta pregunta.

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

### Reporte

Para cada titular movible (no bloqueado) se busca la **mejor alternativa de la banca** que
pueda ocupar su lugar (misma posición; RB/WR/TE para el FLEX), no bloqueada y con
`esperado > 0`. Con `d = esperado_titular − esperado_alternativa`:

- `d ≤ 1.0` → **empate**; `1.0 < d ≤ 2.0` → **casi empate**; más → nada.
- Se compara con `esperado` (proyección × probabilidad de jugar), lo mismo que usa la
  alineación, y sobre la alineación **final** (después de `aplicar_regla_duda`).
- Cada empate se muestra en la sección de la plantilla con los dos nombres, sus puntos y el
  total esperado de su equipo según las apuestas (formato ilustrativo: "Empate:
  Washington 14.1 (su equipo espera X) · Watson 13.8 (su equipo espera Y)"). Si falta la
  línea de alguno, dice "sin línea".
- Una nota fija explica en una línea qué significa: con menos de 1 punto la proyección
  acierta ~51 %, como una moneda; decide Mario.
- No aparece en "Qué hacer" ni cambia la urgencia: es información de la plantilla.
- Aplica a los tres reportes (martes, viernes, domingo); las líneas se leen de
  `crudos["juegos"]` con `contexto.lineas`, como ya hace el modelo v2 en vivo. El equipo
  NFL de cada jugador sale de ESPN (como en el resto del reporte), convertido al código de
  nflverse con `contexto.a_nflverse`.
- Si un jugador de la banca es la mejor alternativa de dos titulares, aparece en los dos
  empates (es información, no un intercambio).

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
- La ventaja medida en 2023–2024 era chica y en 2026 no aparece; por eso el total de
  equipo se muestra como dato y no decide.

## 7. Documentación al terminar

- `docs/ESTADO.md`: la marca de empates en el reporte, la exploración (sección 1) y que la
  prueba de 2025 del desempate queda registrada sin correr.
- `README.md`: una línea sobre los empates en el reporte.
- `PROYECTO.md`: sin decisión nueva (no cambia quién manda).

## 8. Decisiones que tomé yo (Claude), para que Mario las revise

- Umbrales: empate ≤ 1.0, casi empate 1.0–2.0, medidos con `esperado` sobre la alineación
  final.
- La marca va en la sección de la plantilla, no en "Qué hacer".
- No hay comando de seguimiento 2026 en esta rama; si se retoma, se construye junto con la
  prueba de 2025.
