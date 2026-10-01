# Fase 3 — Modelo serio y validación: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un modelo con contexto del partido que se elige solo con 2023–2024, un protocolo
congelado para la corrida única sobre 2025 (que **no** se ejecuta en este plan), la
validación en vivo con 2026 como plan B y el interruptor que deja al modelo decidir cuando
pase.

**Architecture:** Sobre la fase 1. `modelo/contexto.py` arma líneas de apuestas y puntos
permitidos por el rival; `modelo/variables.py` gana `filas_v2`/`desde_crudos_v2`;
`modelo/calibracion.py` estima el factor de ESPN calibrada; `modelo/candidatos.py` entrena
ridge o gradient boosting sobre la corrección `real − espn_cal`; `modelo/seleccion.py` hace
el walk-forward de 2024 y elige; `modelo/validacion.py` aplica el criterio, la corrida
sellada y la validación en vivo; `modelo/estado.py` dice si el modelo manda.

**Tech Stack:** Python 3.12, uv, pandas, numpy, scikit-learn (Ridge, HistGradientBoostingRegressor), joblib, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`, sección **10**;
decisiones 19, 20, 23 y 24 de `PROYECTO.md`.

## Global Constraints

- **2025 sellada**: ningún paso de este plan descarga, lee ni evalúa 2025. El único código que puede tocarla es `fantasy validar --sellado-final`, y **no se ejecuta** en este plan: requiere visto bueno explícito de Mario.
- Ningún archivo de 2025 se guarda en el repo antes de la corrida sellada (`games.csv` se filtra al bajarlo).
- Regla anti-fuga: `semana_fuente_max < semana` en toda fila; las líneas de apuestas de la semana w son información previa al partido.
- ESPN calibrada: `k` en [0.80, 1.10], paso 0.005, minimizando MAE en relevantes de temporadas anteriores.
- Candidatos: ridge α ∈ {1, 10, 100}; HGB `loss="absolute_error"`, `learning_rate=0.05`, `max_depth` ∈ {2, 3}, `max_iter` ∈ {100, 300}, `random_state=0`. Una sola configuración para las 4 posiciones; gana el menor MAE en el walk-forward 2024 (semanas 3–17).
- Criterio (decisión 19): Δ MAE (modelo − ESPN calibrada) < 0, IC95 bootstrap por semanas con límite superior < 0, y en ninguna posición MAE modelo > MAE ESPN calibrada.
- Validación en vivo: semanas ≥ 5, instantánea más reciente de la semana tomada antes del primer partido de esa semana; se evalúa con 8 semanas.
- Abreviaturas: ESPN `LAR`→`LA`, `WSH`→`WAS`; el resto igual. `spread_line` > 0 = local favorito.
- El modelo nunca tumba el reporte (cualquier falla → aviso).

## Review Focus

1. **Una semana sin línea de apuestas para un equipo (descanso, partido internacional sin datos, juego aplazado)**: la fila no se cae ni queda NaN; usa valores neutros. Prueba en la tarea 3.
2. **Un jugador que cambió de equipo a mitad de temporada**: en el histórico su equipo es el de esa semana, no el actual de ESPN. Prueba en la tarea 3.
3. **`games.csv` trae filas de 2025 o resultados de semanas futuras**: nunca llegan a disco ni a las variables. Prueba en la tarea 1.
4. **El registro dice una configuración pero el modelo guardado es otro** (alguien reentrenó): `validar` se niega. Prueba en la tarea 7.
5. **La validación en vivo toma una instantánea posterior al primer partido de la semana**: se descarta. Prueba en la tarea 8.

---

## Estructura de archivos

```
src/fantasy/ingesta/nflverse.py     + columnas opponent_team/target_share/air_yards_share, bajar_juegos, uso_extendido
src/fantasy/ingesta/historico.py    + juegos en guardar/cargar, permitir_sellada
src/fantasy/modelo/contexto.py      (nuevo) líneas y puntos permitidos
src/fantasy/modelo/variables.py     + VARIABLES_V2, filas_v2, desde_crudos_v2
src/fantasy/modelo/calibracion.py   (nuevo)
src/fantasy/modelo/candidatos.py    (nuevo) CONFIGS, ModeloV2, entrenar_v2, predecir_v2, guardar_v2, cargar_v2
src/fantasy/modelo/seleccion.py     (nuevo) walk_forward_v2, comparar
src/fantasy/modelo/validacion.py    (nuevo) criterio, validar_sellado, instantaneas_previas, validar_en_vivo
src/fantasy/modelo/estado.py        (nuevo) estado_validacion
src/fantasy/proyeccion/modelo.py    + usa modelo v2 si existe; prediccion_v2 para cuando manda
src/fantasy/reporte/armado.py, plantilla  + "VALIDADO", proyección del modelo cuando manda
src/fantasy/cli.py                  + seleccionar, validar, validar-en-vivo; juegos en el reporte
historico/juegos_<t>.csv.gz, validacion/registro.json, modelos/modelo_v2.joblib
```

---

### Task 1: Datos nuevos de nflverse (rival, % de targets y air yards, líneas)

**Files:**
- Modify: `src/fantasy/ingesta/nflverse.py`, `src/fantasy/ingesta/historico.py`, `src/fantasy/cli.py`
- Test: `tests/test_nflverse_v2.py`

**Interfaces:**
- Produces:
  - `nflverse.COLUMNAS["semanal"]` incluye además `opponent_team`, `target_share`, `air_yards_share`.
  - `nflverse.URL_JUEGOS = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"`
  - `nflverse.bajar_juegos(temporadas: tuple[int, ...], *, abrir=..., permitir_sellada=False, dormir=time.sleep) -> str` (CSV con `season, week, gameday, gametime, home_team, away_team, spread_line, total_line`, solo `game_type == "REG"` y solo esas temporadas; si incluye 2025 sin `permitir_sellada` → `ValueError("…sellada…")`)
  - `nflverse.uso_extendido(semanal: pd.DataFrame, jugadores: pd.DataFrame) -> pd.DataFrame` columnas `jugador_id, semana, equipo, rival, target_share, air_yards_share` (REG; NaN → 0)
  - `historico.NFLVERSE = ("semanal", "snaps", "jugadores", "juegos")`; `bajar_espn_historico(t, *, get=..., permitir_sellada=False)`; `cargar_historico(raiz, t, *, permitir_sellada=False)`.
  - CLI `historico` también guarda `juegos`; el reporte agrega `crudos["juegos"]` de la temporada en curso (si falla, aviso).

- [ ] **Step 1: Pruebas que fallan**

`tests/test_nflverse_v2.py`:
```python
import io

import pandas as pd
import pytest

from fantasy.ingesta import nflverse

JUEGOS = (
    "game_id,season,game_type,week,gameday,gametime,away_team,home_team,spread_line,total_line\n"
    "a,2024,REG,1,2024-09-08,13:00,BUF,KC,3.0,47.0\n"
    "b,2024,POST,19,2025-01-12,13:00,BUF,KC,1.0,45.0\n"
    "c,2025,REG,1,2025-09-07,13:00,BUF,KC,2.0,48.0\n"
    "d,2026,REG,5,2026-10-11,13:00,LA,WAS,-2.5,44.5\n"
)


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _abrir(url, timeout):
    assert url == nflverse.URL_JUEGOS
    return Resp(JUEGOS.encode())


def test_bajar_juegos_filtra_temporada_y_tipo():
    # Review Focus 3: 2025 y la postemporada nunca pasan.
    df = pd.read_csv(io.StringIO(nflverse.bajar_juegos((2024, 2026), abrir=_abrir)))
    assert sorted(df.season.unique()) == [2024, 2026]
    assert (df.week <= 18).all()
    assert list(df.columns) == ["season", "week", "gameday", "gametime", "home_team",
                                "away_team", "spread_line", "total_line"]


def test_bajar_juegos_2025_sellada():
    with pytest.raises(ValueError, match="sellada"):
        nflverse.bajar_juegos((2025,), abrir=_abrir)
    df = pd.read_csv(io.StringIO(
        nflverse.bajar_juegos((2025,), abrir=_abrir, permitir_sellada=True)))
    assert list(df.season.unique()) == [2025]


def test_uso_extendido():
    semanal = pd.DataFrame({
        "player_id": ["g1", "g1", "g2"], "season_type": ["REG", "REG", "POST"],
        "week": [1, 2, 19], "team": ["KC", "LV", "KC"], "opponent_team": ["BUF", "DEN", "BUF"],
        "target_share": [0.25, None, 0.1], "air_yards_share": [0.3, 0.2, 0.1],
    })
    jug = pd.DataFrame({"gsis_id": ["g1", "g2"], "pfr_id": ["p1", "p2"], "espn_id": [11.0, 12.0]})
    u = nflverse.uso_extendido(semanal, jug).set_index("semana")
    assert list(u.jugador_id.unique()) == [11]
    assert u.loc[2, "equipo"] == "LV" and u.loc[2, "rival"] == "DEN"
    assert u.loc[2, "target_share"] == 0.0
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_nflverse_v2.py -q`
Expected: FAIL con `AttributeError: module 'fantasy.ingesta.nflverse' has no attribute 'bajar_juegos'`

- [ ] **Step 3: Implementar en `nflverse.py`**

En `COLUMNAS["semanal"]` añadir `"opponent_team", "target_share", "air_yards_share"` al final de la lista. Añadir después de `bajar_nflverse`:

```python
URL_JUEGOS = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
COLUMNAS_JUEGOS = ["season", "week", "gameday", "gametime", "home_team", "away_team",
                   "spread_line", "total_line"]
SELLADA = 2025


def bajar_juegos(temporadas, *, abrir=urllib.request.urlopen, permitir_sellada=False,
                 dormir=time.sleep) -> str:
    if SELLADA in temporadas and not permitir_sellada:
        raise ValueError("2025 está sellada para la validación final (decisión 20)")
    df = _leer_csv(URL_JUEGOS, abrir, 3, 5.0, dormir)
    df = df[(df["game_type"] == "REG") & df["season"].isin(temporadas)]
    return df[COLUMNAS_JUEGOS].to_csv(index=False)


def uso_extendido(semanal: pd.DataFrame, jugadores: pd.DataFrame) -> pd.DataFrame:
    ids = jugadores.dropna(subset=["espn_id"])[["gsis_id", "espn_id"]]
    s = semanal[semanal["season_type"] == "REG"].merge(ids, left_on="player_id",
                                                        right_on="gsis_id")
    s = s.rename(columns={"espn_id": "jugador_id", "week": "semana", "team": "equipo",
                          "opponent_team": "rival"})
    s[["target_share", "air_yards_share"]] = s[["target_share", "air_yards_share"]].fillna(0.0)
    s["jugador_id"] = s["jugador_id"].astype("int64")
    s["semana"] = s["semana"].astype("int64")
    return s[["jugador_id", "semana", "equipo", "rival", "target_share", "air_yards_share"]]
```

En `historico.py`: `NFLVERSE = ("semanal", "snaps", "jugadores", "juegos")`; `_no_sellada(temporada, permitir=False)` que no lanza si `permitir`; `bajar_espn_historico(temporada, *, get=obtener_json, permitir_sellada=False)` y `cargar_historico(raiz, temporada, *, permitir_sellada=False)` llaman `_no_sellada(temporada, permitir_sellada)`. `guardar_historico` sigue rechazando 2025 siempre (2025 nunca se guarda en `historico/`).

En `cli.py`, en el bloque `historico`:
```python
            nfl = bajar_nflverse(t) | {"juegos": nflverse.bajar_juegos((t,))}
            historico.guardar_historico(a.raiz, t, historico.bajar_espn_historico(t), nfl)
```
(importar `from fantasy.ingesta import nflverse` arriba). En el flujo del reporte, después de `crudos |= bajar_nflverse(TEMPORADA)` dentro del mismo `try`, añadir `crudos["juegos"] = nflverse.bajar_juegos((TEMPORADA,))`.

- [ ] **Step 4: Verificar y actualizar pruebas viejas**

Run: `uv run pytest -q`
Expected: todo pasa. Si `tests/test_historico.py::test_guardar_y_cargar` falla por la llave nueva, añadir `"juegos": "d\n4\n"` al diccionario de esa prueba (registrar como ruling).

- [ ] **Step 5: Volver a bajar el histórico (con red)**

Run: `uv run fantasy historico && ls historico && uv run python -c "import gzip,io,pandas as pd; d=pd.read_csv(io.BytesIO(gzip.decompress(open('historico/nflverse_2024_juegos.csv.gz','rb').read()))); print(d.season.unique(), len(d))"`
Expected: 10 archivos; `juegos` de 2024 con `[2024] 272`; ningún archivo menciona 2025.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/ingesta tests/test_nflverse_v2.py tests/test_historico.py src/fantasy/cli.py historico
git commit -m "feat: rival, % de targets/air yards y líneas de apuestas desde nflverse (sin 2025)"
```

---

### Task 2: Contexto del partido

**Files:**
- Create: `src/fantasy/modelo/contexto.py`
- Test: `tests/test_contexto.py`

**Interfaces:**
- Produces:
  - `ESPN_A_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}`; `a_nflverse(abrev: str) -> str`
  - `lineas(juegos: pd.DataFrame) -> pd.DataFrame` columnas `equipo, semana, rival, local, pts_equipo, spread_equipo` (dos filas por partido)
  - `permitido(semanal: pd.DataFrame) -> pd.DataFrame` columnas `rival, semana, pos, pts` (puntos PPR de nflverse que la defensa `rival` concedió a esa posición en ese partido; solo REG y QB/RB/WR/TE)
  - `permitido_previo(perm: pd.DataFrame, semanas: list[int]) -> pd.DataFrame` columnas `rival, semana, pos, permitido_prev, fuente` (promedio de semanas < w; `fuente` = última semana usada)

- [ ] **Step 1: Pruebas que fallan**

`tests/test_contexto.py`:
```python
import pandas as pd
import pytest

from fantasy.modelo import contexto as cx


def test_abreviaturas():
    assert cx.a_nflverse("LAR") == "LA" and cx.a_nflverse("WSH") == "WAS"
    assert cx.a_nflverse("KC") == "KC"


def test_lineas_desde_el_punto_de_vista_de_cada_equipo():
    juegos = pd.DataFrame({"season": [2024], "week": [1], "home_team": ["KC"],
                           "away_team": ["BUF"], "spread_line": [3.0], "total_line": [47.0]})
    li = cx.lineas(juegos).set_index("equipo")
    assert li.loc["KC", "pts_equipo"] == pytest.approx(25.0)
    assert li.loc["BUF", "pts_equipo"] == pytest.approx(22.0)
    assert li.loc["KC", "spread_equipo"] == 3.0 and li.loc["BUF", "spread_equipo"] == -3.0
    assert li.loc["KC", "local"] == 1 and li.loc["BUF", "local"] == 0
    assert li.loc["KC", "rival"] == "BUF" and (li.semana == 1).all()


def test_permitido_y_previo():
    semanal = pd.DataFrame({
        "season_type": ["REG"] * 4, "week": [1, 1, 2, 3],
        "position": ["WR", "WR", "WR", "WR"], "opponent_team": ["DEN", "DEN", "DEN", "DEN"],
        "fantasy_points_ppr": [10.0, 5.0, 21.0, 99.0],
    })
    perm = cx.permitido(semanal)
    assert perm.set_index("semana").loc[1, "pts"] == 15.0
    prev = cx.permitido_previo(perm, [3]).iloc[0]
    assert prev.permitido_prev == pytest.approx(18.0)  # (15 + 21) / 2, sin la semana 3
    assert prev.fuente == 2
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_contexto.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar**

`src/fantasy/modelo/contexto.py`:
```python
"""Contexto del partido: líneas de apuestas y lo que permite cada defensa."""

import pandas as pd

ESPN_A_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}
POSICIONES = ("QB", "RB", "WR", "TE")


def a_nflverse(abrev: str) -> str:
    return ESPN_A_NFLVERSE.get(abrev, abrev)


def lineas(juegos: pd.DataFrame) -> pd.DataFrame:
    total, spread = juegos["total_line"], juegos["spread_line"]
    local = pd.DataFrame({"equipo": juegos["home_team"], "semana": juegos["week"],
                          "rival": juegos["away_team"], "local": 1,
                          "pts_equipo": (total + spread) / 2, "spread_equipo": spread})
    visita = pd.DataFrame({"equipo": juegos["away_team"], "semana": juegos["week"],
                           "rival": juegos["home_team"], "local": 0,
                           "pts_equipo": (total - spread) / 2, "spread_equipo": -spread})
    return pd.concat([local, visita], ignore_index=True)


def permitido(semanal: pd.DataFrame) -> pd.DataFrame:
    s = semanal[(semanal["season_type"] == "REG") & semanal["position"].isin(POSICIONES)]
    g = s.groupby(["opponent_team", "week", "position"], as_index=False)["fantasy_points_ppr"].sum()
    return g.rename(columns={"opponent_team": "rival", "week": "semana", "position": "pos",
                             "fantasy_points_ppr": "pts"})


def permitido_previo(perm: pd.DataFrame, semanas) -> pd.DataFrame:
    partes = []
    for w in semanas:
        g = perm[perm.semana < w].groupby(["rival", "pos"]).agg(
            permitido_prev=("pts", "mean"), fuente=("semana", "max")).reset_index()
        g["semana"] = w
        partes.append(g)
    if not partes:
        return pd.DataFrame(columns=["rival", "semana", "pos", "permitido_prev", "fuente"])
    return pd.concat(partes, ignore_index=True)[
        ["rival", "semana", "pos", "permitido_prev", "fuente"]]
```

- [ ] **Step 4: Verificar**

Run: `uv run pytest tests/test_contexto.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/modelo/contexto.py tests/test_contexto.py
git commit -m "feat: contexto del partido (líneas y puntos permitidos por la defensa)"
```

---

### Task 3: Variables v2

**Files:**
- Modify: `src/fantasy/modelo/variables.py`
- Test: `tests/test_variables_v2.py`

**Interfaces:**
- Consumes: `filas`, `contexto.*`, `nflverse.uso_extendido`.
- Produces:
  - `VARIABLES_V2 = VARIABLES + ["target_share_prev", "air_share_prev", "pts_equipo", "spread_equipo", "local", "permitido_prev"]`
  - `NEUTROS = {"pts_equipo": 22.0, "spread_equipo": 0.0, "local": 0.5}`
  - `filas_v2(base: pd.DataFrame, uso_ext: pd.DataFrame, equipos: pd.DataFrame, lineas: pd.DataFrame, perm_prev: pd.DataFrame) -> pd.DataFrame` — `base` es la salida de `filas`; `equipos` tiene `jugador_id, semana, equipo` (equipo nflverse de esa semana). Devuelve las columnas de `base` + las nuevas, sin NaN en `VARIABLES_V2`, con `semana_fuente_max` actualizado y verificado.
  - `desde_crudos_v2(crudos: dict, temporada: int, semanas=None, *, equipo_desde_espn=False) -> pd.DataFrame` — requiere `semanal, snaps, jugadores, juegos`; con `equipo_desde_espn=True` el equipo sale de `proTeamId` de ESPN (traducido con `a_nflverse` usando las abreviaturas de `crudos["calendario"]`), si no, de nflverse en esa semana.

- [ ] **Step 1: Pruebas que fallan**

`tests/test_variables_v2.py`:
```python
import pandas as pd
import pytest

from fantasy.modelo import variables as v


def _base():
    return pd.DataFrame({
        "jugador_id": [1, 1, 2], "temporada": 2024, "semana": [2, 3, 3], "pos": ["WR", "WR", "RB"],
        "proy_espn": [10.0, 11.0, 8.0], "pts_prev": [12.0, 11.0, 8.0], "snaps_prev": [0.8, 0.8, 0.0],
        "targets_prev": [6.0, 6.0, 0.0], "acarreos_prev": [0.0, 0.0, 0.0], "n_prev": [1, 2, 0],
        "semana_fuente_max": [1, 2, 0], "real": [9.0, 14.0, None],
    })


def _ctx():
    uso_ext = pd.DataFrame({"jugador_id": [1, 1, 1], "semana": [1, 2, 3],
                            "equipo": ["KC", "LV", "LV"], "rival": ["BUF", "DEN", "SF"],
                            "target_share": [0.2, 0.3, 0.9], "air_yards_share": [0.1, 0.5, 0.9]})
    equipos = uso_ext[["jugador_id", "semana", "equipo"]]
    lineas = pd.DataFrame({"equipo": ["LV", "LV"], "semana": [2, 3], "rival": ["DEN", "SF"],
                           "local": [1, 0], "pts_equipo": [24.0, 19.0],
                           "spread_equipo": [3.0, -6.0]})
    perm_prev = pd.DataFrame({"rival": ["SF"], "semana": [3], "pos": ["WR"],
                              "permitido_prev": [30.0], "fuente": [2]})
    return uso_ext, equipos, lineas, perm_prev


def test_contexto_y_cambio_de_equipo():
    # Review Focus 2: en la semana 2 y 3 juega en LV aunque empezó en KC.
    f = v.filas_v2(_base(), *_ctx()).set_index(["jugador_id", "semana"])
    s3 = f.loc[(1, 3)]
    assert s3.pts_equipo == 19.0 and s3.spread_equipo == -6.0 and s3.local == 0
    assert s3.permitido_prev == 30.0
    assert s3.target_share_prev == pytest.approx(0.25)  # semanas 1 y 2, no la 3
    assert s3.semana_fuente_max == 2


def test_sin_linea_usa_neutros():
    # Review Focus 1: el jugador 2 no tiene equipo ni línea en la semana 3.
    f = v.filas_v2(_base(), *_ctx()).set_index(["jugador_id", "semana"])
    s = f.loc[(2, 3)]
    assert s.pts_equipo == v.NEUTROS["pts_equipo"] and s.local == v.NEUTROS["local"]
    assert s.spread_equipo == 0.0 and s.target_share_prev == 0.0
    assert not f[v.VARIABLES_V2].isna().any().any()


def test_desde_crudos_v2_en_vivo():
    import pathlib

    from fantasy.almacen.instantaneas import cargar
    from fantasy.modelo.contexto import a_nflverse
    sem4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
    c = cargar(sem4)
    ab = {t["id"]: a_nflverse(t["abbrev"]) for t in c["calendario"]["settings"]["proTeams"]}
    filas_j = []
    for t in c["calendario"]["settings"]["proTeams"]:
        for g in (t.get("proGamesByScoringPeriod") or {}).get("4", []):
            if g["homeProTeamId"] == t["id"]:
                filas_j.append({"season": 2026, "week": 4, "gameday": "x", "gametime": "x",
                                "home_team": ab[g["homeProTeamId"]],
                                "away_team": ab[g["awayProTeamId"]],
                                "spread_line": 1.0, "total_line": 44.0})
    c["juegos"] = pd.DataFrame(filas_j).to_csv(index=False)
    f = v.desde_crudos_v2(c, 2026, [4], equipo_desde_espn=True)
    assert len(f) > 200 and not f[v.VARIABLES_V2].isna().any().any()
    con_partido = f[f.proy_espn > 0]
    assert con_partido.pts_equipo.isin([22.5, 21.5, v.NEUTROS["pts_equipo"]]).all()
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_variables_v2.py -q`
Expected: FAIL con `AttributeError: module 'fantasy.modelo.variables' has no attribute 'filas_v2'`

- [ ] **Step 3: Implementar** (añadir al final de `variables.py`; importar `io` y `from fantasy.modelo import contexto`)

```python
VARIABLES_V2 = VARIABLES + ["target_share_prev", "air_share_prev", "pts_equipo",
                            "spread_equipo", "local", "permitido_prev"]
NEUTROS = {"pts_equipo": 22.0, "spread_equipo": 0.0, "local": 0.5}


def filas_v2(base, uso_ext, equipos, lineas, perm_prev):
    partes = []
    for w, b in base.groupby("semana"):
        u = uso_ext[uso_ext.semana < w].groupby("jugador_id").agg(
            target_share_prev=("target_share", "mean"),
            air_share_prev=("air_yards_share", "mean"), fuente_s=("semana", "max"))
        f = b.merge(u, on="jugador_id", how="left")
        eq = equipos[equipos.semana == w][["jugador_id", "equipo"]].drop_duplicates("jugador_id")
        f = f.merge(eq, on="jugador_id", how="left")
        li = lineas[lineas.semana == w][["equipo", "rival", "local", "pts_equipo",
                                         "spread_equipo"]]
        f = f.merge(li, on="equipo", how="left")
        pp = perm_prev[perm_prev.semana == w][["rival", "pos", "permitido_prev", "fuente"]]
        f = f.merge(pp.rename(columns={"fuente": "fuente_p"}), on=["rival", "pos"], how="left")
        partes.append(f)
    f = pd.concat(partes, ignore_index=True)
    f[["target_share_prev", "air_share_prev"]] = (
        f[["target_share_prev", "air_share_prev"]].fillna(0.0))
    for col, neutro in NEUTROS.items():
        f[col] = f[col].fillna(neutro)
    # Relleno con el promedio de la misma semana y posición (nunca de semanas futuras).
    medias = f.groupby(["semana", "pos"])["permitido_prev"].transform("mean")
    f["permitido_prev"] = f["permitido_prev"].fillna(medias).fillna(0.0)
    f["semana_fuente_max"] = (f[["semana_fuente_max", "fuente_s", "fuente_p"]]
                              .max(axis=1).fillna(0).astype(int))
    cols = ["jugador_id", "temporada", "semana", "pos", *VARIABLES_V2, "semana_fuente_max",
            "real"]
    out = f[cols].reset_index(drop=True)
    verificar_sin_fuga(out)
    return out


def desde_crudos_v2(crudos, temporada, semanas=None, *, equipo_desde_espn=False):
    base = desde_crudos(crudos, temporada, semanas)
    leer = {n: pd.read_csv(io.StringIO(crudos[n]), low_memory=False)
            for n in ("semanal", "jugadores", "juegos")}
    uso_ext = nflverse.uso_extendido(leer["semanal"], leer["jugadores"])
    lineas = contexto.lineas(leer["juegos"][leer["juegos"].season == temporada])
    perm_prev = contexto.permitido_previo(contexto.permitido(leer["semanal"]),
                                          sorted(base.semana.unique()))
    if equipo_desde_espn:
        abrev = {t["id"]: contexto.a_nflverse(t["abbrev"])
                 for t in crudos["calendario"]["settings"]["proTeams"]}
        eq = pd.DataFrame([{"jugador_id": pe["id"],
                            "equipo": abrev.get(pe["player"].get("proTeamId"))}
                           for pe in crudos["proyecciones"]["players"]])
        equipos = pd.concat([eq.assign(semana=w) for w in base.semana.unique()],
                            ignore_index=True)
    else:
        equipos = uso_ext[["jugador_id", "semana", "equipo"]]
    return filas_v2(base, uso_ext, equipos, lineas, perm_prev)
```

(El `permitido` de nflverse se calcula con todo `semanal`, pero `permitido_previo` solo promedia semanas < w y deja `fuente` para que la verificación anti-fuga lo confirme.)

- [ ] **Step 4: Verificar**

Run: `uv run pytest tests/test_variables_v2.py -q && uv run pytest -q`
Expected: 3 passed; suite verde.

- [ ] **Step 5: Revisión con datos reales**

Run: `uv run python -c "import pathlib; from fantasy.ingesta import historico; from fantasy.modelo import variables as v; f=v.desde_crudos_v2(historico.cargar_historico(pathlib.Path('historico'),2024),2024); print(len(f), f[v.VARIABLES_V2].describe().loc[['mean','min','max']].round(2).to_string())"`
Expected: ~17 000 filas; `pts_equipo` entre ~10 y ~35, `local` entre 0 y 1, `permitido_prev` positivo, sin NaN.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/modelo/variables.py tests/test_variables_v2.py
git commit -m "feat: variables v2 con contexto del partido, % de targets y rival"
```

---

### Task 4: ESPN calibrada

**Files:**
- Create: `src/fantasy/modelo/calibracion.py`
- Test: `tests/test_calibracion.py`

**Interfaces:**
- Consumes: `evaluar.relevantes`.
- Produces: `RANGO = np.round(np.arange(0.80, 1.1001, 0.005), 3)`; `factor(f: pd.DataFrame) -> float` (MAE mínimo de `k · proy_espn` contra `real` en `relevantes(f)` con `real` no nulo; en empate, el k más cercano a 1).

- [ ] **Step 1: Prueba que falla**

`tests/test_calibracion.py`:
```python
import numpy as np
import pandas as pd

from fantasy.modelo import calibracion


def test_recupera_el_sesgo():
    r = np.random.default_rng(0)
    n = 4000
    f = pd.DataFrame({"semana": np.repeat(np.arange(1, 11), n // 10),
                      "pos": np.tile(["QB", "RB", "WR", "TE"], n // 4),
                      "proy_espn": r.uniform(5, 25, n)})
    f["real"] = 0.9 * f.proy_espn + r.laplace(0, 1.0, n)  # mediana = 0.9 · proyección
    k = calibracion.factor(f)
    assert abs(k - 0.9) <= 0.015
    assert k in calibracion.RANGO
```

- [ ] **Step 2: Verificar que falla**

Run: `uv run pytest tests/test_calibracion.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar**

```python
"""ESPN calibrada: el factor que mejor corrige el sesgo de ESPN en temporadas anteriores."""

import numpy as np
import pandas as pd

from fantasy.modelo.evaluar import relevantes

RANGO = np.round(np.arange(0.80, 1.1001, 0.005), 3)


def factor(f: pd.DataFrame) -> float:
    r = relevantes(f[f["real"].notna()])
    proy, real = r["proy_espn"].to_numpy(float), r["real"].to_numpy(float)
    errores = [(float(np.abs(k * proy - real).mean()), abs(k - 1.0), float(k)) for k in RANGO]
    return min(errores)[2]
```

- [ ] **Step 4: Verificar y commit**

Run: `uv run pytest tests/test_calibracion.py -q`
Expected: 1 passed

```bash
git add src/fantasy/modelo/calibracion.py tests/test_calibracion.py
git commit -m "feat: factor de calibración de ESPN"
```

---

### Task 5: Candidatos (ridge y gradient boosting sobre la corrección)

**Files:**
- Create: `src/fantasy/modelo/candidatos.py`
- Test: `tests/test_candidatos.py`

**Interfaces:**
- Consumes: `VARIABLES_V2`, `verificar_sin_fuga`.
- Produces:
  - `CONFIGS: list[dict]` (3 ridge + 4 hgb, en el orden de la spec)
  - `@dataclass ModeloV2(config: dict, k: float, variables: list[str], por_pos: dict[str, object], version: int = 2)`
  - `entrenar_v2(f: pd.DataFrame, config: dict, k: float) -> ModeloV2` (filas con `real` no nulo y `proy_espn > 0`)
  - `predecir_v2(m: ModeloV2, f: pd.DataFrame) -> pd.Series` (`k · proy_espn + corrección`; NaN si la posición no tiene modelo)
  - `guardar_v2(m, ruta)`, `cargar_v2(ruta) -> ModeloV2` (joblib; `ValueError` si `variables != VARIABLES_V2` o `version != 2`)
  - `nombre_config(config: dict) -> str` (p. ej. `"ridge(alpha=10)"`, `"hgb(depth=2,iter=300)"`)

- [ ] **Step 1: Pruebas que fallan**

`tests/test_candidatos.py`:
```python
import numpy as np
import pandas as pd
import pytest

from fantasy.modelo import candidatos as c
from fantasy.modelo.variables import VARIABLES_V2, FugaDeDatos


def _datos(n=2000, semilla=0):
    r = np.random.default_rng(semilla)
    f = pd.DataFrame({v: r.uniform(0, 1, n) for v in VARIABLES_V2})
    f["proy_espn"] = r.uniform(5, 20, n)
    f["pts_equipo"] = r.uniform(15, 30, n)
    f["pos"] = np.tile(["QB", "RB", "WR", "TE"], n // 4)
    f["jugador_id"], f["temporada"], f["semana"], f["semana_fuente_max"] = np.arange(n), 2024, 5, 4
    # Lo que ESPN no ve: el contexto del partido mueve ±2 puntos.
    f["real"] = 0.95 * f.proy_espn + 0.4 * (f.pts_equipo - 22.5) + r.normal(0, 0.5, n)
    return f


def test_configs():
    assert len(c.CONFIGS) == 7
    assert [c.nombre_config(x) for x in c.CONFIGS][:2] == ["ridge(alpha=1)", "ridge(alpha=10)"]


@pytest.mark.parametrize("config", [c.CONFIGS[0], c.CONFIGS[4]])
def test_aprende_la_correccion(config):
    f = _datos()
    m = c.entrenar_v2(f, config, k=0.95)
    pred = c.predecir_v2(m, f)
    base = np.abs(0.95 * f.proy_espn - f.real).mean()
    assert np.abs(pred - f.real).mean() < 0.7 * base


def test_guardar_y_cargar(tmp_path):
    f = _datos()
    m = c.entrenar_v2(f, c.CONFIGS[3], k=0.95)
    c.guardar_v2(m, tmp_path / "m.joblib")
    m2 = c.cargar_v2(tmp_path / "m.joblib")
    assert np.allclose(c.predecir_v2(m, f), c.predecir_v2(m2, f))
    m.variables = ["otra"]
    c.guardar_v2(m, tmp_path / "malo.joblib")
    with pytest.raises(ValueError, match="variables"):
        c.cargar_v2(tmp_path / "malo.joblib")


def test_no_entrena_con_fuga():
    f = _datos()
    f.loc[0, "semana_fuente_max"] = 5
    with pytest.raises(FugaDeDatos):
        c.entrenar_v2(f, c.CONFIGS[0], k=1.0)
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_candidatos.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar**

`src/fantasy/modelo/candidatos.py`:
```python
"""Candidatos de la fase 3: ridge o gradient boosting sobre la corrección a ESPN calibrada."""

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fantasy.modelo.variables import VARIABLES_V2, verificar_sin_fuga

CONFIGS = ([{"tipo": "ridge", "alpha": a} for a in (1, 10, 100)]
           + [{"tipo": "hgb", "max_depth": d, "max_iter": n} for d in (2, 3) for n in (100, 300)])


def nombre_config(config: dict) -> str:
    if config["tipo"] == "ridge":
        return f"ridge(alpha={config['alpha']})"
    return f"hgb(depth={config['max_depth']},iter={config['max_iter']})"


def _estimador(config: dict):
    if config["tipo"] == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=config["alpha"]))
    return HistGradientBoostingRegressor(loss="absolute_error", learning_rate=0.05,
                                         max_depth=config["max_depth"],
                                         max_iter=config["max_iter"], random_state=0)


@dataclass
class ModeloV2:
    config: dict
    k: float
    variables: list[str] = field(default_factory=lambda: list(VARIABLES_V2))
    por_pos: dict[str, object] = field(default_factory=dict)
    version: int = 2


def entrenar_v2(f: pd.DataFrame, config: dict, k: float) -> ModeloV2:
    verificar_sin_fuga(f)
    datos = f[f["real"].notna() & (f["proy_espn"] > 0)]
    m = ModeloV2(config=config, k=k)
    for pos, g in datos.groupby("pos"):
        x = g[VARIABLES_V2].to_numpy(float)
        y = g["real"].to_numpy(float) - k * g["proy_espn"].to_numpy(float)
        m.por_pos[pos] = _estimador(config).fit(x, y)
    return m


def predecir_v2(m: ModeloV2, f: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=f.index, dtype=float)
    for pos, est in m.por_pos.items():
        mask = f["pos"] == pos
        if mask.any():
            g = f.loc[mask]
            pred[mask] = m.k * g["proy_espn"].to_numpy(float) + est.predict(
                g[VARIABLES_V2].to_numpy(float))
    return pred


def guardar_v2(m: ModeloV2, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, ruta)


def cargar_v2(ruta: Path) -> ModeloV2:
    m = joblib.load(ruta)
    if getattr(m, "version", None) != 2 or m.variables != VARIABLES_V2:
        raise ValueError(f"el modelo en {ruta} usa otras variables o versión")
    return m
```

- [ ] **Step 4: Verificar y commit**

Run: `uv run pytest tests/test_candidatos.py -q`
Expected: 5 passed

```bash
git add src/fantasy/modelo/candidatos.py tests/test_candidatos.py
git commit -m "feat: candidatos ridge y gradient boosting sobre la corrección a ESPN calibrada"
```

---

### Task 6: Selección en 2024 y registro

**Files:**
- Create: `src/fantasy/modelo/seleccion.py`
- Modify: `src/fantasy/cli.py` (subcomando `seleccionar`)
- Test: `tests/test_seleccion.py`

**Interfaces:**
- Consumes: `calibracion.factor`, `candidatos.*`, `evaluar.relevantes`, `evaluar.resumen`.
- Produces:
  - `walk_forward_v2(previas, actual, config, k=None, semanas=range(3, 18)) -> pd.DataFrame` columnas `semana, pos, jugador_id, real, espn, modelo` donde `espn` = ESPN **calibrada** (`k · proy_espn`; si `k` es None se estima con `previas`)
  - `comparar(previas, actual) -> list[dict]` (una entrada por config: `config, nombre, mae_modelo, mae_espn, delta`; ordenada por `mae_modelo`)
  - CLI `fantasy seleccionar [--raiz historico] [--registro validacion/registro.json] [--modelo modelos/modelo_v2.joblib]`: compara en 2024 (previas = 2023), elige la primera de `comparar`, estima `k` con 2023+2024, entrena con 2023+2024, guarda modelo y registro (`config, nombre, k, variables, comparacion, fecha, commit`).

- [ ] **Step 1: Pruebas que fallan**

`tests/test_seleccion.py`:
```python
import numpy as np
import pandas as pd

from fantasy.modelo import seleccion
from fantasy.modelo.variables import VARIABLES_V2


def _temporada(t, semilla):
    r = np.random.default_rng(semilla)
    filas = []
    for w in range(1, 18):
        for j in range(60):
            fila = {v: float(r.uniform(0, 1)) for v in VARIABLES_V2}
            fila.update({"jugador_id": j, "temporada": t, "semana": w,
                         "pos": ["QB", "RB", "WR", "TE"][j % 4],
                         "proy_espn": 5.0 + j % 15, "pts_equipo": float(r.uniform(15, 30)),
                         "semana_fuente_max": w - 1})
            fila["real"] = 0.9 * fila["proy_espn"] + 0.5 * (fila["pts_equipo"] - 22.5) + r.normal(0, 1)
            filas.append(fila)
    return pd.DataFrame(filas)


def test_walk_forward_usa_espn_calibrada_y_semanas():
    pred = seleccion.walk_forward_v2(_temporada(2023, 0), _temporada(2024, 1),
                                     {"tipo": "ridge", "alpha": 10})
    assert set(pred.semana) == set(range(3, 18))
    assert {"espn", "modelo", "real"} <= set(pred.columns)
    assert (pred.espn < pred.real.max()).all()


def test_comparar_ordena_por_mae():
    res = seleccion.comparar(_temporada(2023, 0), _temporada(2024, 1))
    assert len(res) == 7
    assert [x["mae_modelo"] for x in res] == sorted(x["mae_modelo"] for x in res)
    assert res[0]["delta"] < 0  # el contexto existe en los datos sintéticos
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_seleccion.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar `seleccion.py`**

```python
"""Elección del modelo con el walk-forward de 2024 (regla fijada: menor MAE)."""

import pandas as pd

from fantasy.modelo import calibracion, candidatos
from fantasy.modelo.evaluar import relevantes, resumen


def walk_forward_v2(previas, actual, config, k=None, semanas=range(3, 18)):
    k = calibracion.factor(previas) if k is None else k
    salida = []
    for w in semanas:
        entreno = pd.concat([previas, actual[actual.semana < w]], ignore_index=True)
        m = candidatos.entrenar_v2(entreno, config, k)
        prueba = relevantes(actual[(actual.semana == w) & actual.real.notna()])
        if prueba.empty:
            continue
        salida.append(pd.DataFrame({
            "semana": w, "pos": prueba.pos.values, "jugador_id": prueba.jugador_id.values,
            "real": prueba.real.values, "espn": k * prueba.proy_espn.values,
            "modelo": candidatos.predecir_v2(m, prueba).values}))
    return pd.concat(salida, ignore_index=True)


def comparar(previas, actual):
    k = calibracion.factor(previas)
    res = []
    for config in candidatos.CONFIGS:
        r = resumen(walk_forward_v2(previas, actual, config, k=k), n=200)
        res.append({"config": config, "nombre": candidatos.nombre_config(config),
                    "mae_modelo": r["mae_modelo"], "mae_espn": r["mae_espn"],
                    "delta": r["delta"]})
    return sorted(res, key=lambda x: x["mae_modelo"])
```

- [ ] **Step 4: CLI `seleccionar`**

En `_parser()`:
```python
    se = sub.add_parser("seleccionar", help="elige el modelo v2 en 2024 y lo registra")
    se.add_argument("--raiz", type=Path, default=Path("historico"))
    se.add_argument("--registro", type=Path, default=Path("validacion/registro.json"))
    se.add_argument("--modelo", type=Path, default=Path("modelos/modelo_v2.joblib"))
```
En `main`, junto a los otros subcomandos:
```python
    if a.comando == "seleccionar":
        import json
        import subprocess
        from fantasy.ingesta import historico
        from fantasy.modelo import calibracion, candidatos, seleccion, variables
        t23, t24 = (variables.desde_crudos_v2(historico.cargar_historico(a.raiz, t), t)
                    for t in (2023, 2024))
        comparacion = seleccion.comparar(t23, t24)
        elegido = comparacion[0]
        ambas = pd.concat([t23, t24], ignore_index=True)
        k = calibracion.factor(ambas)
        candidatos.guardar_v2(candidatos.entrenar_v2(ambas, elegido["config"], k), a.modelo)
        commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                text=True).stdout.strip()
        registro = {"config": elegido["config"], "nombre": elegido["nombre"], "k": k,
                    "variables": variables.VARIABLES_V2, "comparacion_2024": comparacion,
                    "modelo": str(a.modelo), "fecha": datetime.now(UTC).isoformat(),
                    "commit": commit}
        a.registro.parent.mkdir(parents=True, exist_ok=True)
        a.registro.write_text(json.dumps(registro, indent=1, ensure_ascii=False),
                              encoding="utf-8")
        for x in comparacion:
            print(f"{x['nombre']:24} MAE {x['mae_modelo']:.3f} · ESPN cal {x['mae_espn']:.3f}"
                  f" · delta {x['delta']:+.3f}")
        print(f"Elegido: {elegido['nombre']} · k = {k}")
        return 0
```

- [ ] **Step 5: Verificar**

Run: `uv run pytest tests/test_seleccion.py -q && uv run pytest -q && uv run ruff check .`
Expected: 2 passed; suite verde.

- [ ] **Step 6: Commit (el registro real se genera en la tarea 10)**

```bash
git add src/fantasy/modelo/seleccion.py src/fantasy/cli.py tests/test_seleccion.py
git commit -m "feat: selección del modelo v2 en 2024 y registro"
```

---

### Task 7: Criterio y corrida sellada (sin ejecutarla)

**Files:**
- Create: `src/fantasy/modelo/validacion.py`
- Modify: `src/fantasy/cli.py` (subcomando `validar`)
- Test: `tests/test_validacion.py`

**Interfaces:**
- Produces:
  - `criterio(res: dict) -> bool` (decisión 19)
  - `validar_sellado(registro: dict, modelo_guardado: ModeloV2, previas: pd.DataFrame, obtener_2025: Callable[[], pd.DataFrame], destino: Path, git_limpio: Callable[[], bool]) -> dict` — lanza `RuntimeError` si `destino` ya existe, si el repo no está limpio o si `modelo_guardado.config != registro["config"]` o `modelo_guardado.k != registro["k"]` (Review Focus 4); si no, corre `walk_forward_v2(previas, obtener_2025(), registro["config"], k=registro["k"])`, aplica `resumen` (n=2000) y `criterio`, guarda JSON en `destino` y lo devuelve.
  - CLI `fantasy validar --sellado-final [--raiz historico] [--registro …] [--destino validacion/2025.json]`; sin `--sellado-final` imprime qué haría y sale con 2.

- [ ] **Step 1: Pruebas que fallan**

`tests/test_validacion.py`:
```python
import json

import pandas as pd
import pytest

from fantasy.modelo import candidatos, validacion
from tests.test_seleccion import _temporada


def _res(delta, hi, por_pos):
    return {"delta": delta, "ic95": (delta - 0.1, hi), "por_pos": por_pos,
            "mae_modelo": 5.0, "mae_espn": 5.0 - delta}


def test_criterio():
    assert validacion.criterio(_res(-0.2, -0.05, {"QB": (5.0, 5.1), "RB": (6.0, 6.2)}))
    assert not validacion.criterio(_res(-0.2, 0.01, {"QB": (5.0, 5.1)}))       # IC toca 0
    assert not validacion.criterio(_res(-0.2, -0.05, {"QB": (5.2, 5.1)}))      # pierde en QB


def _registro_y_modelo():
    previas = pd.concat([_temporada(2023, 0), _temporada(2024, 1)], ignore_index=True)
    config = {"tipo": "ridge", "alpha": 10}
    m = candidatos.entrenar_v2(previas, config, k=0.9)
    return {"config": config, "k": 0.9}, m, previas


def test_validar_sellado_corre_una_sola_vez(tmp_path):
    registro, m, previas = _registro_y_modelo()
    destino = tmp_path / "2025.json"
    res = validacion.validar_sellado(registro, m, previas, lambda: _temporada(2025, 2),
                                     destino, git_limpio=lambda: True)
    assert destino.exists() and "paso" in json.loads(destino.read_text(encoding="utf-8"))
    assert isinstance(res["paso"], bool)
    with pytest.raises(RuntimeError, match="ya se corrió"):
        validacion.validar_sellado(registro, m, previas, lambda: _temporada(2025, 2),
                                   destino, git_limpio=lambda: True)


def test_validar_sellado_exige_repo_limpio_y_modelo_registrado(tmp_path):
    registro, m, previas = _registro_y_modelo()
    llamado = []

    def obtener():
        llamado.append(1)
        return _temporada(2025, 2)

    with pytest.raises(RuntimeError, match="cambios"):
        validacion.validar_sellado(registro, m, previas, obtener, tmp_path / "a.json",
                                   git_limpio=lambda: False)
    otro = dict(registro, k=0.95)  # Review Focus 4
    with pytest.raises(RuntimeError, match="registro"):
        validacion.validar_sellado(otro, m, previas, obtener, tmp_path / "b.json",
                                   git_limpio=lambda: True)
    assert llamado == []  # 2025 nunca se tocó


def test_cli_sin_bandera_no_corre():
    from fantasy.cli import main
    assert main(["validar"]) == 2
```

Además crear `tests/__init__.py` vacío para que `from tests.test_seleccion import _temporada` funcione.

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_validacion.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar `validacion.py`**

```python
"""Criterio de la decisión 19, corrida sellada de 2025 y validación en vivo de 2026."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fantasy.modelo.evaluar import resumen
from fantasy.modelo.seleccion import walk_forward_v2


def criterio(res: dict) -> bool:
    gana_global = res["delta"] < 0 and res["ic95"][1] < 0
    gana_posiciones = all(m <= e for m, e in res["por_pos"].values())
    return bool(gana_global and gana_posiciones)


def _guardar(res: dict, destino: Path, extra: dict) -> dict:
    salida = {**extra, "mae_modelo": res["mae_modelo"], "mae_espn_calibrada": res["mae_espn"],
              "delta": res["delta"], "ic95": list(res["ic95"]),
              "por_pos": {p: list(v) for p, v in res["por_pos"].items()},
              "paso": criterio(res), "fecha": datetime.now(UTC).isoformat()}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    return salida


def validar_sellado(registro, modelo_guardado, previas, obtener_2025, destino: Path,
                    git_limpio) -> dict:
    if destino.exists():
        raise RuntimeError(f"la validación sellada ya se corrió: {destino}")
    if not git_limpio():
        raise RuntimeError("el repo tiene cambios sin commit: congela todo antes de validar")
    if modelo_guardado.config != registro["config"] or modelo_guardado.k != registro["k"]:
        raise RuntimeError("el modelo guardado no coincide con el registro")
    pred = walk_forward_v2(previas, obtener_2025(), registro["config"], k=registro["k"])
    return _guardar(resumen(pred), destino, {"fuente": "2025 sellada",
                                             "config": registro["config"],
                                             "k": registro["k"],
                                             "semanas": sorted(int(s) for s in pred.semana.unique())})
```

- [ ] **Step 4: CLI `validar`**

En `_parser()`:
```python
    va = sub.add_parser("validar", help="corrida única sobre 2025 (requiere --sellado-final)")
    va.add_argument("--sellado-final", action="store_true")
    va.add_argument("--raiz", type=Path, default=Path("historico"))
    va.add_argument("--registro", type=Path, default=Path("validacion/registro.json"))
    va.add_argument("--destino", type=Path, default=Path("validacion/2025.json"))
```
En `main`:
```python
    if a.comando == "validar":
        if not a.sellado_final:
            print("La validación sellada corre una sola vez sobre 2025 y requiere el visto "
                  "bueno de Mario. Repite con --sellado-final.", file=sys.stderr)
            return 2
        import json
        import subprocess
        from fantasy.ingesta import historico, nflverse
        from fantasy.modelo import candidatos, validacion, variables
        registro = json.loads(a.registro.read_text(encoding="utf-8"))
        previas = pd.concat([variables.desde_crudos_v2(historico.cargar_historico(a.raiz, t), t)
                             for t in (2023, 2024)], ignore_index=True)

        def obtener_2025():
            crudos = {"proyecciones": historico.bajar_espn_historico(2025, permitir_sellada=True)}
            crudos |= bajar_nflverse(2025)
            crudos["juegos"] = nflverse.bajar_juegos((2025,), permitir_sellada=True)
            return variables.desde_crudos_v2(crudos, 2025)

        def git_limpio():
            r = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
            return r.stdout.strip() == ""

        res = validacion.validar_sellado(registro, candidatos.cargar_v2(Path(registro["modelo"])),
                                         previas, obtener_2025, a.destino, git_limpio)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0
```

- [ ] **Step 5: Verificar y commit** (no ejecutar `validar --sellado-final`)

Run: `uv run pytest tests/test_validacion.py -q && uv run pytest -q && uv run ruff check .`
Expected: 4 passed; suite verde.

```bash
git add src/fantasy/modelo/validacion.py src/fantasy/cli.py tests/__init__.py tests/test_validacion.py
git commit -m "feat: criterio de la decisión 19 y corrida sellada protegida (no ejecutada)"
```

---

### Task 8: Validación en vivo 2026

**Files:**
- Modify: `src/fantasy/modelo/validacion.py`, `src/fantasy/cli.py` (subcomando `validar-en-vivo`)
- Test: `tests/test_validacion_vivo.py`

**Interfaces:**
- Produces:
  - `instantaneas_previas(datos: Path, temporada: int = 2026, desde: int = 5) -> dict[int, Path]` — por semana `NN ≥ desde`, la carpeta más reciente de `datos/instantaneas/<t>/semNN/` cuya hora (nombre `AAAA-MM-DDTHH-MM`, Sídney) es **anterior al primer partido** de esa semana según su propio `calendario` (Review Focus 5).
  - `ultima_instantanea(datos: Path, temporada: int = 2026) -> Path`
  - `validar_en_vivo(modelo: ModeloV2, previas: dict[int, dict], ultimo: dict, destino: Path, min_semanas: int = 8) -> dict` — `previas` mapea semana → crudos de su instantánea previa; `ultimo` son los crudos más recientes (puntos reales). Si hay menos de `min_semanas` semanas con reales, devuelve `{"semanas": n, "listo": False}` sin escribir; si no, aplica `resumen` (n=2000) y `criterio`, escribe `destino` y devuelve con `"listo": True`.

- [ ] **Step 1: Pruebas que fallan**

`tests/test_validacion_vivo.py`:
```python
import gzip
import json
from pathlib import Path

import pandas as pd

from fantasy.modelo import validacion


def _calendario(primer_partido_ms):
    return {"settings": {"proTeams": [{"id": 1, "abbrev": "KC", "proGamesByScoringPeriod": {
        "5": [{"date": primer_partido_ms, "homeProTeamId": 1, "awayProTeamId": 2}]}}]}}


def _snap(raiz: Path, semana: int, nombre: str, primer_partido_ms: int):
    c = raiz / "instantaneas" / "2026" / f"sem{semana:02d}" / nombre
    c.mkdir(parents=True)
    (c / "calendario.json.gz").write_bytes(
        gzip.compress(json.dumps(_calendario(primer_partido_ms)).encode()))
    return c


def test_solo_instantaneas_anteriores_al_primer_partido(tmp_path):
    # Review Focus 5. Primer partido de la semana 5: jueves 2026-10-08 20:15 ET
    # = viernes 2026-10-09 11:15 en Sídney (AEDT).
    ms = int(pd.Timestamp("2026-10-09 00:15", tz="UTC").timestamp() * 1000)
    _snap(tmp_path, 5, "2026-10-06T19-07", ms)
    viernes = _snap(tmp_path, 5, "2026-10-09T08-07", ms)
    _snap(tmp_path, 5, "2026-10-11T20-07", ms)   # domingo: ya empezó el jueves
    _snap(tmp_path, 4, "2026-10-02T08-07", ms)   # semana < 5: fuera
    assert validacion.instantaneas_previas(tmp_path) == {5: viernes}


def test_validar_en_vivo_espera_8_semanas(tmp_path):
    class Falso:
        pass

    res = validacion.validar_en_vivo(Falso(), {}, {"proyecciones": {"players": []}},
                                     tmp_path / "vivo.json")
    assert res == {"semanas": 0, "listo": False} and not (tmp_path / "vivo.json").exists()
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_validacion_vivo.py -q`
Expected: FAIL con `AttributeError: module 'fantasy.modelo.validacion' has no attribute 'instantaneas_previas'`

- [ ] **Step 3: Implementar** (añadir a `validacion.py`; importar `pandas as pd`, `from fantasy.almacen.instantaneas import cargar`, `from fantasy.horario import ZONA`, `from fantasy.ingesta import espn`, `from fantasy.modelo import candidatos, variables`, `from fantasy.modelo.evaluar import relevantes`)

```python
def _hora(carpeta: Path) -> pd.Timestamp:
    return pd.to_datetime(carpeta.name, format="%Y-%m-%dT%H-%M").tz_localize(ZONA)


def _primer_partido(carpeta: Path, semana: int) -> pd.Timestamp | None:
    cal = cargar_solo(carpeta, "calendario")
    inicios = espn.parsear_calendario(cal)
    inicios = inicios[inicios.semana == semana].inicio_utc
    return inicios.min() if len(inicios) else None


def cargar_solo(carpeta: Path, nombre: str) -> dict:
    import gzip
    import json
    return json.loads(gzip.decompress((carpeta / f"{nombre}.json.gz").read_bytes()))


def instantaneas_previas(datos: Path, temporada: int = 2026, desde: int = 5) -> dict[int, Path]:
    raiz = datos / "instantaneas" / str(temporada)
    salida = {}
    for dir_sem in sorted(raiz.glob("sem*")):
        semana = int(dir_sem.name[3:])
        if semana < desde:
            continue
        for carpeta in sorted(dir_sem.iterdir(), reverse=True):
            primero = _primer_partido(carpeta, semana)
            if primero is not None and _hora(carpeta) < primero:
                salida[semana] = carpeta
                break
    return salida


def ultima_instantanea(datos: Path, temporada: int = 2026) -> Path:
    return max((datos / "instantaneas" / str(temporada)).glob("sem*/*"), key=lambda p: p.name)


def validar_en_vivo(modelo, previas: dict, ultimo: dict, destino: Path,
                    min_semanas: int = 8) -> dict:
    reales = espn.parsear_reales(ultimo["proyecciones"], 2026)
    partes = []
    for semana, crudos in sorted(previas.items()):
        f = variables.desde_crudos_v2(crudos, 2026, [semana], equipo_desde_espn=True)
        f = f.drop(columns="real").merge(
            reales[reales.semana == semana][["jugador_id", "puntos"]].rename(
                columns={"puntos": "real"}), on="jugador_id", how="left")
        f = relevantes(f[f.real.notna()])
        if f.empty:
            continue
        partes.append(pd.DataFrame({"semana": semana, "pos": f.pos.values,
                                    "jugador_id": f.jugador_id.values, "real": f.real.values,
                                    "espn": modelo.k * f.proy_espn.values,
                                    "modelo": candidatos.predecir_v2(modelo, f).values}))
    if len(partes) < min_semanas:
        return {"semanas": len(partes), "listo": False}
    pred = pd.concat(partes, ignore_index=True)
    res = _guardar(resumen(pred), destino, {"fuente": "2026 en vivo",
                                            "semanas": sorted(int(s) for s in pred.semana.unique())})
    return {**res, "listo": True}
```


- [ ] **Step 4: CLI `validar-en-vivo`**

```python
    vv = sub.add_parser("validar-en-vivo", help="aplica el criterio a 2026 con las instantáneas")
    vv.add_argument("--datos", type=Path, required=True)
    vv.add_argument("--modelo", type=Path, default=Path("modelos/modelo_v2.joblib"))
    vv.add_argument("--destino", type=Path, default=Path("validacion/2026_vivo.json"))
```
```python
    if a.comando == "validar-en-vivo":
        import json
        from fantasy.modelo import candidatos, validacion
        previas = {s: instantaneas.cargar(c)
                   for s, c in validacion.instantaneas_previas(a.datos).items()}
        res = validacion.validar_en_vivo(candidatos.cargar_v2(a.modelo), previas,
                                         instantaneas.cargar(validacion.ultima_instantanea(a.datos)),
                                         a.destino)
        print(json.dumps(res, indent=1, ensure_ascii=False))
        return 0
```

- [ ] **Step 5: Verificar y commit**

Run: `uv run pytest tests/test_validacion_vivo.py -q && uv run pytest -q && uv run ruff check .`
Expected: 2 passed; suite verde.

```bash
git add src/fantasy/modelo/validacion.py src/fantasy/cli.py tests/test_validacion_vivo.py
git commit -m "feat: validación en vivo con las instantáneas de 2026"
```

---

### Task 9: Cuando el modelo manda (y segunda opinión con v2)

**Files:**
- Create: `src/fantasy/modelo/estado.py`
- Modify: `src/fantasy/proyeccion/modelo.py`, `src/fantasy/reporte/armado.py`, plantilla, `src/fantasy/config.py`
- Test: `tests/test_modelo_manda.py`

**Interfaces:**
- Produces:
  - `config.RUTA_MODELO_V2 = Path("modelos/modelo_v2.joblib")`, `config.RUTA_VALIDACION = Path("validacion")`
  - `estado_validacion(raiz: Path) -> dict` → `{"manda": bool, "fuente": str | None}` (manda si `2025.json` o `2026_vivo.json` existe con `"paso": true`)
  - `segunda_opinion(crudos, temporada, semana, ruta)` acepta `.joblib` (v2, usa `desde_crudos_v2(..., equipo_desde_espn=True)` y `predecir_v2`) o `.json` (v1); sigue sin lanzar nunca.
  - `armar(..., ruta_modelo=None, ruta_validacion=None)`: si `RUTA_MODELO_V2` existe se usa como segunda opinión; si `estado_validacion` dice que manda, en `tablas[semana]` la columna `proy` de los jugadores con predicción se reemplaza por la del modelo (y `esperado = proy · p_jugar`) **antes** de alineación, agencia libre e intercambios; `Reporte` gana `validado: str | None` (fuente) y cada fila de `alineacion` guarda `espn` (proyección de ESPN) además de `modelo`.
  - Plantilla: el banner dice `VALIDADO (<fuente>) — decide el modelo` cuando `validado`, si no el actual; cuando manda, la columna extra se titula "ESPN" y muestra `f.espn`.

- [ ] **Step 1: Pruebas que fallan**

`tests/test_modelo_manda.py`:
```python
import json
import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.modelo.estado import estado_validacion
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def test_estado(tmp_path):
    assert estado_validacion(tmp_path) == {"manda": False, "fuente": None}
    (tmp_path / "2025.json").write_text(json.dumps({"paso": False}), encoding="utf-8")
    assert estado_validacion(tmp_path)["manda"] is False
    (tmp_path / "2026_vivo.json").write_text(json.dumps({"paso": True}), encoding="utf-8")
    assert estado_validacion(tmp_path) == {"manda": True, "fuente": "2026 en vivo"}


def test_sin_validar_sigue_decidiendo_espn(tmp_path):
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_validacion=tmp_path)
    assert r.validado is None
    assert all(f["proy"] == f["espn"] for f in r.alineacion)
    assert "SIN VALIDAR" in generar_html(r)


def test_cuando_manda_decide_el_modelo(tmp_path, monkeypatch):
    (tmp_path / "2025.json").write_text(json.dumps({"paso": True}), encoding="utf-8")

    def prediccion_falsa(crudos, temporada, semana, ruta):
        from fantasy.ingesta import espn
        pr = espn.parsear_proyecciones(crudos["proyecciones"], temporada)
        pr = pr[pr.semana == semana]
        return {int(j): (40.0 if j == pr.jugador_id.iloc[0] else p * 0.5)
                for j, p in zip(pr.jugador_id, pr.puntos, strict=True)}, None

    monkeypatch.setattr("fantasy.reporte.armado.prediccion_modelo", prediccion_falsa)
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_validacion=tmp_path)
    assert r.validado == "2025 sellada"
    assert any(f["proy"] != f["espn"] for f in r.alineacion)
    html = generar_html(r)
    assert "VALIDADO" in html and "SIN VALIDAR" not in html
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_modelo_manda.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fantasy.modelo.estado'`

- [ ] **Step 3: Implementar**

`src/fantasy/modelo/estado.py`:
```python
"""¿Ya pasó el modelo la validación? (decisiones 19 y 23)."""

import json
from pathlib import Path

FUENTES = (("2025.json", "2025 sellada"), ("2026_vivo.json", "2026 en vivo"))


def estado_validacion(raiz: Path) -> dict:
    for archivo, fuente in FUENTES:
        ruta = raiz / archivo
        if ruta.exists():
            try:
                if json.loads(ruta.read_text(encoding="utf-8")).get("paso") is True:
                    return {"manda": True, "fuente": fuente}
            except (ValueError, OSError):
                continue
    return {"manda": False, "fuente": None}
```

En `proyeccion/modelo.py`: dentro del `try`, si `ruta.suffix == ".joblib"` usar
`m = candidatos.cargar_v2(ruta)`, `f = variables.desde_crudos_v2(crudos, temporada, [semana], equipo_desde_espn=True)` y `pred = candidatos.predecir_v2(m, f)`; si no, el camino v1 actual. Para v2 exigir además `"juegos" in crudos` (si falta → aviso "Sin líneas de apuestas: …"). Añadir el alias `prediccion_modelo = segunda_opinion`.

En `config.py`: `RUTA_MODELO_V2 = Path("modelos/modelo_v2.joblib")` y `RUTA_VALIDACION = Path("validacion")`.

En `armado.py`:
- importar `from fantasy.modelo.estado import estado_validacion` y `from fantasy.proyeccion.modelo import prediccion_modelo` (en lugar de `segunda_opinion`); añadir `validado: str | None = None` a `Reporte` y el parámetro `ruta_validacion: Path | None = None` a `armar`.
- Justo después de construir `tablas`, calcular
  `ruta = ruta_modelo or (RUTA_MODELO_V2 if RUTA_MODELO_V2.exists() else RUTA_MODELO)`,
  `modelo, aviso_modelo = prediccion_modelo(crudos, TEMPORADA, semana, ruta)` y
  `estado_val = estado_validacion(ruta_validacion or RUTA_VALIDACION)`;
  guardar `espn_semana = dict(zip(tablas[semana].jugador_id, tablas[semana].proy))`;
  si `estado_val["manda"]` y hay predicciones:
  ```python
      t0 = tablas[semana]
      nueva = t0["jugador_id"].map(modelo)
      t0["proy"] = nueva.where(nueva.notna(), t0["proy"]).clip(lower=0.0)
      t0["esperado"] = t0["proy"] * t0["p_jugar"]
  ```
- En cada fila de `alineacion` añadir `"espn": round(float(espn_semana.get(j, 0.0)), 1)`; `proy` sigue saliendo de `idx` (que ya refleja al modelo cuando manda).
- Pasar `validado=estado_val["fuente"] if estado_val["manda"] else None` al `Reporte`.

En la plantilla:
```html
{% if validado %}<p class="sinvalidar">VALIDADO ({{ validado }}) — decide el modelo</p>
{% else %}<p class="sinvalidar">SIN VALIDAR — decide la proyección de ESPN</p>{% endif %}
```
y en la tabla de alineación, cuando `validado`, la columna extra se titula "ESPN" y muestra `f.espn` (en vez de "Modelo"/`f.modelo`). En `correo.resumen`, cambiar el texto fijo "SIN VALIDAR (decide ESPN)" por `"VALIDADO (decide el modelo)" if r.validado else "SIN VALIDAR (decide ESPN)"`.

- [ ] **Step 4: Verificar**

Run: `uv run pytest -q && uv run ruff check .`
Expected: todo pasa (las pruebas anteriores siguen verdes: sin `validacion/` con `paso: true` nada cambia de comportamiento).

- [ ] **Step 5: Commit**

```bash
git add src/fantasy tests/test_modelo_manda.py
git commit -m "feat: el modelo decide cuando pasa la validación; segunda opinión con el modelo v2"
```

---

### Task 10: Elegir con datos reales, documentar y detenerse

**Files:**
- Create: `validacion/registro.json`, `modelos/modelo_v2.joblib` (generados)
- Modify: `README.md`

- [ ] **Step 1: Selección real**

Run: `uv run fantasy seleccionar | tee docs/seleccion_2024.txt`
Expected: 7 líneas (una por candidato) y "Elegido: …"; `validacion/registro.json` y `modelos/modelo_v2.joblib` creados. El resultado, sea cual sea, **no se ajusta** después de verlo (regla fijada).

- [ ] **Step 2: Prueba de humo del reporte con el modelo v2**

Run: `uv run fantasy reporte --tipo martes --salida salida_prueba --sin-correo --forzar` y revisar que la columna "Modelo" tenga valores razonables y que el banner siga en "SIN VALIDAR". Luego `rm -rf salida_prueba`.

- [ ] **Step 3: README** — sección "Fase 3" con el contenido de `docs/seleccion_2024.txt`, la explicación del protocolo (registro congelado, corrida única de 2025, plan B en vivo) y la línea: "La corrida sellada todavía no se ha ejecutado."

- [ ] **Step 4: Commit y alto**

```bash
git add validacion/registro.json modelos/modelo_v2.joblib docs/seleccion_2024.txt README.md
git commit -m "feat: modelo v2 elegido en 2024 y registro congelado (2025 sin correr)"
```

**Fin del plan.** La corrida `fantasy validar --sellado-final` **no** forma parte de este plan:
se le presenta a Mario el registro y el resultado de 2024, y solo con su visto bueno explícito
se ejecuta, en una sesión aparte, con el repo limpio.
