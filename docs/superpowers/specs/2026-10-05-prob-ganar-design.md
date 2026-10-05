# Probabilidad de ganar: alinear contra el rival — diseño

Fecha: 2026-10-05. Rama: `prob-ganar`. Aprobado por Mario en la sesión (diseño en cuatro partes).

## Problema

Semana 4: BanKAI perdió 101.7 a 128.1 contra PUTIPUERCAS FC con 34.5 puntos de ventaja
proyectada. El diagnóstico con toda la liga (semanas 3–4):

- ESPN no tiene sesgo (error medio por equipo +0.2) pero sí mucho ruido: desviación de ~9
  puntos por jugador y **~23 por equipo**. Con ese ruido, +34.5 era ≈ 86% de ganar: fue mala
  suerte, no un error de dirección.
- Pero el sistema **solo maximiza puntos esperados** (`decision/alineacion.py: optima`). No
  mira al rival ni la varianza. El favorito debería preferir estabilidad; el que va abajo,
  techo. Solo cambia decisiones parejas (Washington 15.3 vs Nabers 13.6) y vale pocos puntos
  porcentuales de victoria por semana; no se sabe si habría cambiado la semana 4.

## Objetivo

Que el reporte muestre la **probabilidad de ganar** la semana y, en las decisiones parejas,
alinee para **maximizarla**, solo si pasa una validación sellada fijada de antemano.

## Decisiones de la sesión

1. **Mandar con validación (opción B).** Se calcula y se muestra; manda solo si pasa.
2. **Decisión 25 (nueva):** la varianza se desarrolla con 2023–2024 y se valida **una sola
   vez** sobre 2025. La regla "nunca reusar 2025" de `docs/ESTADO.md` era para el modelo de
   puntos; la varianza no se ha medido en 2025, así que la prueba sigue limpia. 2025 se usa
   una vez para esto y queda gastada también para la varianza.
3. **Criterio** (ver "Validación"): gana más + porcentajes creíbles.
4. **Enfoque:** errores históricos reales de ESPN remuestreados (no una campana), por
   **grupos de rol** que forma k-means; el número de grupos lo eligen los datos y "1 grupo"
   (solo posición) es la base. Si los grupos no ayudan en 2024, se descartan.
5. **Lo que dice 2026 de cada jugador es su rol** (que se estabiliza rápido), no su varianza
   en 3–4 partidos (que es ruido).

## Restricción

La validación en vivo del modelo v2 exige que **no cambie** `src/fantasy/modelo/` ni
`src/fantasy/ingesta/historico.py`. El trabajo va en un paquete nuevo
`src/fantasy/varianza/` que **solo importa** de ellos.

## 1. Cómo se calcula la probabilidad de ganar

**a) Rol (`varianza/rol.py`).** Por jugador y semana N, solo con partidos de semanas < N de
la temporada (nflverse `semanal` y `snaps`):

| Característica | Definición |
|---|---|
| `adot` | air yards / targets |
| `target_share` | targets / targets del equipo |
| `rush_share` | acarreos / acarreos del equipo |
| `snap_pct` | promedio de % de snaps de ataque |
| `td_share` | puntos por TD / puntos PPR totales |

Mezcla con el año anterior: `x = (n·x_temporada + m·x_previo) / (n + m)`, con `n` partidos
jugados y `m = 3`. Sin año previo (novato), se usa la mediana de la posición como `x_previo`.
Las características se estandarizan por posición con medias y desviaciones de 2023.

**b) Grupos (`varianza/grupos.py`).** k-means por posición (QB, RB, WR, TE) sobre el rol
de 2023, `k ∈ {1, …, 5}`, semilla fija. Para cada `k` se arman las colecciones (c) con 2023 y
se mide en 2024 el **CRPS** medio de la distribución predicha frente al real (jugadores
relevantes, semanas 3–17). Gana el `k` de menor CRPS; empate (diferencia < 1%) → el menor
`k`. Con `k = 1` el modelo es "solo posición".

**c) Colecciones de errores (`varianza/errores.py`).** Error = puntos reales − proyección de
ESPN de esa semana, jugadores relevantes (los de `modelo/evaluar.relevantes`). Se guarda por
(posición, grupo, tramo de proyección). Tramos: terciles de la proyección por posición en los
datos de construcción. Una celda con menos de 200 errores se junta con su tramo vecino del
mismo grupo. Para la temporada en vivo y para 2025 las colecciones se construyen con
2023–2024 juntos.

**d) Correlación entre compañeros.** Con 2023–2024, la correlación de rangos (Spearman)
de los errores de compañeros del mismo equipo NFL en la misma semana, por par de posiciones
(QB-RB, QB-WR, QB-TE, RB-RB, RB-WR, RB-TE, WR-WR, WR-TE, TE-TE). Pares con menos de 300
observaciones → 0. Jugadores de equipos distintos: independientes.

**e) Simulación (`varianza/simular.py`).** Cópula gaussiana: para los titulares de ambos
equipos se generan normales correlacionadas con la matriz de (d) (proyectada a la matriz
definida positiva más cercana si hace falta), se pasan a uniformes y se toma el cuantil
correspondiente de la colección del jugador. Puntos = proyección + error, con piso en el
mínimo de puntos reales observado en la posición (puede ser negativo, p. ej. un QB con
intercepciones).
Un jugador con `p_jugar < 1` juega con esa probabilidad; si no, hace 0. Un jugador ya
jugado o en juego bloqueado aporta sus **puntos reales** (sin simular). **N = 10 000**,
semilla fija por reporte. P(ganar) = fracción de simulaciones en que BanKAI supera al rival;
empate = ½.

**Rival.** Su alineación actual en ESPN. Si un titular suyo está fuera, en descanso o el
lugar está vacío, se usa su alineación `optima` por puntos esperados.

## 2. Cómo alinea y qué muestra el reporte

**Alineación (`varianza/alinear.py`).**
1. Candidatas: todas las alineaciones válidas (con los bloqueados fijos) cuyo esperado queda
   a **≤ 10 puntos** de la `optima`.
2. Se evalúan todas con las **mismas** simulaciones (números aleatorios comunes).
3. Gana la de mayor P(ganar). Si la diferencia con la `optima` es < 1 punto porcentual, se
   queda la `optima`.
4. Encima se aplica lo que ya existe: regla de duda y reemplazos condicionales.

**Reporte (`reporte/armado.py` + plantilla), según `validacion/2025_pganar.json`:**

| Estado | Muestra | Alinea |
|---|---|---|
| No existe el archivo | Nada nuevo | Puntos esperados |
| Pasa 1 y 2 | "Probabilidad de ganar: X%" arriba de "Qué hacer" y, por cada titular cambiado, una línea "Entra A por B: vas arriba/abajo y conviene estabilidad/techo" | **P(ganar)** |
| Solo 2 | "Probabilidad de ganar: X%" | Puntos esperados |
| Ninguna | Aviso: "La probabilidad de ganar no pasó la validación." | Puntos esperados |

En el reporte del **martes** el porcentaje lleva "(preliminar: el rival aún puede cambiar)".
"Vas arriba/abajo" = P(ganar) de la `optima` ≥ 50% o < 50%; "estabilidad/techo" = el que
entra tiene menor/mayor dispersión (rango 10–90%) que el que sale.

Si la simulación falla (falta el artefacto, error de datos), el reporte sale igual que hoy
con un aviso. Nunca bloquea el reporte.

## 3. Validación y sellado

**Desarrollo.** Grupos y colecciones con 2023; `k` con 2024. Ensayo completo de la prueba
sobre 2024 con colecciones de 2023 (para depurar; 2024 ya es de desarrollo).

**Ligas simuladas (`varianza/ligas.py`).** 200 ligas de 8 equipos, semilla fija. Draft en
serpiente de 14 rondas; valor = proyección de ESPN de la semana 1 × (1 + ruido N(0, 0.15));
límites por posición: QB ≤ 3, RB ≤ 6, WR ≤ 6, TE ≤ 3, y cada equipo completa 1 QB, 2 RB,
2 WR, 1 TE antes de la ronda 10. Plantillas fijas toda la temporada. Calendario: cada semana
emparejamiento aleatorio por liga. Semanas 3–17.

En cada enfrentamiento, cada equipo alinea por puntos esperados (`optima`) y por P(ganar)
(sección 2) contra la `optima` del rival; se resuelve con los puntos reales (empate = ½).
Para la simulación se usan solo proyecciones de ESPN y rol con datos anteriores a la semana;
los reales solo resuelven.

**Criterio (fijado antes de construir):**
1. **Gana más:** Δ = victorias(P(ganar)) − victorias(esperados) por enfrentamiento; Δ medio
   > 0 y el IC95 bootstrap remuestreando **semanas** (10 000 réplicas) no incluye el cero.
2. **Porcentajes creíbles:** P(ganar) de las alineaciones por P(ganar), en tramos de 10
   puntos (0–10, …, 90–100). En cada tramo con ≥ 100 enfrentamientos,
   |tasa real − pronóstico medio| < 5 puntos porcentuales.

**Sellado (`varianza/validar.py`).** `fantasy varianza-registrar` congela
`validacion/registro_pganar.json` (commit, `k` por posición, huella de
`modelos/varianza.joblib`, semillas, parámetros). `fantasy varianza-validar --sellado-final`
se niega si: el repo tiene cambios sin commit, `src/fantasy/varianza/` cambió desde el commit
registrado, la huella no coincide, o ya existe `validacion/2025_pganar.json`. 2025 se baja con
`historico.bajar_espn_historico(2025, permitir_sellada=True)` y nflverse 2025 con la ingesta
existente. Resultado: `validacion/2025_pganar.json` con Δ, IC95, tabla de calibración y
`paso_1`, `paso_2`.

## 4. Código, comandos y pruebas

| Archivo | Qué hace |
|---|---|
| `varianza/rol.py` | Rol por jugador y semana, sin fuga, con mezcla |
| `varianza/grupos.py` | k-means por posición, elección de `k` por CRPS |
| `varianza/errores.py` | Colecciones y correlaciones; artefacto `modelos/varianza.joblib` |
| `varianza/simular.py` | Monte Carlo con cópula → P(ganar) |
| `varianza/alinear.py` | Candidatas y elección |
| `varianza/ligas.py` | Draft y ligas simuladas |
| `varianza/validar.py` | Criterio, registro, sellado |

Cambian además `reporte/armado.py`, la plantilla HTML y `cli.py` (comandos
`varianza-construir`, `varianza-ensayo --temporada 2024`, `varianza-registrar`,
`varianza-validar --sellado-final`). Sin dependencias nuevas: `scikit-learn` ya está
(k-means); lo demás con numpy, pandas y scipy.

**Pruebas (TDD):**
- Simulación: errores sin dispersión → P ∈ {0, 1}; equipos idénticos → ~50%; bloqueados
  usan reales; `p_jugar = 0` → 0 puntos.
- Correlación: dos compañeros con ρ = 0.5 salen con ρ ≈ 0.5.
- Alineación: nunca a > 10 de la `optima`; < 1 punto porcentual → `optima`; bloqueados fijos.
- Fuga: el rol de la semana N no usa la semana N ni posteriores.
- Grupos: con datos sin estructura gana `k = 1`.
- Criterio: casos sintéticos que pasan, fallan 1 y fallan 2.
- Sellado: se niega con repo sucio, `varianza/` cambiado, huella distinta o resultado
  existente.
- Reporte: cada fila de la tabla de la sección 2.

**Documentación:** decisión 25 en `PROYECTO.md`, `docs/ESTADO.md` y README.

## Fuera de alcance

- Usar P(ganar) en agencia libre o intercambios.
- Correlación entre rivales del mismo partido NFL.
- Waivers en las ligas simuladas.
- Cambiar el modelo v2 o su validación en vivo.
