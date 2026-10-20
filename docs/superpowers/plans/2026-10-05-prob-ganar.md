# Probabilidad de ganar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el reporte calcule la probabilidad de ganar la semana contra el rival real y, si pasa una validación sellada sobre 2025, alinee para maximizarla en las decisiones parejas.

**Architecture:** Paquete nuevo `src/fantasy/varianza/`: rol de cada jugador (nflverse, sin fuga) → grupos por rol (k-means por posición, `k` elegido por CRPS en 2024) → colecciones de errores reales de ESPN por (posición, grupo, tramo) + correlación entre compañeros → Monte Carlo con cópula gaussiana → P(ganar). Ligas simuladas comparan "alinear por esperados" contra "alinear por P(ganar)" con puntos reales; la corrida única de 2025 decide qué muestra el reporte.

**Tech Stack:** Python 3.12, pandas, numpy, scipy (ya instalada como dependencia de scikit-learn; se declara), scikit-learn (KMeans), joblib, Jinja2, pytest, ruff, uv.

**Spec:** `docs/superpowers/specs/2026-10-05-prob-ganar-design.md`

## Estado de ejecución (2026-10-06) — LEER PRIMERO AL RETOMAR

**Hechas (commits en la rama `prob-ganar`):** Tasks 1–9. Suite completa: 238 pruebas en verde.
Comandos con `uv run --no-env-file ...` (hay un `UV_ENV_FILE=.env` global y no existe `.env`).

**Resultados hasta ahora:**
- `varianza-construir` (Task 4) eligió **k = 1 en todas las posiciones**. La revisión de mitad de fase
  mostró que **la prueba fue degenerada**: con solo 2023 para formar grupos, QB/TE tienen 180 filas
  (toda celda < 200 → cae a la posición, CRPS idéntico para todo k) y en RB/WR (450 filas) solo
  k = 2 se probó de verdad; k ≥ 3 cae a la posición. No prueba que el rol no importe.
- Ensayo 2024, 200 ligas (Task 8, desarrollo): **gana más ❌** (delta 0.0, IC95 [−0.0001, 0.0001];
  la alineación cambió en 23 de 24 000 enfrentamientos) · **porcentajes creíbles ✅** (máx. ±2.3
  puntos por tramo). Sin grupos, jugadores de la misma posición y tramo tienen la misma
  distribución y P(ganar) casi no puede preferir a uno.
- Comprobación real: viernes de la semana 4 → P(ganar) **76%** contra Norway Ass.

**Decisión de Mario (2026-10-06): opción B — hacer justa la prueba de grupos antes del sellado.**
Siguiente paso al retomar (Task 4b, TDD):
1. `grupos.elegir_k(..., minimo_celda=100)`: durante la **elección de k** la cadena de respaldo usa
   un mínimo de 100 errores (no 200). Implementarlo como parámetro `minimo` en
   `Colecciones.muestra` / `errores.construir` (por defecto `MINIMO_CELDA = 200`, que sigue rigiendo
   el artefacto final). Prueba: con 450 filas WR estructuradas en 3 grupos, `elegir_k` con
   mínimo 100 distingue k = 3 (CRPS distinto de k = 1).
2. Volver a correr `uv run --no-env-file fantasy varianza-construir` y anotar la tabla CRPS y el k.
3. Si cambia algún k, volver a correr `fantasy varianza-ensayo` (200 ligas, ~25 min, en segundo
   plano) y anotar el resultado. Si no cambia, quedarse con el ensayo ya hecho.
4. Anotar en la spec (sección 1b) el ajuste y su motivo (tamaño de los datos, no el resultado).

**Task 4b hecha (2026-10-19, commit `baaa391`).** Con el mínimo de 100 al elegir k, la tabla
CRPS: QB 4.699/4.701/4.704/4.699/4.699 · RB 4.252/4.244/4.245/4.251/4.236 · WR
4.756/4.750/4.759/4.783/4.795 · TE 3.935/3.921/3.935/3.935/3.935 (k = 1…5). Mayor mejora 0.4 %
(< 1 % de empate) → **k = 1 en todas**; `modelos/varianza.joblib` quedó idéntico, así que vale el
ensayo ya hecho (gana más ❌, porcentajes creíbles ✅). Anotado en la spec, sección 1b.

**Después:** Task 10 (docs: `docs/ESTADO.md`, `README.md`; la decisión 25 ya está en
`PROYECTO.md`), revisión final de la rama (subagente), PR. **El sellado de 2025
(`varianza-registrar` + `varianza-validar --sellado-final`) solo con el visto bueno de Mario.**

**Pendientes menores de la revisión (no bloquean):**
- La reparación de la matriz de correlación puede debilitar pares si la matriz no es válida;
  con las correlaciones reales (débiles) es improbable. Podría registrarse cuando ocurra.
- Posible doble conteo de ausencias en vivo: los errores históricos ya incluyen 0 de jugadores
  que no jugaron y en vivo además se aplica `p_jugar < 1` a los dudosos.
- Los grupos se ajustan con filas de 2023 sin año previo y se aplican a filas que sí lo tienen.
- `eficiencia` llega a ~10 con pocas oportunidades (puede sesgar k-means).

Bitácora detallada (no versionada): `.superpowers/sdd/2026-10-05-prob-ganar/progress.md`.

## Global Constraints

- **No modificar** `src/fantasy/modelo/`, `src/fantasy/ingesta/historico.py`, `src/fantasy/ingesta/nflverse.py` ni `src/fantasy/proyeccion/modelo.py` (modelo v2 congelado hasta la validación en vivo). Solo se **importan**.
- 2025 se toca **una sola vez**, en `fantasy varianza-validar --sellado-final`. Ningún test ni comando de desarrollo baja 2025.
- Constantes (copiadas de la spec): `PESO_PREVIO = 3`; `k ∈ {1..5}`, empate de CRPS < 1% → menor `k`; `MINIMO_CELDA = 200`; `MINIMO_PAR = 300`; `N_SIM = 10_000`; `MARGEN = 10.0` puntos; `UMBRAL = 0.01`; 200 ligas, 8 equipos, 14 rondas, ruido 0.15, topes QB 3 / RB 6 / WR 6 / TE 3, pool de 200; semanas 3–17; bootstrap 10 000 réplicas por semanas; calibración en tramos de 10 puntos con ≥ 100 casos y error < 5 puntos.
- Manda = `paso_1 and paso_2`; muestra el porcentaje = `paso_2`; si existe el resultado y no `paso_2` → aviso "La probabilidad de ganar no pasó la validación.".
- La simulación **nunca** bloquea el reporte: cualquier excepción → aviso y alineación por esperados.
- Textos visibles en español, sin jerga sin explicar.
- Comandos: `uv run pytest -q`, `uv run ruff check src tests`.
- Archivos con fin de línea LF.
- Cero costo; nada se ejecuta en ESPN.

## Review Focus

1. **Jugador en descanso o con proyección 0 entre los titulares** (propios o del rival): debe aportar 0, no `0 + error`. → test en Task 5.
2. **Rival con un titular fuera, en descanso o con lugar vacío:** se usa su `optima`; sin eso la P(ganar) sale inflada. → test en Task 9.
3. **Reporte del domingo con partidos ya jugados (bloqueados):** usan sus puntos reales y nunca entran ni salen en la alineación elegida. → tests en Task 5 y Task 6.
4. **Artefacto que no coincide con el validado** (alguien regeneró `varianza.joblib` después de la corrida): el reporte no debe mandar ni mostrar porcentaje. → test en Task 8.
5. **Instantánea sin nflverse** (falló la descarga): el rol cae al año previo/mediana y el reporte sale igual. → test en Task 9.

---

## File Structure

- Create `src/fantasy/varianza/__init__.py` — vacío.
- Create `src/fantasy/varianza/rol.py` — rasgos de rol por partido y previos a cada semana, con mezcla.
- Create `src/fantasy/varianza/errores.py` — `Colecciones`, `construir`, `crps`, `correlaciones`, `rho`.
- Create `src/fantasy/varianza/grupos.py` — `GruposPos`, `ajustar`, `asignar`, `elegir_k`.
- Create `src/fantasy/varianza/datos.py` — tabla jugador-semana de una temporada.
- Create `src/fantasy/varianza/artefacto.py` — `Artefacto`, `construir`, `guardar`, `cargar`.
- Create `src/fantasy/varianza/simular.py` — Monte Carlo, `p_ganar`, `dispersion`.
- Create `src/fantasy/varianza/alinear.py` — `candidatas`, `elegir`.
- Create `src/fantasy/varianza/ligas.py` — `draft`, `temporada`.
- Create `src/fantasy/varianza/validar.py` — `criterio`, `estado`, `validar_sellado`.
- Create `src/fantasy/varianza/en_vivo.py` — rival, simulación de la semana, explicaciones.
- Modify `src/fantasy/config.py` — `RUTA_VARIANZA`, `RUTA_ROL_PREVIO`.
- Modify `src/fantasy/cli.py` — `varianza-construir`, `varianza-ensayo`, `varianza-registrar`, `varianza-validar`.
- Modify `src/fantasy/reporte/armado.py` — campos `p_ganar`, `p_ganar_preliminar`, `explicaciones_pg`; cableado.
- Modify `src/fantasy/reporte/plantillas/reporte.html.j2` — porcentaje arriba de "Qué hacer".
- Modify `pyproject.toml` — declarar `scipy`.
- Tests nuevos: `tests/test_varianza_rol.py`, `tests/test_varianza_errores.py`, `tests/test_varianza_grupos.py`, `tests/test_varianza_datos.py`, `tests/test_varianza_simular.py`, `tests/test_varianza_alinear.py`, `tests/test_varianza_ligas.py`, `tests/test_varianza_validar.py`, `tests/test_varianza_reporte.py`; helper `tests/varianza_util.py`.
- Docs: `PROYECTO.md` (decisión 25), `docs/ESTADO.md`, `README.md`.

**Revisiones (forma de trabajo de Mario):** revisión independiente (subagente) al terminar la Task 6 y otra de toda la rama al final, antes del PR.

---

### Task 1: Rol de cada jugador sin fuga

**Files:**
- Create: `src/fantasy/varianza/__init__.py`, `src/fantasy/varianza/rol.py`
- Test: `tests/test_varianza_rol.py`

**Interfaces:**
- Produces:
  - `rol.RASGOS: dict[str, list[str]]`, `rol.TODOS: list[str]`, `rol.PESO_PREVIO = 3`
  - `rol.por_partido(semanal, snaps, jugadores) -> DataFrame[jugador_id, semana, target_share, rel_depth, rush_share, eficiencia, snap_pct]`
  - `rol.leer(crudos: dict) -> DataFrame` (igual que `por_partido`; vacío con esas columnas si faltan `semanal`/`snaps`/`jugadores`)
  - `rol.promedio_temporada(pp) -> DataFrame[jugador_id, *TODOS]`
  - `rol.previo_a(pp, base, previo=None) -> DataFrame[jugador_id, semana, pos, *TODOS, fuente_max]` donde `base` tiene `jugador_id, semana, pos`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_rol.py
import pandas as pd
import pytest

from fantasy.varianza import rol


def _semanal(filas):
    base = {"season_type": "REG", "team": "DET", "receptions": 0, "fantasy_points_ppr": 0.0,
            "target_share": 0.0, "air_yards_share": 0.0, "targets": 0, "carries": 0}
    return pd.DataFrame([{**base, **f} for f in filas])


JUG = pd.DataFrame({"gsis_id": ["a", "b"], "pfr_id": ["pa", "pb"], "espn_id": [1, 2]})


def test_por_partido_calcula_rasgos():
    s = _semanal([
        {"player_id": "a", "week": 1, "carries": 10, "targets": 5, "receptions": 4,
         "fantasy_points_ppr": 20.0, "target_share": 0.25, "air_yards_share": 0.5},
        {"player_id": "b", "week": 1, "carries": 10},
    ])
    n = pd.DataFrame({"week": [1], "pfr_player_id": ["pa"], "offense_pct": [0.8]})
    pp = rol.por_partido(s, n, JUG).set_index("jugador_id")
    a = pp.loc[1]
    assert a.rush_share == pytest.approx(0.5)
    assert a.rel_depth == pytest.approx(2.0)
    assert a.eficiencia == pytest.approx((20 - 4) / 15)
    assert a.snap_pct == pytest.approx(0.8)
    assert pd.isna(pp.loc[2].snap_pct)  # sin fila de snaps no es 0%


def test_previo_usa_solo_semanas_anteriores_y_mezcla_con_el_previo():
    pp = pd.DataFrame({"jugador_id": [1, 1, 1], "semana": [1, 2, 3],
                       "target_share": [0.3, 0.5, 0.9], "rel_depth": 1.0,
                       "rush_share": 0.0, "eficiencia": 1.0, "snap_pct": 0.7})
    base = pd.DataFrame({"jugador_id": [1], "semana": [3], "pos": ["WR"]})
    previo = pd.DataFrame({"jugador_id": [1], "target_share": [0.1], "rel_depth": [1.0],
                           "rush_share": [0.0], "eficiencia": [1.0], "snap_pct": [0.7]})
    r = rol.previo_a(pp, base, previo).iloc[0]
    assert r.target_share == pytest.approx((2 * 0.4 + 3 * 0.1) / 5)  # la semana 3 no entra
    assert r.fuente_max == 2


def test_sin_previo_usa_la_mediana_de_la_posicion():
    pp = pd.DataFrame({"jugador_id": [1, 2], "semana": [1, 1], "target_share": [0.2, 0.4],
                       "rel_depth": 1.0, "rush_share": 0.0, "eficiencia": 1.0, "snap_pct": 0.5})
    base = pd.DataFrame({"jugador_id": [1, 2, 3], "semana": [2, 2, 2], "pos": "WR"})
    previo = pd.DataFrame({"jugador_id": [1, 2], "target_share": [0.2, 0.4], "rel_depth": 1.0,
                           "rush_share": 0.0, "eficiencia": 1.0, "snap_pct": 0.5})
    r = rol.previo_a(pp, base, previo).set_index("jugador_id")
    assert r.loc[3, "target_share"] == pytest.approx(0.3)  # novato sin partidos: mediana previa


def test_previo_nunca_usa_la_semana_ni_posteriores():
    pp = pd.DataFrame({"jugador_id": [1] * 5, "semana": [1, 2, 3, 4, 5], "target_share": 0.2,
                       "rel_depth": 1.0, "rush_share": 0.0, "eficiencia": 1.0, "snap_pct": 0.5})
    base = pd.DataFrame({"jugador_id": [1, 1, 1], "semana": [2, 4, 5], "pos": "WR"})
    r = rol.previo_a(pp, base)
    assert (r.fuente_max < r.semana).all()


def test_leer_sin_nflverse_devuelve_vacio():
    pp = rol.leer({"proyecciones": {}})
    assert pp.empty and set(rol.TODOS) <= set(pp.columns)
    base = pd.DataFrame({"jugador_id": [1], "semana": [5], "pos": ["RB"]})
    r = rol.previo_a(pp, base)
    assert r[rol.TODOS].notna().all().all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_rol.py -q`
Expected: FAIL (`ModuleNotFoundError: fantasy.varianza`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/__init__.py
```

```python
# src/fantasy/varianza/rol.py
"""Rol de cada jugador (cómo lo usa su equipo), solo con partidos anteriores a la semana.

El rol se estabiliza rápido; la varianza de un jugador en 3–4 partidos es ruido. Por eso lo
que dice 2026 de cada jugador entra por aquí y no por sus puntos."""

import io

import numpy as np
import pandas as pd

from fantasy.modelo.variables import FugaDeDatos

RASGOS = {
    "QB": ["rush_share", "snap_pct"],
    "RB": ["target_share", "rush_share", "snap_pct", "eficiencia"],
    "WR": ["target_share", "rel_depth", "snap_pct", "eficiencia"],
    "TE": ["target_share", "rel_depth", "snap_pct", "eficiencia"],
}
TODOS = ["target_share", "rel_depth", "rush_share", "eficiencia", "snap_pct"]
PESO_PREVIO = 3  # el año anterior pesa como 3 partidos
SEMANA_MAX = 18  # temporada regular


def _division(a, b) -> np.ndarray:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.divide(a, b, out=np.zeros_like(a), where=b > 0)


def por_partido(semanal: pd.DataFrame, snaps: pd.DataFrame,
                jugadores: pd.DataFrame) -> pd.DataFrame:
    ids = jugadores.dropna(subset=["espn_id"])
    s = semanal[semanal["season_type"] == "REG"].copy()
    s["acarreos_eq"] = s.groupby(["team", "week"])["carries"].transform("sum")
    s = s.merge(ids[["gsis_id", "espn_id"]], left_on="player_id", right_on="gsis_id")
    ts = s["target_share"].fillna(0.0).to_numpy(float)
    oport = (s["targets"] + s["carries"]).to_numpy(float)
    out = pd.DataFrame({
        "jugador_id": s["espn_id"].astype("int64").to_numpy(),
        "semana": s["week"].astype("int64").to_numpy(),
        "target_share": ts,
        "rel_depth": _division(s["air_yards_share"].fillna(0.0), ts),
        "rush_share": _division(s["carries"], s["acarreos_eq"]),
        "eficiencia": _division(s["fantasy_points_ppr"] - s["receptions"], oport),
    })
    out = out.groupby(["jugador_id", "semana"], as_index=False).mean()
    n = snaps.merge(ids[["pfr_id", "espn_id"]], left_on="pfr_player_id", right_on="pfr_id")
    n = (n.groupby(["espn_id", "week"], as_index=False)["offense_pct"].max()
         .rename(columns={"espn_id": "jugador_id", "week": "semana", "offense_pct": "snap_pct"}))
    n[["jugador_id", "semana"]] = n[["jugador_id", "semana"]].astype("int64")
    n = n[n.semana <= SEMANA_MAX]
    # Sin fila de snaps no es 0% de snaps: queda vacío y lo cubre la mezcla.
    return out.merge(n, on=["jugador_id", "semana"], how="left")


def _vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float) for c in ["jugador_id", "semana", *TODOS]})


def leer(crudos: dict) -> pd.DataFrame:
    if not all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        return _vacio()
    t = {k: pd.read_csv(io.StringIO(crudos[k]), low_memory=False)
         for k in ("semanal", "snaps", "jugadores")}
    return por_partido(t["semanal"], t["snaps"], t["jugadores"])


def promedio_temporada(pp: pd.DataFrame) -> pd.DataFrame:
    return pp.groupby("jugador_id", as_index=False)[TODOS].mean()


def previo_a(pp: pd.DataFrame, base: pd.DataFrame,
             previo: pd.DataFrame | None = None) -> pd.DataFrame:
    """Para cada fila de `base` (jugador_id, semana, pos): promedio de sus partidos de semanas
    anteriores mezclado con el año previo, `x = (n·x_temporada + 3·x_previo) / (n + 3)`.
    Sin año previo: mediana de la posición en el previo; si tampoco hay, la de la temporada."""
    ref = previo.set_index("jugador_id") if previo is not None and len(previo) else None
    partes = []
    for w, b in base.groupby("semana"):
        antes = pp[pp.semana < w]
        g = antes.groupby("jugador_id")
        media, cuenta = g[TODOS].mean(), g[TODOS].count()
        f = b[["jugador_id", "semana", "pos"]].reset_index(drop=True)
        f["fuente_max"] = f.jugador_id.map(g["semana"].max()).fillna(0).astype(int)
        for c in TODOS:
            xt = f.jugador_id.map(media[c]) if c in media else pd.Series(np.nan, index=f.index)
            n = f.jugador_id.map(cuenta[c]).fillna(0) if c in cuenta else 0.0
            xp = f.jugador_id.map(ref[c]) if ref is not None else pd.Series(np.nan, index=f.index)
            xp = xp.fillna(xp.groupby(f.pos).transform("median"))
            xp = xp.fillna(xt.groupby(f.pos).transform("median")).fillna(0.0)
            f[c] = (n * xt.fillna(0.0) + PESO_PREVIO * xp) / (n + PESO_PREVIO)
        partes.append(f)
    if not partes:
        return pd.DataFrame(columns=["jugador_id", "semana", "pos", *TODOS, "fuente_max"])
    out = pd.concat(partes, ignore_index=True)
    if (out.fuente_max >= out.semana).any():
        raise FugaDeDatos("el rol usa datos de su propia semana o posteriores")
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_rol.py -q && uv run ruff check src/fantasy/varianza tests/test_varianza_rol.py`
Expected: 5 passed, ruff sin errores.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/varianza tests/test_varianza_rol.py
git commit -m "feat(varianza): rol de cada jugador sin fuga, mezclado con el año previo"
```

---

### Task 2: Colecciones de errores, CRPS y correlación entre compañeros

**Files:**
- Create: `src/fantasy/varianza/errores.py`
- Modify: `pyproject.toml` (declarar `scipy>=1.11` en `dependencies`; `uv lock`)
- Test: `tests/test_varianza_errores.py`

**Interfaces:**
- Produces:
  - `errores.MINIMO_CELDA = 200`, `errores.MINIMO_PAR = 300`, `errores.POS = ("QB","RB","WR","TE")`
  - `@dataclass Colecciones(cortes: dict[str, tuple[float,float]], muestras: dict[tuple, np.ndarray], piso: dict[str, float])` con `.tramo(pos, proy) -> int` (0,1,2) y `.muestra(pos, grupo, tramo) -> np.ndarray` (ordenada; cadena de respaldo (pos,grupo,tramo) → (pos,grupo) → (pos,))
  - `errores.construir(filas[pos, grupo, proy_espn, real]) -> Colecciones`
  - `errores.crps(muestra_ordenada: np.ndarray, z: np.ndarray) -> np.ndarray`
  - `errores.correlaciones(filas[temporada, semana, equipo, jugador_id, pos, error], minimo=MINIMO_PAR) -> dict[tuple[str,str], float]` (correlación ya convertida a la de la cópula gaussiana)
  - `errores.rho(corr, pos_a, pos_b) -> float`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_errores.py
import numpy as np
import pandas as pd
import pytest

from fantasy.varianza import errores


def test_crps_de_un_punto_es_la_distancia():
    assert errores.crps(np.array([0.0]), np.array([1.0, -2.0])) == pytest.approx([1.0, 2.0])


def test_crps_normal_estandar_en_cero():
    m = np.sort(np.random.default_rng(0).standard_normal(200_000))
    assert errores.crps(m, np.array([0.0]))[0] == pytest.approx(0.2337, abs=0.005)


def _filas(n, rng, pos="WR", grupo=0, proy=10.0, sd=5.0):
    return pd.DataFrame({"pos": pos, "grupo": grupo, "proy_espn": proy,
                         "real": proy + rng.normal(0, sd, n)})


def test_construir_tramos_y_respaldo():
    rng = np.random.default_rng(1)
    f = pd.concat([_filas(600, rng, proy=5.0), _filas(600, rng, proy=10.0),
                   _filas(600, rng, proy=20.0), _filas(50, rng, grupo=1, proy=20.0)])
    col = errores.construir(f)
    assert col.tramo("WR", 4.0) == 0 and col.tramo("WR", 25.0) == 2
    assert len(col.muestra("WR", 0, 2)) == 600
    # grupo 1 tiene 50 errores: cae a (WR,) completo
    assert len(col.muestra("WR", 1, 2)) == len(col.muestras[("WR",)])
    assert np.all(np.diff(col.muestra("WR", 0, 0)) >= 0)
    assert col.piso["WR"] == pytest.approx(f.real.min())


def test_correlaciones_entre_companeros():
    rng = np.random.default_rng(2)
    n = 800
    z = rng.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], n)
    qb = pd.DataFrame({"temporada": 2023, "semana": np.arange(n) % 17, "equipo":
                       [f"T{i // 17}" for i in range(n)], "jugador_id": np.arange(n),
                       "pos": "QB", "error": z[:, 0]})
    wr = qb.assign(jugador_id=qb.jugador_id + 10_000, pos="WR", error=z[:, 1])
    te = qb.head(100).assign(jugador_id=qb.head(100).jugador_id + 20_000, pos="TE")
    corr = errores.correlaciones(pd.concat([qb, wr, te]))
    assert corr[("QB", "WR")] == pytest.approx(0.5, abs=0.08)
    assert corr[("QB", "TE")] == 0.0  # solo 100 pares
    assert errores.rho(corr, "WR", "QB") == corr[("QB", "WR")]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_errores.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/errores.py
"""Errores reales de ESPN (puntos reales − proyección) por tipo de jugador, su CRPS y la
correlación entre compañeros del mismo equipo NFL."""

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

MINIMO_CELDA = 200
MINIMO_PAR = 300
POS = ("QB", "RB", "WR", "TE")


@dataclass
class Colecciones:
    cortes: dict[str, tuple[float, float]]
    muestras: dict[tuple, np.ndarray]
    piso: dict[str, float]

    def tramo(self, pos: str, proy: float) -> int:
        bajo, alto = self.cortes[pos]
        return int(proy > bajo) + int(proy > alto)

    def muestra(self, pos: str, grupo: int, tramo: int) -> np.ndarray:
        for clave in ((pos, int(grupo), int(tramo)), (pos, int(grupo))):
            m = self.muestras.get(clave)
            if m is not None and len(m) >= MINIMO_CELDA:
                return m
        return self.muestras[(pos,)]


def _clave(k) -> tuple:
    k = k if isinstance(k, tuple) else (k,)
    return tuple(x if isinstance(x, str) else int(x) for x in k)


def construir(filas: pd.DataFrame) -> Colecciones:
    f = filas.dropna(subset=["real"]).copy()
    f["error"] = f["real"] - f["proy_espn"]
    cortes = {p: tuple(float(x) for x in np.quantile(g.proy_espn, [1 / 3, 2 / 3]))
              for p, g in f.groupby("pos")}
    col = Colecciones(cortes, {}, {p: float(g.real.min()) for p, g in f.groupby("pos")})
    f["tramo"] = [col.tramo(p, x) for p, x in zip(f.pos, f.proy_espn, strict=True)]
    for claves in (["pos"], ["pos", "grupo"], ["pos", "grupo", "tramo"]):
        for k, g in f.groupby(claves):
            col.muestras[_clave(k)] = np.sort(g.error.to_numpy(float))
    return col


def crps(muestra: np.ndarray, z: np.ndarray) -> np.ndarray:
    """CRPS de la distribución empírica `muestra` (ordenada) en cada valor de `z`:
    E|X − z| − ½·E|X − X'|."""
    x, n = muestra, len(muestra)
    z = np.asarray(z, float)
    c = np.concatenate([[0.0], np.cumsum(x)])
    k = np.searchsorted(x, z, side="right")
    e1 = (k * z - c[k] + (c[n] - c[k]) - (n - k) * z) / n
    i = np.arange(1, n + 1)
    e2 = 2.0 * np.sum((2 * i - n - 1) * x) / n**2
    return e1 - 0.5 * e2


def correlaciones(filas: pd.DataFrame, minimo: int = MINIMO_PAR) -> dict[tuple[str, str], float]:
    """Spearman de los errores de compañeros (mismo equipo, misma semana) por par de
    posiciones, pasada a la correlación de una cópula gaussiana: 2·sen(π·ρs/6)."""
    f = filas.dropna(subset=["equipo", "error"])
    f = f.assign(clave=f.temporada.astype(str) + "-" + f.semana.astype(str) + "-"
                 + f.equipo.astype(str))
    p = f.merge(f, on="clave", suffixes=("_a", "_b"))
    p = p[p.jugador_id_a < p.jugador_id_b]
    salida = {}
    for par in itertools.combinations_with_replacement(POS, 2):
        directo = (p.pos_a == par[0]) & (p.pos_b == par[1])
        cruzado = (p.pos_a == par[1]) & (p.pos_b == par[0]) & (par[0] != par[1])
        x = pd.concat([p.loc[directo, "error_a"], p.loc[cruzado, "error_b"]])
        y = pd.concat([p.loc[directo, "error_b"], p.loc[cruzado, "error_a"]])
        if len(x) < minimo:
            salida[par] = 0.0
            continue
        rs = float(np.corrcoef(x.rank(), y.rank())[0, 1])
        salida[par] = float(2 * np.sin(np.pi * rs / 6))
    return salida


def rho(corr: dict[tuple[str, str], float], pos_a: str, pos_b: str) -> float:
    return corr.get(tuple(sorted((pos_a, pos_b), key=POS.index)), 0.0)
```

Nota: las claves del dict siguen el orden de `POS` (`("QB","WR")`, no `("WR","QB")`); `rho` ordena igual.

Además, en `pyproject.toml`, dentro de `dependencies`, añade la línea `"scipy>=1.11",` (la usa la Task 5) y corre `uv lock`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_errores.py -q && uv run ruff check src/fantasy/varianza tests/test_varianza_errores.py`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/varianza/errores.py tests/test_varianza_errores.py pyproject.toml uv.lock
git commit -m "feat(varianza): colecciones de errores de ESPN, CRPS y correlación entre compañeros"
```

---

### Task 3: Grupos por rol y elección de `k`

**Files:**
- Create: `src/fantasy/varianza/grupos.py`
- Test: `tests/test_varianza_grupos.py`

**Interfaces:**
- Consumes: `rol.RASGOS`, `errores.construir`, `errores.crps`, `errores.POS`.
- Produces:
  - `@dataclass GruposPos(rasgos: list[str], media: np.ndarray, desv: np.ndarray, centros: np.ndarray)` con `.asignar(X: DataFrame) -> np.ndarray[int]`
  - `grupos.ajustar(filas, pos, k, semilla=0) -> GruposPos`
  - `grupos.asignar(grupos: dict[str, GruposPos], filas) -> pd.Series[int]` (0 para posiciones sin grupos)
  - `grupos.elegir_k(construccion, eleccion, ks=range(1, 6), semilla=0) -> tuple[dict[str,int], pd.DataFrame[pos,k,crps]]`; `construccion`/`eleccion` traen `pos, *rasgos, proy_espn, real`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_grupos.py
import numpy as np
import pandas as pd

from fantasy.varianza import grupos
from fantasy.varianza.rol import RASGOS


def _wr(n, rng, estructura):
    X = rng.normal(0, 1, (n, 4))
    if estructura:  # dos tipos: los de rasgo 0 alto son explosivos
        explosivo = rng.random(n) < 0.5
        X[:, 0] = np.where(explosivo, 3.0, -3.0) + rng.normal(0, 0.3, n)
        sd = np.where(explosivo, 14.0, 3.0)
    else:
        sd = np.full(n, 8.0)
    f = pd.DataFrame(X, columns=RASGOS["WR"]).assign(pos="WR", proy_espn=10.0)
    return f.assign(real=10.0 + rng.normal(0, 1, n) * sd)


def test_sin_estructura_gana_k_1():
    rng = np.random.default_rng(0)
    k, tabla = grupos.elegir_k(_wr(4000, rng, False), _wr(4000, rng, False))
    assert k["WR"] == 1
    assert set(tabla.k) == {1, 2, 3, 4, 5}


def test_con_estructura_gana_mas_de_un_grupo():
    rng = np.random.default_rng(1)
    k, _ = grupos.elegir_k(_wr(4000, rng, True), _wr(4000, rng, True))
    assert k["WR"] >= 2


def test_asignar_respeta_posiciones_y_es_estable():
    rng = np.random.default_rng(2)
    f = _wr(1000, rng, True)
    g = {"WR": grupos.ajustar(f, "WR", 2)}
    mezcla = pd.concat([f.head(5), pd.DataFrame({"pos": ["QB"], "rush_share": [0.1],
                                                 "snap_pct": [1.0]})], ignore_index=True)
    a = grupos.asignar(g, mezcla)
    assert a.iloc[-1] == 0  # QB sin grupos
    assert (a.iloc[:5].to_numpy() == g["WR"].asignar(f.head(5))).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_grupos.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/grupos.py
"""Tipos de jugador por rol (k-means por posición). El número de grupos lo eligen los datos:
el que mejor predice la variación (CRPS) en una temporada que no se usó para formarlos."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from fantasy.varianza import errores
from fantasy.varianza.rol import RASGOS

EMPATE = 0.01  # 1% de CRPS: se prefiere el k más chico


@dataclass
class GruposPos:
    rasgos: list[str]
    media: np.ndarray
    desv: np.ndarray
    centros: np.ndarray

    def asignar(self, X: pd.DataFrame) -> np.ndarray:
        z = (X[self.rasgos].to_numpy(float) - self.media) / self.desv
        d = ((z[:, None, :] - self.centros[None, :, :]) ** 2).sum(axis=2)
        return d.argmin(axis=1)


def ajustar(filas: pd.DataFrame, pos: str, k: int, semilla: int = 0) -> GruposPos:
    rasgos = RASGOS[pos]
    X = filas.loc[filas.pos == pos, rasgos].to_numpy(float)
    media, desv = X.mean(axis=0), X.std(axis=0)
    desv[desv == 0] = 1.0
    if k == 1:
        centros = np.zeros((1, len(rasgos)))
    else:
        km = KMeans(n_clusters=k, n_init=10, random_state=semilla).fit((X - media) / desv)
        centros = km.cluster_centers_
    return GruposPos(rasgos, media, desv, centros)


def asignar(grupos: dict[str, GruposPos], filas: pd.DataFrame) -> pd.Series:
    salida = pd.Series(0, index=filas.index, dtype=int)
    for pos, g in grupos.items():
        m = filas.pos == pos
        if m.any():
            salida[m] = g.asignar(filas[m])
    return salida


def _crps_medio(g: GruposPos, c: pd.DataFrame, e: pd.DataFrame, pos: str) -> float:
    col = errores.construir(c.assign(grupo=g.asignar(c)))
    d = pd.DataFrame({"g": g.asignar(e), "t": [col.tramo(pos, x) for x in e.proy_espn],
                      "z": (e.real - e.proy_espn).to_numpy(float)})
    total = sum(errores.crps(col.muestra(pos, gi, ti), s.z.to_numpy()).sum()
                for (gi, ti), s in d.groupby(["g", "t"]))
    return float(total / len(d))


def elegir_k(construccion: pd.DataFrame, eleccion: pd.DataFrame, ks=range(1, 6),
             semilla: int = 0) -> tuple[dict[str, int], pd.DataFrame]:
    elegido, filas = {}, []
    for pos in errores.POS:
        c = construccion[(construccion.pos == pos) & construccion.real.notna()]
        e = eleccion[(eleccion.pos == pos) & eleccion.real.notna()]
        if c.empty or e.empty:
            continue
        res = {k: _crps_medio(ajustar(c, pos, k, semilla), c, e, pos) for k in ks}
        filas += [{"pos": pos, "k": k, "crps": v} for k, v in res.items()]
        mejor = min(res.values())
        elegido[pos] = min(k for k, v in res.items() if v <= mejor * (1 + EMPATE))
    return elegido, pd.DataFrame(filas)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_grupos.py -q && uv run ruff check src/fantasy/varianza tests/test_varianza_grupos.py`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/varianza/grupos.py tests/test_varianza_grupos.py
git commit -m "feat(varianza): grupos por rol con k elegido por CRPS fuera de muestra"
```

---

### Task 4: Tabla histórica, artefacto y `fantasy varianza-construir`

**Files:**
- Create: `src/fantasy/varianza/datos.py`, `src/fantasy/varianza/artefacto.py`
- Modify: `src/fantasy/config.py`, `src/fantasy/cli.py`
- Test: `tests/test_varianza_datos.py`
- Output (commit): `modelos/varianza.joblib`

**Interfaces:**
- Consumes: `variables.desde_crudos`, `variables.equipo_previo`, `nflverse.uso_extendido`, `evaluar.relevantes`, `historico.cargar_historico`, `rol.*`, `grupos.*`, `errores.*`.
- Produces:
  - `datos.SEMANAS = range(3, 18)`
  - `datos.tabla(crudos, temporada, previo=None) -> DataFrame[jugador_id, temporada, semana, pos, proy_espn, real, equipo, relevante, *rol.TODOS, fuente_max]` (semanas 1–17, solo `proy_espn > 0`)
  - `datos.para_construir(t) -> DataFrame` (filas `relevante` de semanas 3–17)
  - `@dataclass Artefacto(version: int, k: dict[str,int], grupos: dict[str, GruposPos], colecciones: Colecciones, correlaciones: dict, temporadas: tuple[int, ...])`
  - `artefacto.construir(filas_grupos, filas_colecciones, k, semilla=0) -> Artefacto`
  - `artefacto.guardar(art, ruta)`, `artefacto.cargar(ruta) -> Artefacto` (`ValueError` si la versión no es 1)
  - `config.RUTA_VARIANZA = Path("modelos/varianza.joblib")`, `config.RUTA_ROL_PREVIO = Path("modelos/rol_previo_2026.csv")`

- [ ] **Step 1: Write the failing tests** (usan el histórico real de 2023 que está en el repo)

```python
# tests/test_varianza_datos.py
from pathlib import Path

import pytest

from fantasy.ingesta import historico
from fantasy.varianza import artefacto, datos, rol

RAIZ = Path(__file__).parents[1] / "historico"


@pytest.fixture(scope="module")
def t23():
    return datos.tabla(historico.cargar_historico(RAIZ, 2023), 2023)


def test_tabla_tiene_rol_sin_fuga_y_equipo(t23):
    assert set(rol.TODOS) <= set(t23.columns)
    assert (t23.fuente_max < t23.semana).all()
    assert t23.semana.min() == 1 and t23.semana.max() == 17
    c = datos.para_construir(t23)
    assert c.relevante.all() and c.semana.between(3, 17).all()
    assert c.equipo.notna().mean() > 0.9
    assert c[rol.TODOS].notna().all().all()


def test_artefacto_ida_y_vuelta(t23, tmp_path):
    c = datos.para_construir(t23)
    art = artefacto.construir(c, c, {"QB": 1, "RB": 2, "WR": 2, "TE": 1})
    ruta = tmp_path / "v.joblib"
    artefacto.guardar(art, ruta)
    otra = artefacto.cargar(ruta)
    assert otra.k == art.k and otra.temporadas == (2023,)
    assert len(otra.colecciones.muestra("WR", 1, 2)) >= 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_datos.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/datos.py
"""Tabla jugador-semana de una temporada para la varianza: proyección de ESPN, puntos reales,
equipo NFL (último conocido antes de la semana) y rol previo."""

import io

import pandas as pd

from fantasy.ingesta import nflverse
from fantasy.modelo import variables
from fantasy.modelo.evaluar import relevantes
from fantasy.varianza import rol

SEMANAS = range(3, 18)


def tabla(crudos: dict, temporada: int, previo: pd.DataFrame | None = None) -> pd.DataFrame:
    base = variables.desde_crudos(crudos, temporada, semanas=list(range(1, 18)))
    base = base[base.proy_espn > 0][["jugador_id", "temporada", "semana", "pos",
                                     "proy_espn", "real"]]
    marca = relevantes(base)[["jugador_id", "semana"]].assign(relevante=True)
    base = base.merge(marca, on=["jugador_id", "semana"], how="left")
    base["relevante"] = base.relevante.fillna(False).astype(bool)
    leer = {n: pd.read_csv(io.StringIO(crudos[n]), low_memory=False)
            for n in ("semanal", "jugadores")}
    uso = nflverse.uso_extendido(leer["semanal"], leer["jugadores"])
    eq = variables.equipo_previo(uso, sorted(base.semana.unique()))
    base = base.merge(eq, on=["jugador_id", "semana"], how="left")
    r = rol.previo_a(rol.leer(crudos), base[["jugador_id", "semana", "pos"]], previo)
    return base.merge(r.drop(columns="pos"), on=["jugador_id", "semana"], how="left")


def para_construir(t: pd.DataFrame) -> pd.DataFrame:
    return t[t.relevante & t.semana.isin(SEMANAS)]
```

```python
# src/fantasy/varianza/artefacto.py
"""Todo lo que la simulación necesita, congelado en un archivo (con huella para el sellado)."""

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from fantasy.varianza import errores
from fantasy.varianza.errores import Colecciones
from fantasy.varianza.grupos import GruposPos, ajustar, asignar

VERSION = 1


@dataclass
class Artefacto:
    version: int
    k: dict[str, int]
    grupos: dict[str, GruposPos]
    colecciones: Colecciones
    correlaciones: dict[tuple[str, str], float]
    temporadas: tuple[int, ...]


def construir(filas_grupos: pd.DataFrame, filas_colecciones: pd.DataFrame,
              k: dict[str, int], semilla: int = 0) -> Artefacto:
    """Grupos formados con `filas_grupos`; colecciones y correlaciones con
    `filas_colecciones` (ambas: filas relevantes de semanas 3–17)."""
    grupos = {pos: ajustar(filas_grupos, pos, n, semilla) for pos, n in k.items()}
    f = filas_colecciones.assign(grupo=asignar(grupos, filas_colecciones))
    col = errores.construir(f)
    corr = errores.correlaciones(f.assign(error=f.real - f.proy_espn))
    temporadas = tuple(sorted(int(t) for t in f.temporada.unique()))
    return Artefacto(VERSION, dict(k), grupos, col, corr, temporadas)


def guardar(art: Artefacto, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, ruta)


def cargar(ruta: Path) -> Artefacto:
    art = joblib.load(ruta)
    if getattr(art, "version", None) != VERSION:
        raise ValueError(f"el artefacto de varianza en {ruta} es de otra versión")
    return art
```

En `src/fantasy/config.py` añade al final:

```python
RUTA_VARIANZA = Path("modelos/varianza.joblib")
RUTA_ROL_PREVIO = Path("modelos/rol_previo_2026.csv")  # lo genera varianza-validar
```

En `src/fantasy/cli.py`, dentro de `_parser()` antes de `return p`:

```python
    vc = sub.add_parser("varianza-construir",
                        help="grupos por rol (k con 2024) y colecciones de errores 2023–2024")
    vc.add_argument("--raiz", type=Path, default=Path("historico"))
    vc.add_argument("--salida", type=Path, default=Path("modelos/varianza.joblib"))
```

y en `main`, antes de `if a.comando == "validar-en-vivo":`:

```python
    if a.comando == "varianza-construir":
        from fantasy.ingesta import historico
        from fantasy.varianza import artefacto, datos, grupos, rol
        c23, c24 = (historico.cargar_historico(a.raiz, t) for t in (2023, 2024))
        t23 = datos.tabla(c23, 2023)
        t24 = datos.tabla(c24, 2024, previo=rol.promedio_temporada(rol.leer(c23)))
        f23, f24 = datos.para_construir(t23), datos.para_construir(t24)
        k, tabla_crps = grupos.elegir_k(f23, f24)
        print(tabla_crps.to_string(index=False))
        print(f"k elegido: {k}")
        art = artefacto.construir(f23, pd.concat([f23, f24], ignore_index=True), k)
        artefacto.guardar(art, a.salida)
        print(f"Artefacto guardado en {a.salida}")
        return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_datos.py -q && uv run ruff check src tests`
Expected: 2 passed.

- [ ] **Step 5: Construir el artefacto real y anotar el resultado**

Run: `uv run fantasy varianza-construir`
Expected: tabla `pos k crps` (20 filas), `k elegido: {...}` y el archivo `modelos/varianza.joblib`. **Copia la tabla y el `k` elegido** al mensaje del commit y al resumen para Mario (es un resultado: dice si los grupos por rol ayudan o si quedó `k = 1`).

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/varianza/datos.py src/fantasy/varianza/artefacto.py src/fantasy/config.py src/fantasy/cli.py tests/test_varianza_datos.py modelos/varianza.joblib
git commit -m "feat(varianza): tabla histórica, artefacto y fantasy varianza-construir

k elegido: <pegar>"
```

---

### Task 5: Monte Carlo y probabilidad de ganar

**Files:**
- Create: `src/fantasy/varianza/simular.py`, `tests/varianza_util.py`
- Test: `tests/test_varianza_simular.py`

**Interfaces:**
- Consumes: `Artefacto`, `Colecciones`, `errores.rho`.
- Produces:
  - `simular.N_SIM = 10_000`
  - `simular.simular(jug, art, n=N_SIM, semilla=0) -> np.ndarray (n × len(jug))`; `jug`: `pos, proy, p_jugar, grupo, equipo, real_fijo` (NaN si falta jugar; `equipo` puede ser NaN)
  - `simular.p_ganar(puntos, cols_a: list[int], cols_b: list[int]) -> float` (empate = ½)
  - `simular.dispersion(puntos, col: int) -> float` (percentil 90 − percentil 10)
  - `tests/varianza_util.art_prueba(sd=8.0, corr=None, n=5000, semilla=0) -> Artefacto` (k = 1, errores normales)

- [ ] **Step 1: Write the helper and the failing tests**

```python
# tests/varianza_util.py
import numpy as np

from fantasy.varianza.artefacto import VERSION, Artefacto
from fantasy.varianza.errores import POS, Colecciones


def art_prueba(sd=8.0, corr=None, n=5000, semilla=0) -> Artefacto:
    rng = np.random.default_rng(semilla)
    muestras = {(p,): np.sort(rng.normal(0, sd, n)) if sd else np.zeros(n) for p in POS}
    col = Colecciones({p: (5.0, 12.0) for p in POS}, muestras, {p: -10.0 for p in POS})
    return Artefacto(VERSION, {p: 1 for p in POS}, {}, col, corr or {}, (2023,))
```

```python
# tests/test_varianza_simular.py
import numpy as np
import pandas as pd
import pytest

from fantasy.varianza import simular
from tests.varianza_util import art_prueba


def _jug(proys, pos="WR", equipo=None, real=np.nan, p_jugar=1.0):
    return pd.DataFrame({"pos": pos, "proy": proys, "p_jugar": p_jugar, "grupo": 0,
                         "equipo": equipo, "real_fijo": real})


def test_sin_dispersion_gana_el_que_proyecta_mas():
    pts = simular.simular(_jug([20.0, 10.0]), art_prueba(sd=0), n=1000)
    assert simular.p_ganar(pts, [0], [1]) == 1.0
    assert simular.p_ganar(pts, [1], [0]) == 0.0


def test_equipos_identicos_dan_mitad():
    pts = simular.simular(_jug([15.0] * 4), art_prueba(), n=20_000)
    assert simular.p_ganar(pts, [0, 1], [2, 3]) == pytest.approx(0.5, abs=0.02)


def test_jugados_usan_sus_puntos_reales():
    jug = _jug([15.0, 15.0]).assign(real_fijo=[30.0, np.nan])
    pts = simular.simular(jug, art_prueba(), n=500)
    assert (pts[:, 0] == 30.0).all()


def test_no_juega_hace_cero_y_proyeccion_cero_tambien():
    jug = _jug([15.0, 0.0]).assign(p_jugar=[0.0, 1.0])
    pts = simular.simular(jug, art_prueba(), n=500)
    assert (pts == 0.0).all()


def test_companeros_correlacionados():
    jug = _jug([15.0, 15.0, 15.0], pos=["QB", "WR", "WR"], equipo=["DET", "DET", "CHI"])
    pts = simular.simular(jug, art_prueba(corr={("QB", "WR"): 0.5}), n=20_000)
    assert np.corrcoef(pts[:, 0], pts[:, 1])[0, 1] == pytest.approx(0.5, abs=0.05)
    assert abs(np.corrcoef(pts[:, 0], pts[:, 2])[0, 1]) < 0.03


def test_piso_y_dispersion():
    pts = simular.simular(_jug([1.0]), art_prueba(sd=20.0), n=5000)
    assert pts.min() >= -10.0
    assert simular.dispersion(pts, 0) > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_simular.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/simular.py
"""Monte Carlo de una semana: a cada jugador se le suma un error real de ESPN de su tipo
(grupo y tramo); los compañeros comparten suerte mediante una cópula gaussiana."""

import numpy as np
import pandas as pd
from scipy.special import ndtr

from fantasy.varianza import errores
from fantasy.varianza.artefacto import Artefacto

N_SIM = 10_000


def _matriz(pos: list[str], equipos: list, corr: dict) -> np.ndarray:
    m = len(pos)
    R = np.eye(m)
    for i in range(m):
        for j in range(i + 1, m):
            if equipos[i] is not None and equipos[i] == equipos[j]:
                R[i, j] = R[j, i] = errores.rho(corr, pos[i], pos[j])
    w, v = np.linalg.eigh(R)
    if w.min() < 1e-6:  # la más cercana definida positiva
        R = (v * np.clip(w, 1e-6, None)) @ v.T
        d = np.sqrt(np.diag(R))
        R = R / np.outer(d, d)
    return R


def simular(jug: pd.DataFrame, art: Artefacto, n: int = N_SIM, semilla: int = 0) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    m = len(jug)
    equipos = [None if pd.isna(e) else e for e in jug.equipo]
    L = np.linalg.cholesky(_matriz(list(jug.pos), equipos, art.correlaciones))
    u = ndtr(rng.standard_normal((n, m)) @ L.T)
    juega = rng.random((n, m)) < jug.p_jugar.to_numpy(float)
    col = art.colecciones
    salida = np.zeros((n, m))
    for i, f in enumerate(jug.itertuples(index=False)):
        if not pd.isna(f.real_fijo):
            salida[:, i] = f.real_fijo
            continue
        if f.proy <= 0:
            continue  # descansa o no lo proyectan: 0, no "0 + error"
        mu = col.muestra(f.pos, int(f.grupo), col.tramo(f.pos, f.proy))
        idx = np.minimum((u[:, i] * len(mu)).astype(int), len(mu) - 1)
        pts = np.maximum(f.proy + mu[idx], col.piso[f.pos])
        salida[:, i] = np.where(juega[:, i], pts, 0.0)
    return salida


def p_ganar(puntos: np.ndarray, cols_a: list[int], cols_b: list[int]) -> float:
    a = puntos[:, cols_a].sum(axis=1)
    b = puntos[:, cols_b].sum(axis=1)
    return float(((a > b) + 0.5 * (a == b)).mean())


def dispersion(puntos: np.ndarray, col: int) -> float:
    q10, q90 = np.quantile(puntos[:, col], [0.1, 0.9])
    return float(q90 - q10)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_simular.py -q && uv run ruff check src tests`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/varianza/simular.py tests/varianza_util.py tests/test_varianza_simular.py
git commit -m "feat(varianza): Monte Carlo con cópula y probabilidad de ganar"
```

---

### Task 6: Alineaciones candidatas y elección por P(ganar)

**Files:**
- Create: `src/fantasy/varianza/alinear.py`
- Test: `tests/test_varianza_alinear.py`

**Interfaces:**
- Consumes: `decision.alineacion.{CUPOS, FLEX_POS, TITULARES, Alineacion, optima}`.
- Produces:
  - `alinear.MARGEN = 10.0`, `alinear.UMBRAL = 0.01`
  - `alinear.candidatas(t, margen=MARGEN) -> list[Alineacion]`; `t` con `jugador_id, pos, esperado, bloqueado, slot`; `[0]` es `optima(t)`; sin repetidos (por conjunto de jugadores).
  - `alinear.elegir(p: list[float], umbral=UMBRAL) -> int` (índice en `candidatas`; 0 si ninguna supera a la óptima por ≥ umbral).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_alinear.py
import pandas as pd

from fantasy.decision.alineacion import optima
from fantasy.varianza import alinear


def _t():
    filas = [(1, "QB", 20), (2, "QB", 12), (3, "RB", 18), (4, "RB", 15), (5, "RB", 9),
             (6, "WR", 17), (7, "WR", 14), (8, "WR", 13), (9, "WR", 4), (10, "TE", 10),
             (11, "TE", 7)]
    return pd.DataFrame(filas, columns=["jugador_id", "pos", "esperado"]).assign(
        bloqueado=False, slot="BANCA")


def test_la_primera_es_la_optima_y_ninguna_se_aleja_mas_del_margen():
    t = _t()
    c = alinear.candidatas(t)
    assert c[0].ids() == optima(t).ids()
    assert all(x.esperado >= c[0].esperado - alinear.MARGEN for x in c)
    assert len({frozenset(x.ids()) for x in c}) == len(c)
    assert len(c) > 5
    assert all(len(x.slots) == 7 for x in c)


def test_bloqueados_quedan_fijos():
    t = _t()
    t.loc[t.jugador_id == 2, ["bloqueado", "slot"]] = [True, "QB"]  # QB malo ya jugando
    t.loc[t.jugador_id == 8, ["bloqueado", "slot"]] = [True, "BANCA"]  # en banca y ya jugó
    for x in alinear.candidatas(t):
        assert 2 in x.ids() and 1 not in x.ids() and 8 not in x.ids()


def test_elegir_exige_un_punto_porcentual():
    assert alinear.elegir([0.60, 0.605, 0.58]) == 0
    assert alinear.elegir([0.60, 0.62, 0.61]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_alinear.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/alinear.py
"""Alineaciones cercanas a la óptima por puntos esperados y elección por P(ganar)."""

import itertools

import pandas as pd

from fantasy.decision.alineacion import CUPOS, FLEX_POS, TITULARES, Alineacion, optima

MARGEN = 10.0  # nunca más de 10 puntos esperados por debajo de la óptima
UMBRAL = 0.01  # cambiar solo por al menos 1 punto porcentual de P(ganar)
_ORDEN = {s: i for i, s in enumerate(TITULARES)}


def _alineacion(elegidos: list[tuple[str, int]], esp: dict[int, float]) -> Alineacion:
    slots = tuple(sorted(elegidos, key=lambda x: _ORDEN[x[0]]))
    return Alineacion(slots, float(sum(esp[j] for _, j in slots)))


def candidatas(t: pd.DataFrame, margen: float = MARGEN) -> list[Alineacion]:
    mejor = optima(t)
    esp = dict(zip(t.jugador_id.astype(int), t.esperado.astype(float), strict=True))
    fijos_df = t[t.bloqueado & t.slot.isin(TITULARES)]
    fijos = [(s, int(j)) for s, j in zip(fijos_df.slot, fijos_df.jugador_id, strict=True)]
    libres = t[~t.bloqueado]
    por_pos = {p: [int(j) for j in libres.loc[libres.pos == p, "jugador_id"]] for p in CUPOS}
    faltan = {p: max(n - sum(1 for s, _ in fijos if s == p), 0) for p, n in CUPOS.items()}
    falta_flex = not any(s == "FLEX" for s, _ in fijos)
    salida, vistos = [mejor], {frozenset(mejor.ids())}
    for eleccion in itertools.product(*(itertools.combinations(por_pos[p], faltan[p])
                                        for p in CUPOS)):
        base = fijos + [(p, j) for p, js in zip(CUPOS, eleccion, strict=True) for j in js]
        usados = {j for _, j in base}
        flex = ([j for p in FLEX_POS for j in por_pos[p] if j not in usados]
                if falta_flex else [None])
        for fx in flex:
            el = base + ([("FLEX", fx)] if fx is not None else [])
            clave = frozenset(j for _, j in el)
            if clave in vistos:
                continue
            al = _alineacion(el, esp)
            if al.esperado >= mejor.esperado - margen:
                vistos.add(clave)
                salida.append(al)
    return salida


def elegir(p: list[float], umbral: float = UMBRAL) -> int:
    i = max(range(len(p)), key=lambda k: p[k])
    return i if p[i] - p[0] >= umbral else 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_alinear.py -q && uv run ruff check src tests`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/varianza/alinear.py tests/test_varianza_alinear.py
git commit -m "feat(varianza): alineaciones candidatas y elección por probabilidad de ganar"
```

- [ ] **Step 6: Revisión de mitad de fase** — lanzar un subagente revisor sobre `git diff main...HEAD -- src/fantasy/varianza tests` con la spec y este plan; corregir lo confirmado antes de seguir.

---

### Task 7: Ligas simuladas

**Files:**
- Create: `src/fantasy/varianza/ligas.py`
- Test: `tests/test_varianza_ligas.py`

**Interfaces:**
- Consumes: `optima`, `alinear.candidatas/elegir`, `simular.simular/p_ganar`, `grupos.asignar`, `Artefacto`, tabla de `datos.tabla`.
- Produces:
  - `ligas.draft(valores: DataFrame[jugador_id,pos,valor], rng) -> list[list[int]]` (8 × 14)
  - `ligas.temporada(t, art, *, n_ligas=200, semanas=range(3,18), n_sim=N_SIM, semilla=0, margen=MARGEN) -> DataFrame[liga, semana, equipo, p, p_optima, gana_pg, gana_esp, cambia]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_ligas.py
import numpy as np
import pandas as pd

from fantasy.varianza import ligas
from tests.varianza_util import art_prueba


def _pool(rng, n=200):
    pos = rng.choice(["QB", "RB", "WR", "TE"], n, p=[0.15, 0.35, 0.35, 0.15])
    return pd.DataFrame({"jugador_id": np.arange(n), "pos": pos, "valor": rng.uniform(1, 25, n)})


def test_draft_respeta_topes_y_titulares():
    rng = np.random.default_rng(0)
    equipos = ligas.draft(_pool(rng), rng)
    pos = _pool(np.random.default_rng(0)).set_index("jugador_id").pos
    assert len(equipos) == 8 and all(len(e) == 14 for e in equipos)
    assert len({j for e in equipos for j in e}) == 8 * 14
    for e in equipos:
        c = pos.loc[e].value_counts()
        assert c.get("QB", 0) <= 3 and c.get("RB", 0) <= 6 and c.get("TE", 0) <= 3
        assert c.get("QB", 0) >= 1 and c.get("RB", 0) >= 2 and c.get("WR", 0) >= 2
        assert c.get("TE", 0) >= 1


def _temporada_falsa(rng):
    pool = _pool(rng)
    filas = []
    for w in range(1, 6):
        for r in pool.itertuples():
            filas.append({"jugador_id": r.jugador_id, "semana": w, "pos": r.pos,
                          "proy_espn": r.valor, "real": r.valor + rng.normal(0, 8),
                          "equipo": f"T{r.jugador_id % 32}", "rush_share": 0.0,
                          "snap_pct": 0.8, "target_share": 0.1, "rel_depth": 1.0,
                          "eficiencia": 1.0})
    return pd.DataFrame(filas)


def test_temporada_produce_un_resultado_por_equipo_y_semana():
    rng = np.random.default_rng(1)
    res = ligas.temporada(_temporada_falsa(rng), art_prueba(), n_ligas=2,
                          semanas=range(3, 5), n_sim=500)
    assert len(res) == 2 * 2 * 8
    assert res.p.between(0, 1).all()
    assert set(res.gana_pg.unique()) <= {0.0, 0.5, 1.0}
    assert (res.gana_pg[~res.cambia] == res.gana_esp[~res.cambia]).all()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_ligas.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement**

```python
# src/fantasy/varianza/ligas.py
"""Ligas simuladas para comparar dos formas de alinear con los puntos reales de una temporada:
por puntos esperados (`optima`) o por probabilidad de ganar."""

import numpy as np
import pandas as pd

from fantasy.decision.alineacion import optima
from fantasy.varianza import alinear, simular
from fantasy.varianza.grupos import asignar

EQUIPOS = 8
RONDAS = 14
RUIDO = 0.15
POOL = 200
TOPE = {"QB": 3, "RB": 6, "WR": 6, "TE": 3}
MINIMOS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}


def draft(valores: pd.DataFrame, rng: np.random.Generator) -> list[list[int]]:
    v = valores.assign(valor=valores.valor * (1 + rng.normal(0, RUIDO, len(valores))))
    v = v.sort_values("valor", ascending=False)
    disponibles = list(zip(v.jugador_id.astype(int), v.pos, strict=True))
    equipos = [[] for _ in range(EQUIPOS)]
    conteo = [dict.fromkeys(TOPE, 0) for _ in range(EQUIPOS)]
    for r in range(RONDAS):
        orden = range(EQUIPOS) if r % 2 == 0 else range(EQUIPOS - 1, -1, -1)
        for e in orden:
            faltan = {p: max(MINIMOS[p] - conteo[e][p], 0) for p in TOPE}
            obligado = sum(faltan.values()) >= RONDAS - r
            for i, (j, p) in enumerate(disponibles):
                if conteo[e][p] >= TOPE[p] or (obligado and faltan[p] == 0):
                    continue
                equipos[e].append(j)
                conteo[e][p] += 1
                disponibles.pop(i)
                break
    return equipos


def _tabla_equipo(jug: pd.DataFrame, ids: list[int]) -> pd.DataFrame:
    return jug[jug.jugador_id.isin(ids)].assign(bloqueado=False, slot="BANCA")


def temporada(t: pd.DataFrame, art, *, n_ligas: int = 200, semanas=range(3, 18),
              n_sim: int = simular.N_SIM, semilla: int = 0,
              margen: float = alinear.MARGEN) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    t = t.assign(grupo=asignar(art.grupos, t))
    valores = (t[t.semana == 1].nlargest(POOL, "proy_espn")[["jugador_id", "pos", "proy_espn"]]
               .rename(columns={"proy_espn": "valor"}))
    pos = valores.set_index("jugador_id").pos
    por_semana = {w: t[t.semana == w].drop_duplicates("jugador_id").set_index("jugador_id")
                  for w in semanas}
    filas = []
    for liga in range(n_ligas):
        equipos = draft(valores, rng)
        todos = [j for e in equipos for j in e]
        for w in semanas:
            s = por_semana[w].reindex(todos)
            jug = pd.DataFrame({
                "jugador_id": todos, "pos": pos.loc[todos].to_numpy(),
                "proy": s.proy_espn.fillna(0.0).to_numpy(), "p_jugar": 1.0,
                "grupo": s.grupo.fillna(0).astype(int).to_numpy(),
                "equipo": s.equipo.to_numpy(), "real_fijo": np.nan,
                "real": s.real.fillna(0.0).to_numpy()})
            jug["esperado"] = jug.proy
            pts = simular.simular(jug, art, n_sim, semilla=int(rng.integers(2**31)))
            col = {j: i for i, j in enumerate(todos)}
            real = jug.real.to_numpy()
            optimas = [optima(_tabla_equipo(jug, e)) for e in equipos]
            orden = rng.permutation(EQUIPOS)
            for a, b in zip(orden[::2], orden[1::2], strict=True):
                for yo, rival in ((a, b), (b, a)):
                    cols_r = [col[j] for j in optimas[rival].ids()]
                    pts_rival = real[cols_r].sum()
                    cands = alinear.candidatas(_tabla_equipo(jug, equipos[yo]), margen)
                    p = [simular.p_ganar(pts, [col[j] for j in c.ids()], cols_r) for c in cands]
                    i = alinear.elegir(p)

                    def resultado(al, pts_rival=pts_rival):
                        x = real[[col[j] for j in al.ids()]].sum()
                        return 1.0 if x > pts_rival else 0.5 if x == pts_rival else 0.0

                    filas.append({"liga": liga, "semana": w, "equipo": int(yo), "p": p[i],
                                  "p_optima": p[0], "gana_pg": resultado(cands[i]),
                                  "gana_esp": resultado(cands[0]), "cambia": i != 0})
    return pd.DataFrame(filas)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_ligas.py -q && uv run ruff check src tests`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/varianza/ligas.py tests/test_varianza_ligas.py
git commit -m "feat(varianza): ligas simuladas para comparar las dos formas de alinear"
```

---

### Task 8: Criterio, estado, sellado y comandos `varianza-ensayo` / `-registrar` / `-validar`

**Files:**
- Create: `src/fantasy/varianza/validar.py`
- Modify: `src/fantasy/cli.py`
- Test: `tests/test_varianza_validar.py`

**Interfaces:**
- Consumes: `ligas.temporada`, `artefacto.cargar`, `modelo.estado.huella` (solo import), `datos.tabla`, `rol.*`, `historico.bajar_espn_historico`, `nflverse.bajar_nflverse`.
- Produces:
  - `validar.RESULTADO = "2025_pganar.json"`, `validar.REGISTRO = "registro_pganar.json"`
  - `validar.criterio(res, semilla=0, n_boot=10_000) -> dict{delta, ic95, paso_1, paso_2, calibracion, enfrentamientos, cambios}`
  - `validar.estado(raiz: Path, ruta_artefacto: Path) -> dict{existe, paso_1, paso_2}`
  - `validar.validar_sellado(registro, ruta_artefacto, obtener_2025, destino, *, git_limpio, varianza_igual) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_validar.py
import json

import numpy as np
import pandas as pd
import pytest

from fantasy.modelo.estado import huella
from fantasy.varianza import validar


def _res(delta_por_semana, p=0.7, real=0.7, n=300, semilla=0):
    rng = np.random.default_rng(semilla)
    filas = []
    for w, d in delta_por_semana.items():
        gana = (rng.random(n) < real).astype(float)
        esp = gana.copy()
        k = int(abs(d) * n)
        esp[:k] = gana[:k] - np.sign(d)  # en k casos la otra forma pierde (o gana)
        filas.append(pd.DataFrame({"semana": w, "p": p, "gana_pg": gana,
                                   "gana_esp": esp.clip(0, 1), "cambia": True}))
    return pd.concat(filas, ignore_index=True)


def test_pasa_las_dos():
    r = validar.criterio(_res({w: 0.05 for w in range(3, 18)}), n_boot=2000)
    assert r["paso_1"] and r["paso_2"] and r["ic95"][0] > 0


def test_falla_1_si_no_gana_mas():
    r = validar.criterio(_res({w: 0.0 for w in range(3, 18)}), n_boot=2000)
    assert not r["paso_1"] and r["paso_2"]


def test_falla_2_si_los_porcentajes_no_son_creibles():
    r = validar.criterio(_res({w: 0.05 for w in range(3, 18)}, p=0.9, real=0.6), n_boot=2000)
    assert not r["paso_2"]


def _art(tmp_path):
    ruta = tmp_path / "varianza.joblib"
    ruta.write_bytes(b"artefacto")
    return ruta


def test_estado_segun_archivo_y_huella(tmp_path):
    ruta = _art(tmp_path)
    assert validar.estado(tmp_path, ruta) == {"existe": False, "paso_1": False, "paso_2": False}
    (tmp_path / validar.RESULTADO).write_text(json.dumps(
        {"paso_1": True, "paso_2": True, "sha256": huella(ruta)}), encoding="utf-8")
    assert validar.estado(tmp_path, ruta) == {"existe": True, "paso_1": True, "paso_2": True}
    ruta.write_bytes(b"otro artefacto")  # alguien lo regeneró
    assert validar.estado(tmp_path, ruta) == {"existe": True, "paso_1": False, "paso_2": False}


def test_sellado_se_niega(tmp_path):
    ruta = _art(tmp_path)
    reg = {"commit": "abc", "sha256": huella(ruta), "ligas": 1, "n_sim": 10, "semilla": 0}
    destino = tmp_path / validar.RESULTADO
    nunca = lambda: pytest.fail("no debe tocar 2025")  # noqa: E731
    casos = [
        dict(git_limpio=lambda: False, varianza_igual=lambda c: True),
        dict(git_limpio=lambda: True, varianza_igual=lambda c: False),
    ]
    for kw in casos:
        with pytest.raises(RuntimeError):
            validar.validar_sellado(reg, ruta, nunca, destino, **kw)
    with pytest.raises(RuntimeError, match="huella"):
        validar.validar_sellado({**reg, "sha256": "x"}, ruta, nunca, destino,
                                git_limpio=lambda: True, varianza_igual=lambda c: True)
    destino.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ya se corrió"):
        validar.validar_sellado(reg, ruta, nunca, destino,
                                git_limpio=lambda: True, varianza_igual=lambda c: True)


def test_cli_validar_sin_bandera_no_corre():
    from fantasy.cli import main
    assert main(["varianza-validar"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_validar.py -q`
Expected: FAIL (`ImportError`)

- [ ] **Step 3: Implement `validar.py`**

```python
# src/fantasy/varianza/validar.py
"""Criterio de la probabilidad de ganar (decisión 25) y su corrida única sobre 2025."""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy.modelo.estado import huella
from fantasy.varianza import artefacto, ligas

RESULTADO = "2025_pganar.json"
REGISTRO = "registro_pganar.json"
N_BOOT = 10_000
MIN_TRAMO = 100
TOLERANCIA = 0.05


def criterio(res: pd.DataFrame, semilla: int = 0, n_boot: int = N_BOOT) -> dict:
    d = res.assign(delta=res.gana_pg - res.gana_esp)
    por_semana = d.groupby("semana").delta.agg(["sum", "size"])
    rng = np.random.default_rng(semilla)
    idx = rng.integers(0, len(por_semana), size=(n_boot, len(por_semana)))
    sumas, tamanos = por_semana["sum"].to_numpy(), por_semana["size"].to_numpy()
    boot = sumas[idx].sum(axis=1) / tamanos[idx].sum(axis=1)
    bajo, alto = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    delta = float(d.delta.mean())
    tramo = np.minimum((d.p * 10).astype(int), 9)
    calibracion = [{"tramo": f"{10 * k}-{10 * k + 10}%", "n": int(len(g)),
                    "pronostico": float(g.p.mean()), "real": float(g.gana_pg.mean())}
                   for k, g in d.groupby(tramo)]
    evaluables = [c for c in calibracion if c["n"] >= MIN_TRAMO]
    paso_2 = bool(evaluables) and all(abs(c["real"] - c["pronostico"]) < TOLERANCIA
                                      for c in evaluables)
    return {"delta": delta, "ic95": [bajo, alto], "paso_1": bool(delta > 0 and bajo > 0),
            "paso_2": paso_2, "calibracion": calibracion, "enfrentamientos": int(len(d)),
            "cambios": int(d.cambia.sum())}


def estado(raiz: Path, ruta_artefacto: Path) -> dict:
    ruta = raiz / RESULTADO
    if not ruta.exists():
        return {"existe": False, "paso_1": False, "paso_2": False}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"existe": True, "paso_1": False, "paso_2": False}
    if not ruta_artefacto.exists() or huella(ruta_artefacto) != datos.get("sha256"):
        return {"existe": True, "paso_1": False, "paso_2": False}
    return {"existe": True, "paso_1": datos.get("paso_1") is True,
            "paso_2": datos.get("paso_2") is True}


def validar_sellado(registro: dict, ruta_artefacto: Path, obtener_2025, destino: Path, *,
                    git_limpio, varianza_igual) -> dict:
    """Corre una sola vez. Todas las verificaciones van antes de tocar 2025."""
    if destino.exists():
        raise RuntimeError(f"la validación de la varianza ya se corrió: {destino}")
    if not git_limpio():
        raise RuntimeError("el repo tiene cambios sin commit: congela todo antes de validar")
    if not varianza_igual(registro["commit"]):
        raise RuntimeError("src/fantasy/varianza cambió desde el registro: vuelve a registrar")
    if huella(ruta_artefacto) != registro["sha256"]:
        raise RuntimeError("la huella del artefacto no coincide con el registro")
    art = artefacto.cargar(ruta_artefacto)
    res = ligas.temporada(obtener_2025(), art, n_ligas=registro["ligas"],
                          n_sim=registro["n_sim"], semilla=registro["semilla"])
    salida = {**criterio(res, semilla=registro["semilla"]), "fuente": "2025 sellada",
              "sha256": registro["sha256"], "k": registro.get("k"),
              "fecha": datetime.now(UTC).isoformat()}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    return salida
```

- [ ] **Step 4: Comandos en `cli.py`**

En `_parser()`, antes de `return p`:

```python
    ve = sub.add_parser("varianza-ensayo", help="la prueba de ligas simuladas sobre 2024")
    ve.add_argument("--raiz", type=Path, default=Path("historico"))
    ve.add_argument("--artefacto", type=Path, default=Path("modelos/varianza.joblib"))
    ve.add_argument("--ligas", type=int, default=200)
    vr = sub.add_parser("varianza-registrar", help="congela el registro antes del sellado")
    vr.add_argument("--artefacto", type=Path, default=Path("modelos/varianza.joblib"))
    vs = sub.add_parser("varianza-validar",
                        help="corrida única sobre 2025 (requiere --sellado-final)")
    vs.add_argument("--sellado-final", action="store_true")
    vs.add_argument("--raiz", type=Path, default=Path("historico"))
    vs.add_argument("--artefacto", type=Path, default=Path("modelos/varianza.joblib"))
```

En `main`, junto al bloque de `varianza-construir`:

```python
    if a.comando == "varianza-ensayo":
        import json

        from fantasy.ingesta import historico
        from fantasy.varianza import artefacto, datos, ligas, rol, validar
        c23, c24 = (historico.cargar_historico(a.raiz, t) for t in (2023, 2024))
        f23 = datos.para_construir(datos.tabla(c23, 2023))
        t24 = datos.tabla(c24, 2024, previo=rol.promedio_temporada(rol.leer(c23)))
        # Mismo k que el artefacto, pero colecciones solo con 2023: 2024 queda fuera de muestra.
        art = artefacto.construir(f23, f23, artefacto.cargar(a.artefacto).k)
        res = validar.criterio(ligas.temporada(t24, art, n_ligas=a.ligas))
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0
    if a.comando == "varianza-registrar":
        import json
        import subprocess

        from fantasy.modelo.estado import huella
        from fantasy.varianza import artefacto
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                check=False, text=True).stdout.strip()
        registro = {"commit": commit, "sha256": huella(a.artefacto),
                    "artefacto": a.artefacto.as_posix(), "k": artefacto.cargar(a.artefacto).k,
                    "ligas": 200, "n_sim": 10_000, "semilla": 0, "margen": 10.0,
                    "fecha": datetime.now(UTC).isoformat()}
        destino = RUTA_VALIDACION / "registro_pganar.json"
        destino.write_text(json.dumps(registro, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Registro escrito en {destino}. Haz commit antes de validar.")
        return 0
    if a.comando == "varianza-validar":
        if not a.sellado_final:
            print("La validación de la varianza corre una sola vez sobre 2025 y requiere el "
                  "visto bueno de Mario. Repite con --sellado-final.", file=sys.stderr)
            return 2
        import json
        import subprocess

        from fantasy.config import RUTA_ROL_PREVIO
        from fantasy.ingesta import historico
        from fantasy.varianza import datos, rol, validar
        registro = json.loads((RUTA_VALIDACION / "registro_pganar.json")
                              .read_text(encoding="utf-8"))
        guardado = {}

        def obtener_2025():
            c24 = historico.cargar_historico(a.raiz, 2024)
            crudos = {"proyecciones": historico.bajar_espn_historico(2025,
                                                                     permitir_sellada=True)}
            crudos |= bajar_nflverse(2025)
            guardado["crudos"] = crudos
            return datos.tabla(crudos, 2025, previo=rol.promedio_temporada(rol.leer(c24)))

        def git(*args):
            return subprocess.run(["git", *args], capture_output=True, text=True, check=False)

        def git_limpio():
            r = git("status", "--porcelain")
            return r.returncode == 0 and r.stdout.strip() == ""

        def varianza_igual(commit):
            return git("diff", "--quiet", commit, "HEAD", "--",
                       "src/fantasy/varianza").returncode == 0

        res = validar.validar_sellado(registro, a.artefacto, obtener_2025,
                                      RUTA_VALIDACION / validar.RESULTADO,
                                      git_limpio=git_limpio, varianza_igual=varianza_igual)
        # El "año anterior" del rol en vivo de 2026.
        rol.promedio_temporada(rol.leer(guardado["crudos"])).to_csv(RUTA_ROL_PREVIO,
                                                                     index=False)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_varianza_validar.py -q && uv run ruff check src tests`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/varianza/validar.py src/fantasy/cli.py tests/test_varianza_validar.py
git commit -m "feat(varianza): criterio, estado, sellado y comandos de ensayo/registro/validación"
```

- [ ] **Step 7: Ensayo sobre 2024 (desarrollo, no decide)**

Run: `uv run fantasy varianza-ensayo --ligas 20` (rápido, para ver que corre y medir el tiempo); luego `uv run fantasy varianza-ensayo` (200 ligas; correr en segundo plano si tarda más de 2 min).
Expected: JSON con `delta`, `ic95`, `paso_1`, `paso_2`, `calibracion`. **Anotar el resultado para Mario.** Si el ensayo muestra un error de código (p. ej. calibración absurda por un bug), corregir y volver a la Task correspondiente; **no** ajustar parámetros para "hacer pasar" 2024: los parámetros son los de la spec.

---

### Task 9: El reporte usa la probabilidad de ganar

**Files:**
- Create: `src/fantasy/varianza/en_vivo.py`
- Modify: `src/fantasy/reporte/armado.py`, `src/fantasy/reporte/plantillas/reporte.html.j2`
- Test: `tests/test_varianza_reporte.py`

**Interfaces:**
- Consumes: `tablas[semana]` de `armado` (`jugador_id, nombre, pos, proy, esperado, p_jugar, lesion, equipo_nfl_id, inicio_utc, slot, bloqueado`), `plantillas`, `espn.parsear_reales`, `espn.rival_de`, `rol.leer/previo_a`, `artefacto.cargar`, `validar.estado`, `alinear`, `simular`.
- Produces:
  - `en_vivo.tabla_rival(t, plantillas, rival_id, ahora) -> DataFrame`
  - `en_vivo.alineacion_rival(tr) -> Alineacion`
  - `@dataclass Simulacion(puntos, col: dict[int,int], cols_rival: list[int])` con `.p(al) -> float`, `.dispersion(j) -> float`
  - `en_vivo.preparar(tm, tr, al_rival, reales, rol_semana, art, n=N_SIM, semilla=0) -> Simulacion`
  - `en_vivo.elegir(sim, tm) -> tuple[Alineacion, float]` (elegida, P de la óptima)
  - `en_vivo.explicar(elegida, optima_al, p_optima, sim, nombres: dict[int,str]) -> list[str]`
  - `Reporte.p_ganar: int | None = None`, `Reporte.p_ganar_preliminar: bool = False`, `Reporte.explicaciones_pg: list[str] = []`
  - `armar(..., ruta_varianza: Path | None = None, ruta_rol_previo: Path | None = None)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_varianza_reporte.py
import json
import pathlib

import pandas as pd
import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.modelo.estado import huella
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html
from fantasy.varianza import artefacto, en_vivo, validar
from tests.varianza_util import art_prueba

VIE = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-10-02"
AHORA = pd.Timestamp("2026-10-01 23:23", tz="UTC")


@pytest.fixture(scope="module")
def crudos():
    return cargar(VIE)


def _entorno(tmp_path, paso_1, paso_2, escribir=True):
    ruta = tmp_path / "varianza.joblib"
    artefacto.guardar(art_prueba(), ruta)
    if escribir:
        (tmp_path / validar.RESULTADO).write_text(json.dumps(
            {"paso_1": paso_1, "paso_2": paso_2, "sha256": huella(ruta)}), encoding="utf-8")
    return dict(ruta_validacion=tmp_path, ruta_varianza=ruta,
                ruta_rol_previo=tmp_path / "no_existe.csv")


def _r(crudos, tmp_path, tipo="viernes", **kw):
    return armar(crudos, AHORA, tipo, 5, **_entorno(tmp_path, **kw))


def test_sin_resultado_no_cambia_nada(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=False, paso_2=False, escribir=False)
    base = armar(crudos, AHORA, "viernes", 5, ruta_validacion=tmp_path)
    assert r.p_ganar is None and r.explicaciones_pg == []
    assert [x["jugador_id"] for x in r.alineacion] == [x["jugador_id"] for x in base.alineacion]
    assert not any("probabilidad de ganar" in a.lower() for a in r.avisos)


def test_solo_creible_muestra_porcentaje_sin_cambiar_la_alineacion(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=False, paso_2=True)
    base = armar(crudos, AHORA, "viernes", 5, ruta_validacion=tmp_path / "x")
    assert 0 <= r.p_ganar <= 100
    assert [x["jugador_id"] for x in r.alineacion] == [x["jugador_id"] for x in base.alineacion]
    assert "Probabilidad de ganar" in generar_html(r)


def test_pasa_las_dos_puede_alinear_y_no_se_aleja_10_puntos(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=True, paso_2=True)
    base = armar(crudos, AHORA, "viernes", 5, ruta_validacion=tmp_path / "x")
    assert r.p_ganar is not None
    assert r.esperado >= base.esperado - 10.0


def test_no_paso_avisa(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=True, paso_2=False)
    assert r.p_ganar is None
    assert "La probabilidad de ganar no pasó la validación." in r.avisos


def test_martes_es_preliminar(crudos, tmp_path):
    r = _r(crudos, tmp_path, tipo="martes", paso_1=False, paso_2=True)
    assert r.p_ganar_preliminar and "preliminar" in generar_html(r)


def test_artefacto_roto_no_tumba_el_reporte(crudos, tmp_path):
    kw = _entorno(tmp_path, True, True)
    kw["ruta_varianza"].write_bytes(b"roto")
    (tmp_path / validar.RESULTADO).write_text(json.dumps(
        {"paso_1": True, "paso_2": True, "sha256": huella(kw["ruta_varianza"])}),
        encoding="utf-8")
    r = armar(crudos, AHORA, "viernes", 5, **kw)
    assert r.p_ganar is None
    assert any("probabilidad de ganar" in a.lower() for a in r.avisos)


def test_sin_nflverse_igual_calcula(crudos, tmp_path):
    sin = {k: v for k, v in crudos.items() if k not in ("semanal", "snaps", "jugadores")}
    r = armar(sin, AHORA, "viernes", 5, **_entorno(tmp_path, False, True))
    assert r.p_ganar is not None


def test_rival_con_titular_fuera_usa_su_optima():
    t = pd.DataFrame({
        "jugador_id": [1, 2, 3, 4, 5, 6, 7, 8], "pos": ["QB", "RB", "RB", "WR", "WR", "TE",
                                                        "WR", "WR"],
        "esperado": [20, 15, 14, 13, 12, 10, 0, 11], "proy": [20, 15, 14, 13, 12, 10, 9, 11],
        "lesion": ["ACTIVE"] * 6 + ["OUT", "ACTIVE"], "inicio_utc": pd.Timestamp(
            "2026-10-05 17:00", tz="UTC"), "slot": ["QB", "RB", "RB", "WR", "WR", "TE",
                                                     "FLEX", "BANCA"], "bloqueado": False})
    al = en_vivo.alineacion_rival(t)
    assert 7 not in al.ids() and 8 in al.ids()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_varianza_reporte.py -q`
Expected: FAIL (`ImportError` / `TypeError: unexpected keyword 'ruta_varianza'`)

- [ ] **Step 3: Implement `en_vivo.py`**

```python
# src/fantasy/varianza/en_vivo.py
"""La probabilidad de ganar en el reporte: rival real, partidos ya jugados, rol de 2026."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy.decision.agencia_libre import FUERA
from fantasy.decision.alineacion import TITULARES, Alineacion, optima
from fantasy.varianza import alinear, simular
from fantasy.varianza.grupos import asignar


def tabla_rival(t: pd.DataFrame, plantillas: pd.DataFrame, rival_id: int,
                ahora: pd.Timestamp) -> pd.DataFrame:
    pr = plantillas.loc[plantillas.equipo_id == rival_id, ["jugador_id", "slot", "bloqueado"]]
    tr = t.drop(columns=["slot", "bloqueado"], errors="ignore").merge(pr, on="jugador_id")
    empezo = tr.inicio_utc.notna() & (tr.inicio_utc <= ahora)
    tr["bloqueado"] = tr.bloqueado.astype(bool) & empezo
    return tr


def alineacion_rival(tr: pd.DataFrame) -> Alineacion:
    """Su alineación actual; si tiene un titular fuera, en descanso o un lugar vacío, la
    mejor por puntos esperados (lo razonable es que la arregle)."""
    tit = tr[tr.slot.isin(TITULARES)]
    incompleta = (len(tit) < len(TITULARES) + 2  # QB, RB×2, WR×2, TE, FLEX = 7
                  or tit.lesion.isin(FUERA).any()
                  or (tit.inicio_utc.isna() & ~tit.bloqueado.astype(bool)).any())
    if incompleta:
        return optima(tr)
    return Alineacion(tuple((s, int(j)) for s, j in zip(tit.slot, tit.jugador_id, strict=True)),
                      float(tit.esperado.sum()))


@dataclass
class Simulacion:
    puntos: np.ndarray
    col: dict[int, int]
    cols_rival: list[int]

    def p(self, al: Alineacion) -> float:
        return simular.p_ganar(self.puntos, [self.col[j] for j in al.ids()], self.cols_rival)

    def dispersion(self, j: int) -> float:
        return simular.dispersion(self.puntos, self.col[j])


def preparar(tm: pd.DataFrame, tr: pd.DataFrame, al_rival: Alineacion, reales: pd.DataFrame,
             rol_semana: pd.DataFrame, art, n: int = simular.N_SIM,
             semilla: int = 0) -> Simulacion:
    mios = [int(j) for j in tm.jugador_id]
    ids = mios + [j for j in al_rival.ids() if j not in set(mios)]
    f = pd.concat([tm, tr]).drop_duplicates("jugador_id").set_index("jugador_id").loc[ids]
    real = dict(zip(reales.jugador_id.astype(int), reales.puntos, strict=True))
    bloq = f.bloqueado.fillna(False).astype(bool).to_numpy()
    jug = pd.DataFrame({
        "jugador_id": ids, "pos": f.pos.to_numpy(), "proy": f.proy.to_numpy(float),
        "p_jugar": f.p_jugar.to_numpy(float), "equipo": f.equipo_nfl_id.to_numpy(),
        "real_fijo": [real.get(j, np.nan) if b else np.nan for j, b in zip(ids, bloq,
                                                                            strict=True)]})
    jug.loc[jug.real_fijo.notna(), "p_jugar"] = 1.0
    rasgos = rol_semana.drop(columns="pos").set_index("jugador_id").reindex(ids).fillna(0.0)
    jug["grupo"] = asignar(art.grupos, rasgos.reset_index(drop=True).assign(
        pos=jug.pos.to_numpy())).to_numpy()
    puntos = simular.simular(jug, art, n, semilla)
    col = {j: i for i, j in enumerate(ids)}
    return Simulacion(puntos, col, [col[j] for j in al_rival.ids()])


def elegir(sim: Simulacion, tm: pd.DataFrame) -> tuple[Alineacion, float]:
    cands = alinear.candidatas(tm)
    p = [sim.p(c) for c in cands]
    return cands[alinear.elegir(p)], p[0]


def explicar(elegida: Alineacion, opt: Alineacion, p_optima: float, sim: Simulacion,
             nombres: dict[int, str]) -> list[str]:
    entran = sorted(elegida.ids() - opt.ids())
    salen = sorted(opt.ids() - elegida.ids())
    lado = "arriba" if p_optima >= 0.5 else "abajo"
    lineas = []
    for e, s in zip(entran, salen, strict=False):
        busca = "estabilidad" if sim.dispersion(e) < sim.dispersion(s) else "techo"
        lineas.append(f"Entra {nombres[e]} por {nombres[s]}: vas {lado} y conviene {busca}.")
    return lineas
```

- [ ] **Step 4: Cablear en `armado.py`**

Imports nuevos (junto a los existentes):

```python
from fantasy.config import RUTA_ROL_PREVIO, RUTA_VARIANZA
from fantasy.varianza import artefacto as artefacto_pg
from fantasy.varianza import en_vivo
from fantasy.varianza import rol as rol_pg
from fantasy.varianza import validar as validar_pg
```

Campos nuevos al final de `Reporte`:

```python
    p_ganar: int | None = None
    p_ganar_preliminar: bool = False
    explicaciones_pg: list[str] = field(default_factory=list)
```

Firma de `armar`: añade `ruta_varianza: Path | None = None, ruta_rol_previo: Path | None = None`.

Reemplaza la línea `al = aplicar_regla_duda(optima(tm), tm)` por:

```python
    al_optima = optima(tm)
    al = aplicar_regla_duda(al_optima, tm)
    p_ganar, explicaciones_pg = None, []
    est_pg = validar_pg.estado(ruta_validacion or RUTA_VALIDACION,
                               ruta_varianza or RUTA_VARIANZA)
    if est_pg["paso_2"]:
        try:
            sim = _simulacion(crudos, t, tm, plantillas, liga, equipo_id, semana, ahora,
                              ruta_varianza or RUTA_VARIANZA, ruta_rol_previo or RUTA_ROL_PREVIO)
            if est_pg["paso_1"]:
                elegida, p_opt = en_vivo.elegir(sim, tm)
                nombres_tm = dict(zip(tm.jugador_id.astype(int), tm.nombre, strict=True))
                explicaciones_pg = en_vivo.explicar(elegida, al_optima, p_opt, sim, nombres_tm)
                al = aplicar_regla_duda(elegida, tm)
            p_ganar = round(100 * sim.p(al))
        except Exception as e:  # noqa: BLE001 — la simulación nunca bloquea el reporte
            avisos.append(f"No se pudo calcular la probabilidad de ganar "
                          f"({type(e).__name__}: {e}).")
            al = aplicar_regla_duda(al_optima, tm)
            explicaciones_pg = []
    elif est_pg["existe"]:
        avisos.append("La probabilidad de ganar no pasó la validación.")
```

Añade la función de módulo (después de `hora_sidney`):

```python
def _simulacion(crudos, t, tm, plantillas, liga, equipo_id, semana, ahora, ruta_art,
                ruta_previo):
    art = artefacto_pg.cargar(ruta_art)
    rival = espn.rival_de(liga, equipo_id, semana)
    if rival is None:
        raise ValueError(f"sin rival en la semana {semana}")
    tr = en_vivo.tabla_rival(t, plantillas, rival, ahora)
    al_rival = en_vivo.alineacion_rival(tr)
    reales = espn.parsear_reales(crudos["proyecciones"], TEMPORADA)
    reales = reales[reales.semana == semana]
    previo = pd.read_csv(ruta_previo) if ruta_previo.exists() else None
    ids = pd.concat([tm, tr]).drop_duplicates("jugador_id")[["jugador_id", "pos"]]
    rol_semana = rol_pg.previo_a(rol_pg.leer(crudos), ids.assign(semana=semana), previo)
    return en_vivo.preparar(tm, tr, al_rival, reales, rol_semana, art)
```

En el `return Reporte(...)` añade:

```python
        p_ganar=p_ganar, p_ganar_preliminar=(tipo == "martes" and p_ganar is not None),
        explicaciones_pg=explicaciones_pg,
```

Nota: `cambios`, `inicios`, `reemplazos` y la plantilla ya se calculan a partir de `al` más abajo, así que la alineación elegida fluye sola.

- [ ] **Step 5: Plantilla**

En `reporte.html.j2`, justo antes de `<h2>Qué hacer</h2>`:

```jinja
{% if p_ganar is not none %}
<p class="pganar"><strong>Probabilidad de ganar esta semana: {{ p_ganar }}%</strong>{% if p_ganar_preliminar %} <small>(preliminar: el rival aún puede cambiar su alineación)</small>{% endif %}</p>
{% if explicaciones_pg %}<ul class="suave">{% for x in explicaciones_pg %}<li>{{ x }}</li>{% endfor %}</ul>{% endif %}
{% endif %}
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_varianza_reporte.py -q && uv run pytest -q && uv run ruff check src tests`
Expected: 8 passed; toda la suite en verde (las pruebas viejas de `armar` no pasan `ruta_varianza` y, sin `validacion/2025_pganar.json` en el repo, no cambian).

- [ ] **Step 7: Commit**

```bash
git add src/fantasy/varianza/en_vivo.py src/fantasy/reporte tests/test_varianza_reporte.py
git commit -m "feat(reporte): probabilidad de ganar contra el rival real, según la validación"
```

---

### Task 10: Documentación y cierre

**Files:**
- Modify: `PROYECTO.md`, `docs/ESTADO.md`, `README.md`

- [ ] **Step 1: `PROYECTO.md`** — añade a la tabla de decisiones cerradas:

```markdown
| 25 | Probabilidad de ganar | El reporte calcula la **probabilidad de ganar** contra el rival real (errores reales de ESPN por tipo de jugador según su rol, compañeros correlacionados, Monte Carlo) y, en decisiones parejas, alinea para maximizarla. Manda solo si pasa una corrida **única sobre 2025** (que se reutiliza una vez solo para esto, porque la varianza no se había medido ahí): gana más enfrentamientos en ligas simuladas (IC95 por semanas sin el cero) **y** sus porcentajes son creíbles (±5 puntos por tramo). Si solo cumple lo segundo, se muestra el porcentaje sin mandar. (2026-10-05) |
```

- [ ] **Step 2: `docs/ESTADO.md`** — en "Dónde estamos" añade la fila de la fase "Probabilidad de ganar" con el estado real (construida; ensayo 2024 con su resultado; sellado pendiente o hecho) y en "Pendientes" el paso siguiente: `uv run fantasy varianza-registrar`, commit, y `uv run fantasy varianza-validar --sellado-final` **con el visto bueno de Mario**. Añade los comandos nuevos a "Comandos". Cambia "nunca reusar 2025" por "2025 ya se usó para el modelo de puntos y (una vez) para la varianza".

- [ ] **Step 3: `README.md`** — una sección corta "Probabilidad de ganar" con qué hace, cómo se valida y los cuatro comandos.

- [ ] **Step 4: Verificación completa**

Run: `uv run pytest -q && uv run ruff check src tests && uv run fantasy reporte --tipo domingo --salida <scratch> --sin-correo --forzar`
Expected: suite en verde, ruff limpio, reporte generado sin la sección nueva (aún no hay resultado sellado).

- [ ] **Step 5: Commit, revisión final y PR**

```bash
git add PROYECTO.md docs/ESTADO.md README.md
git commit -m "docs: decisión 25 y estado de la probabilidad de ganar"
```

Lanzar la revisión final de toda la rama (subagente, modelo más capaz) contra la spec; corregir lo confirmado; `git push -u origin prob-ganar` y `gh pr create` (avisar a Mario en una línea antes). **No** correr `varianza-validar --sellado-final` sin su visto bueno explícito.
