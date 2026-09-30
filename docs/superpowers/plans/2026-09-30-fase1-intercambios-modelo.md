# Fase 1 — Intercambios y modelo como segunda opinión: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el reporte del martes proponga intercambios (hasta 5, uno por rival) y que la
alineación muestre la proyección de un modelo propio junto a la de ESPN, sin que el modelo
cambie ninguna decisión.

**Architecture:** Sobre la fase 0. `decision/intercambios.py` reutiliza `Valuador`.
`modelo/` (nuevo) construye variables sin fuga, entrena una ridge por posición con
2023–2024 guardados en `historico/`, la evalúa semana por semana contra ESPN y se guarda como
JSON en `modelos/`. `proyeccion/modelo.py` la aplica a la semana en curso para el reporte.

**Tech Stack:** Python 3.12, uv, pandas, scikit-learn (nuevo), Jinja2, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`, secciones 4.3, 6 y
**9 (fase 1, aprobada 2026-09-29)**. Requisitos: `PROYECTO.md`.

## Global Constraints

- Cero costo; nada escribe en ESPN.
- **ESPN decide**; el modelo solo se muestra (decisión 15). Todo reporte sigue diciendo "SIN VALIDAR".
- **2025 está sellado**: ningún código de esta fase baja, lee ni evalúa la temporada 2025.
- Intercambios solo en el reporte del **martes**; nunca con el rival de la semana objetivo.
- Aceptación: Δ alineación del rival (ESPN) ≥ −15 y Δ nombre ≥ −3, nombre = 100·e^(−ADP/45) (ADP ausente = 200).
- Riesgo de veto por desbalance (resto ESPN recibe − da)/da: > 0.25 alto, > 0.10 medio, si no bajo.
- Agencia libre: nunca sugerir soltar a un jugador con ADP < 60.
- Modelo: variables `proy_espn, pts_prev, snaps_prev, targets_prev, acarreos_prev, n_prev`; objetivo = puntos reales de ESPN; filas con `semana_fuente_max >= semana` detienen la corrida.
- Relevantes para el MAE: top 12 QB, 30 RB, 30 WR, 12 TE por proyección de ESPN de esa semana.
- ⚑ cuando |modelo − ESPN| > 3.0 puntos.
- Textos visibles en español.

## Review Focus

1. **Un rival con menos de 5 jugadores con proyección, o una plantilla con IR/espacios vacíos**: la búsqueda no truena y no propone recibir a alguien lesionado sin decirlo. Prueba en la tarea 2.
2. **Un jugador de 2026 sin partidos previos (novato o recién activado)**: el modelo predice sin NaN (usa la proyección de ESPN como `pts_prev`). Prueba en la tarea 6.
3. **Un jugador en nflverse sin `espn_id`, o uno de ESPN sin fila de uso**: no desaparece de la tabla; sus variables de uso quedan en 0 con `n_prev` real. Prueba en la tarea 6.
4. **El modelo JSON no existe en el runner o es de otra versión de variables**: el reporte sale sin la columna "Modelo" y lo avisa, en vez de tronar. Prueba en la tarea 9.
5. **La búsqueda de intercambios tarda demasiado para Actions** (plantillas de 14 contra 6 rivales): debe correr en menos de 90 s en la fixture real. Prueba en la tarea 2 (mide y falla si pasa de 90 s).

---

## Estructura de archivos

```
src/fantasy/
  ingesta/espn.py           + parsear_reales, parsear_adp, rival_de
  ingesta/historico.py      (nuevo) descarga y recorte del histórico 2023–2024
  decision/intercambios.py  (nuevo) búsqueda y evaluación de intercambios
  decision/agencia_libre.py + intocables en recomendar
  modelo/__init__.py        (nuevo)
  modelo/variables.py       (nuevo) filas sin fuga
  modelo/ridge.py           (nuevo) entrenar / predecir / guardar / cargar
  modelo/evaluar.py         (nuevo) walk-forward contra ESPN
  proyeccion/modelo.py      (nuevo) segunda opinión para la semana en curso
  reporte/armado.py, html, plantilla, correo   + intercambios y columna Modelo
  cli.py                    + subcomandos historico, entrenar, evaluar
historico/                  espn_2023.json.gz, espn_2024.json.gz, nflverse_<t>_<nombre>.csv.gz
modelos/modelo_v1.json
tests/fixtures/sem04_2026-09-30/   (ya existe: instantánea real del 2026-09-30)
```

La fixture `sem04_2026-09-30` es la instantánea real que generó `fantasy reporte` el
2026-09-30 11:40 (Sídney): semana objetivo 4, BanKAI (5) contra Norway (7), intercambio con
Chumpi (4) pendiente. Trae puntos reales de las semanas 1–3 de 2026 y ADP en la liga.

---

### Task 1: Datos nuevos de ESPN — puntos reales, ADP y rival de la semana

**Files:**
- Modify: `src/fantasy/ingesta/espn.py`
- Test: `tests/test_espn_extra.py`

**Interfaces:**
- Produces:
  - `parsear_reales(proyecciones: dict, temporada: int) -> pd.DataFrame` columnas `jugador_id, semana, puntos` (statSourceId 0, split 1, semana > 0, sin duplicados)
  - `parsear_adp(liga: dict) -> dict[int, float]` (ADP de cada jugador con dueño; ausente = 200.0)
  - `rival_de(liga: dict, equipo_id: int, semana: int) -> int | None`

- [ ] **Step 1: Pruebas que fallan**

`tests/test_espn_extra.py`:
```python
import pathlib

import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.ingesta import espn

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"


@pytest.fixture(scope="module")
def c():
    return cargar(SEM4)


def _id(c, nombre):
    j = espn.parsear_jugadores(c["proyecciones"], c["liga"], c["agentes_libres"])
    return int(j.loc[j.nombre == nombre, "jugador_id"].iloc[0])


def test_reales_de_2026(c):
    r = espn.parsear_reales(c["proyecciones"], 2026)
    shough = r[r.jugador_id == _id(c, "Tyler Shough")].set_index("semana").puntos
    assert shough.round(1).to_dict() == {1: 23.2, 2: 22.4, 3: 23.8}
    assert not r.duplicated(["jugador_id", "semana"]).any()


def test_adp(c):
    adp = espn.parsear_adp(c["liga"])
    assert adp[_id(c, "Jahmyr Gibbs")] == pytest.approx(1.8, abs=0.05)
    assert adp[_id(c, "Malik Nabers")] == pytest.approx(48.3, abs=0.05)


def test_rival_de_la_semana(c):
    assert espn.rival_de(c["liga"], 5, 4) == 7
    assert espn.rival_de(c["liga"], 4, 4) == 8
    assert espn.rival_de(c["liga"], 5, 99) is None
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_espn_extra.py -q`
Expected: FAIL con `AttributeError: module 'fantasy.ingesta.espn' has no attribute 'parsear_reales'`

- [ ] **Step 3: Implementar** (añadir en `espn.py`, después de `parsear_proyecciones`)

```python
def parsear_reales(proyecciones: dict, temporada: int) -> pd.DataFrame:
    filas = [
        {"jugador_id": pe["id"], "semana": int(s["scoringPeriodId"]),
         "puntos": float(s.get("appliedTotal") or 0.0)}
        for pe in proyecciones.get("players", [])
        for s in pe["player"].get("stats") or []
        if s.get("seasonId") == temporada and s.get("statSourceId") == 0
        and s.get("statSplitTypeId") == 1 and s.get("scoringPeriodId", 0) > 0
    ]
    df = pd.DataFrame(filas, columns=PROYECCIONES).drop_duplicates(["jugador_id", "semana"])
    return validar(df, PROYECCIONES, "reales")


def parsear_adp(liga: dict) -> dict[int, float]:
    adp = {}
    for t in liga["teams"]:
        for e in t["roster"]["entries"]:
            o = e["playerPoolEntry"]["player"].get("ownership") or {}
            adp[e["playerId"]] = float(o.get("averageDraftPosition") or 200.0)
    return adp


def rival_de(liga: dict, equipo_id: int, semana: int) -> int | None:
    for m in liga.get("schedule", []):
        if m.get("matchupPeriodId") != semana:
            continue
        local, visita = m["home"]["teamId"], m.get("away", {}).get("teamId")
        if equipo_id == local:
            return visita
        if equipo_id == visita:
            return local
    return None
```

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_espn_extra.py -q`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/ingesta/espn.py tests/test_espn_extra.py tests/fixtures/sem04_2026-09-30
git commit -m "feat: puntos reales, ADP y rival de la semana desde ESPN"
```

---

### Task 2: Búsqueda de intercambios

**Files:**
- Create: `src/fantasy/decision/intercambios.py`
- Test: `tests/test_intercambios.py`

**Interfaces:**
- Consumes: `Valuador`, `tablas_por_semana` (agencia_libre), `parsear_*` de la tarea 1.
- Produces:
  - `nombre(adp: float | None) -> float`
  - `@dataclass(frozen=True) Propuesta(rival: int, das: tuple[int, ...], recibes: tuple[int, ...], relleno: tuple[int, ...], ganancia: float, delta_rival: float, delta_nombre: float, desbalance: float, riesgo_veto: str)`
  - `buscar(plantillas: pd.DataFrame, jugadores: pd.DataFrame, tablas: dict[int, pd.DataFrame], equipo_id: int, adp: dict[int, float], rival_excluido: int | None, *, top_rival: int = 5, max_das: int = 3, max_recibes: int = 2, n_libres: int = 6, max_propuestas: int = 5, tope: int = 14) -> list[Propuesta]`

- [ ] **Step 1: Pruebas que fallan**

`tests/test_intercambios.py`:
```python
import pathlib
import time

import pandas as pd
import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.decision import intercambios as it
from fantasy.decision.agencia_libre import tablas_por_semana
from fantasy.ingesta import espn

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"


def test_nombre():
    assert it.nombre(0) == pytest.approx(100.0)
    assert it.nombre(45) == pytest.approx(100 / 2.718281828, rel=1e-6)
    assert it.nombre(None) == it.nombre(200)


def _jug(filas):
    base = {"equipo_nfl_id": 1, "lesion": "ACTIVE", "dueno_pct": 50.0, "dueno_cambio": 0.0}
    return pd.DataFrame([{**base, **f} for f in filas])


def _tabla(jug, puntos):
    t = jug.copy()
    t["proy"] = t.jugador_id.map(puntos).fillna(0.0)
    t["p_jugar"] = 1.0
    t["esperado"] = t.proy
    t["inicio_utc"] = pd.Timestamp("2026-10-04 17:00", tz="UTC")
    t["slot"] = "BANCA"
    t["bloqueado"] = False
    return t


def _liga_chica():
    # Mario (5): 3 RB buenos + WR flojos. Rival (4): WR estrella, RB flojos.
    mio = [(1, "QB"), (2, "RB"), (3, "RB"), (4, "RB"), (5, "WR"), (6, "WR"), (7, "TE")]
    suyo = [(11, "QB"), (12, "RB"), (13, "RB"), (14, "WR"), (15, "WR"), (16, "TE")]
    filas = [{"jugador_id": j, "nombre": f"J{j}", "pos": p, "equipo_fantasy_id": 5,
              "disponibilidad": "EQUIPO"} for j, p in mio]
    filas += [{"jugador_id": j, "nombre": f"J{j}", "pos": p, "equipo_fantasy_id": 4,
               "disponibilidad": "EQUIPO"} for j, p in suyo]
    filas += [{"jugador_id": 21, "nombre": "LIBRE", "pos": "RB", "equipo_fantasy_id": 0,
               "disponibilidad": "LIBRE"}]
    jug = _jug(filas)
    puntos = {1: 20, 2: 18, 3: 16, 4: 15, 5: 9, 6: 8, 7: 10,
              11: 20, 12: 8, 13: 7, 14: 22, 15: 12, 16: 10, 21: 6}
    tablas = {w: _tabla(jug, puntos) for w in (4, 5)}
    plantillas = jug[jug.equipo_fantasy_id > 0].rename(columns={"equipo_fantasy_id": "equipo_id"})
    adp = {2: 10.0, 3: 30.0, 4: 50.0, 14: 20.0}
    return plantillas, jug, tablas, adp


def test_propone_rb_de_sobra_por_su_wr_estrella():
    plantillas, jug, tablas, adp = _liga_chica()
    props = it.buscar(plantillas, jug, tablas, 5, adp, None, tope=7)
    mejor = props[0]
    assert mejor.rival == 4 and 14 in mejor.recibes
    assert set(mejor.das) <= {2, 3, 4, 5, 6}
    assert mejor.ganancia > 0
    assert mejor.delta_rival >= -15 and mejor.delta_nombre >= -3
    assert mejor.riesgo_veto in {"bajo", "medio", "alto"}


def test_nunca_propone_al_rival_de_la_semana():
    plantillas, jug, tablas, adp = _liga_chica()
    assert it.buscar(plantillas, jug, tablas, 5, adp, rival_excluido=4, tope=7) == []


def test_riesgo_de_veto():
    assert it.riesgo_veto(0.30) == "alto"
    assert it.riesgo_veto(0.15) == "medio"
    assert it.riesgo_veto(-0.50) == "bajo"


def test_semana4_real_rapido_y_sin_norway():
    # Review Focus 1 y 5
    c = cargar(SEM4)
    liga = c["liga"]
    j = espn.parsear_jugadores(c["proyecciones"], liga, c["agentes_libres"])
    p = espn.parsear_plantillas(liga)
    tablas = tablas_por_semana(
        j, espn.parsear_proyecciones(c["proyecciones"], 2026),
        espn.parsear_calendario(c["calendario"]), p[p.equipo_id == 5].assign(bloqueado=False),
        4, pd.Timestamp("2026-09-30 01:40", tz="UTC"))
    inicio = time.perf_counter()
    props = it.buscar(p, j, tablas, 5, espn.parsear_adp(liga), espn.rival_de(liga, 5, 4))
    assert time.perf_counter() - inicio < 90
    assert 1 <= len(props) <= 5
    assert 7 not in {x.rival for x in props}
    assert len({x.rival for x in props}) == len(props)  # una por rival
    assert all(x.ganancia > 0 for x in props)
    assert [x.ganancia for x in props] == sorted((x.ganancia for x in props), reverse=True)
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_intercambios.py -q`
Expected: FAIL con `ImportError: cannot import name 'intercambios'`

- [ ] **Step 3: Implementar**

`src/fantasy/decision/intercambios.py`:
```python
"""Intercambios: qué dar y qué pedir a cada rival para ganar según ESPN, y que acepten."""

import itertools
import math
from dataclasses import dataclass

import pandas as pd

from fantasy.decision.agencia_libre import Valuador

MIN_DELTA_RIVAL = -15.0
MIN_DELTA_NOMBRE = -3.0


@dataclass(frozen=True)
class Propuesta:
    rival: int
    das: tuple[int, ...]
    recibes: tuple[int, ...]
    relleno: tuple[int, ...]
    ganancia: float
    delta_rival: float
    delta_nombre: float
    desbalance: float
    riesgo_veto: str


def nombre(adp: float | None) -> float:
    return 100.0 * math.exp(-(adp if adp is not None else 200.0) / 45.0)


def riesgo_veto(desbalance: float) -> str:
    if desbalance > 0.25:
        return "alto"
    if desbalance > 0.10:
        return "medio"
    return "bajo"


def buscar(plantillas, jugadores, tablas, equipo_id, adp, rival_excluido, *, top_rival=5,
           max_das=3, max_recibes=2, n_libres=6, max_propuestas=5, tope=14):
    valuador = Valuador(tablas)
    resto = pd.concat(tablas.values()).groupby("jugador_id")["proy"].sum()
    val = lambda ids: valuador.valor(ids)  # noqa: E731
    fama = lambda ids: sum(nombre(adp.get(i)) for i in ids)  # noqa: E731
    total = lambda ids: float(sum(resto.get(i, 0.0) for i in ids))  # noqa: E731

    libres = jugadores[(jugadores.disponibilidad != "EQUIPO") & (jugadores.lesion == "ACTIVE")]
    libres = (libres.assign(r=libres.jugador_id.map(resto).fillna(0.0))
              .sort_values("r", ascending=False).jugador_id.head(n_libres).tolist())

    def rellenar(ids: set[int]) -> tuple[set[int], tuple[int, ...]]:
        ids, agregados = set(ids), []
        while len(ids) < tope:
            opciones = [f for f in libres if f not in ids]
            if not opciones:
                break
            mejor = max(opciones, key=lambda f: val(ids | {f}))
            ids.add(mejor)
            agregados.append(mejor)
        return ids, tuple(agregados)

    def recortar(ids: set[int]) -> set[int]:
        ids = set(ids)
        while len(ids) > tope:
            ids.remove(min(ids, key=lambda x: resto.get(x, 0.0)))
        return ids

    por_equipo = {e: set(g.jugador_id) for e, g in plantillas.groupby("equipo_id")}
    mia = por_equipo[equipo_id]
    base_mia = val(rellenar(mia)[0])
    mejores: list[Propuesta] = []
    for rival, suya in por_equipo.items():
        if rival in (equipo_id, rival_excluido):
            continue
        base_suya = val(suya)
        top = sorted(suya, key=lambda x: -resto.get(x, 0.0))[:top_rival]
        mejor: Propuesta | None = None
        for k2 in range(1, max_recibes + 1):
            for recibes in itertools.combinations(top, k2):
                for k1 in range(1, max_das + 1):
                    for das in itertools.combinations(sorted(mia), k1):
                        d_nombre = fama(das) - fama(recibes)
                        if d_nombre < MIN_DELTA_NOMBRE:
                            continue
                        d_rival = val(recortar((suya - set(recibes)) | set(das))) - base_suya
                        if d_rival < MIN_DELTA_RIVAL:
                            continue
                        nueva, relleno = rellenar((mia - set(das)) | set(recibes))
                        ganancia = round(val(nueva) - base_mia, 6)
                        if ganancia <= 0 or (mejor and ganancia <= mejor.ganancia):
                            continue
                        dar, recibir = total(das), total(recibes)
                        desbalance = (recibir - dar) / max(dar, 1.0)
                        mejor = Propuesta(rival, das, recibes, relleno, ganancia,
                                          round(d_rival, 1), round(d_nombre, 1),
                                          round(desbalance, 3), riesgo_veto(desbalance))
        if mejor:
            mejores.append(mejor)
    mejores.sort(key=lambda x: -x.ganancia)
    return mejores[:max_propuestas]
```

- [ ] **Step 4: Verificar que pasan**

Run: `uv run pytest tests/test_intercambios.py -q --durations=3`
Expected: 4 passed; `test_semana4_real_rapido_y_sin_norway` por debajo de 90 s. Si pasa de 90 s, perfila con `--durations` y reduce `n_libres` o poda por `d_nombre` antes de evaluar al rival; registra la decisión en el ledger.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/intercambios.py tests/test_intercambios.py
git commit -m "feat: búsqueda de intercambios con aceptación del rival y riesgo de veto"
```

---

### Task 3: La agencia libre no suelta moneda de cambio

**Files:**
- Modify: `src/fantasy/decision/agencia_libre.py` (`recomendar`)
- Test: `tests/test_agencia_libre.py` (añadir)

**Interfaces:**
- Produces: `recomendar(..., intocables: set[int] = frozenset())` — los ids en `intocables` nunca aparecen en `soltar`. `ADP_INTOCABLE = 60.0`.

- [ ] **Step 1: Prueba que falla** (añadir al final de `tests/test_agencia_libre.py`)

```python
def test_no_suelta_intocables():
    jug = _jug(_mia() + [{"jugador_id": 99, "nombre": "LIBRE", "pos": "WR"}])
    puntos = {1: 20, 2: 15, 3: 14, 4: 13, 5: 12, 6: 10, 7: 11, 8: 2, 99: 16}
    tablas = {4: _tabla(jug, puntos)}
    r = al.recomendar(jug, tablas, set(range(1, 9)), 4, intocables={8})
    assert 8 not in set(r.soltar)
    assert (r.ganancia > 0).all()
```

- [ ] **Step 2: Verificar que falla**

Run: `uv run pytest tests/test_agencia_libre.py -q -k intocables`
Expected: FAIL con `TypeError: recomendar() got an unexpected keyword argument 'intocables'`

- [ ] **Step 3: Implementar**

En `agencia_libre.py` añadir la constante `ADP_INTOCABLE = 60.0  # nombre alto: sirve para intercambios` junto a `SEGURO`, cambiar la firma a
`def recomendar(jugadores, tablas, mis_ids, semana, *, max_candidatos=30, max_sugerencias=5, intocables=frozenset()):`
y la línea de `soltables` a
`soltables = [j for j in mis_ids if j not in bloqueados and j not in intocables]`.

- [ ] **Step 4: Verificar que pasa y que la suite sigue verde**

Run: `uv run pytest -q`
Expected: todo pasa.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/agencia_libre.py tests/test_agencia_libre.py
git commit -m "feat: la agencia libre no sugiere soltar jugadores con nombre (ADP < 60)"
```

---

### Task 4: Intercambios e intocables en el reporte

**Files:**
- Modify: `src/fantasy/reporte/armado.py`, `src/fantasy/reporte/plantillas/reporte.html.j2`, `src/fantasy/reporte/correo.py`
- Test: `tests/test_reporte_fase1.py`

**Interfaces:**
- Consumes: `intercambios.buscar`, `parsear_adp`, `rival_de`, `ADP_INTOCABLE`.
- Produces: `Reporte.intercambios: list[dict]` (vacía salvo el martes) con llaves `rival, das, recibes, relleno, ganancia, riesgo, lesiones` (nombres de equipo/jugadores ya resueltos; `lesiones` = estados en español de los que recibes que no están sanos).

- [ ] **Step 1: Pruebas que fallan**

`tests/test_reporte_fase1.py`:
```python
import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte import correo
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def test_martes_trae_intercambios():
    r = armar(cargar(SEM4), MARTES, "martes", 5)
    assert 1 <= len(r.intercambios) <= 5
    assert "Norway Ass" not in {x["rival"] for x in r.intercambios}
    x = r.intercambios[0]
    assert x["das"] and x["recibes"] and x["ganancia"] > 0
    html = generar_html(r)
    assert "Intercambios" in html and "propón una a la vez" in html
    assert x["recibes"][0] in html
    assert "Intercambio:" in correo.resumen(r)


def test_viernes_no_trae_intercambios():
    r = armar(cargar(SEM4), MARTES, "viernes", 5)
    assert r.intercambios == []
    assert "propón una a la vez" not in generar_html(r)


def test_agencia_no_suelta_a_nabers():
    r = armar(cargar(SEM4), MARTES, "martes", 5)
    assert "Malik Nabers" not in {a["soltar"] for a in r.agencia}
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_reporte_fase1.py -q`
Expected: FAIL con `AttributeError: 'Reporte' object has no attribute 'intercambios'`

- [ ] **Step 3: Implementar en `armado.py`**

Imports nuevos:
```python
from fantasy.decision import intercambios as intercambios_mod
from fantasy.decision.agencia_libre import ADP_INTOCABLE
```
En `Reporte`, antes de `avisos`, añadir `intercambios: list[dict] = field(default_factory=list)`.
Después de calcular `mis_ids`, calcular `adp = espn.parsear_adp(liga)` y `intocables = {j for j in mis_ids if adp.get(j, 200.0) < ADP_INTOCABLE}`, y pasar `intocables=intocables` a `agencia_libre.recomendar`.
Antes del `return`, añadir:
```python
    propuestas: list[dict] = []
    if tipo == "martes":
        equipos = {t["id"]: t["name"].strip() for t in liga["teams"]}
        rival = espn.rival_de(liga, equipo_id, semana)
        for x in intercambios_mod.buscar(plantillas, jugadores, tablas, equipo_id, adp, rival):
            propuestas.append({
                "rival": equipos[x.rival],
                "das": [nombres[i] for i in x.das],
                "recibes": [nombres[i] for i in x.recibes],
                "relleno": [nombres[i] for i in x.relleno],
                "ganancia": round(x.ganancia, 1),
                "riesgo": x.riesgo_veto,
                "lesiones": [f"{nombres[i]} ({estado(por_id.loc[i, 'lesion'])})"
                             for i in x.recibes if por_id.loc[i, "lesion"] != "ACTIVE"],
            })
```
y pasar `intercambios=propuestas` al constructor de `Reporte`.

- [ ] **Step 4: Plantilla** (insertar antes de `<h2>Ganando rol</h2>`)

```html
{% if intercambios %}
<h2>Intercambios</h2>
<table>
  <tr><th>Rival</th><th>Das</th><th>Recibes</th><th class="num">Ganancia</th><th>Veto</th></tr>
  {% for x in intercambios %}
  <tr><td>{{ x.rival }}</td><td>{{ x.das | join(", ") }}</td>
      <td>{{ x.recibes | join(", ") }}{% if x.lesiones %} <strong>{{ x.lesiones | join(", ") }}</strong>{% endif %}
          {% if x.relleno %}<br><small>y tomas de la agencia libre: {{ x.relleno | join(", ") }}</small>{% endif %}</td>
      <td class="num">+{{ x.ganancia }}</td><td>{{ x.riesgo }}</td></tr>
  {% endfor %}
</table>
<p class="suave">Una propuesta por rival; propón una a la vez. Ganancia: puntos proyectados extra de aquí a la semana 17. Ninguna es con tu rival de esta semana.</p>
{% endif %}
```

- [ ] **Step 5: Correo** (en `resumen`, después de la línea de agencia libre)

```python
    if r.intercambios:
        x = r.intercambios[0]
        lineas.append(f"Intercambio: das {', '.join(x['das'])} a {x['rival']} por "
                      f"{', '.join(x['recibes'])} (+{x['ganancia']}, veto {x['riesgo']})")
```

- [ ] **Step 6: Verificar**

Run: `uv run pytest -q && uv run ruff check .`
Expected: todo pasa.

- [ ] **Step 7: Commit**

```bash
git add src/fantasy/reporte tests/test_reporte_fase1.py
git commit -m "feat: intercambios en el reporte del martes; la agencia libre protege a los de nombre"
```

---

### Task 5: Histórico 2023–2024

**Files:**
- Create: `src/fantasy/ingesta/historico.py`
- Modify: `src/fantasy/cli.py` (subcomando `historico`)
- Test: `tests/test_historico.py`

**Interfaces:**
- Consumes: `obtener_json`, `bajar_nflverse`.
- Produces:
  - `TEMPORADAS_ENTRENAMIENTO = (2023, 2024)`; `SELLADA = 2025`
  - `bajar_espn_historico(temporada: int, *, get=obtener_json) -> dict` (recortado: por jugador `id`, `player.{id, fullName, defaultPositionId, proTeamId}`, y solo stats de esa temporada con split 1 y fuente 0 o 1, con `seasonId, scoringPeriodId, statSourceId, statSplitTypeId, appliedTotal`)
  - `guardar_historico(raiz: Path, temporada: int, espn: dict, nflverse: dict[str, str]) -> None` → `raiz/espn_<t>.json.gz` y `raiz/nflverse_<t>_<nombre>.csv.gz`
  - `cargar_historico(raiz: Path, temporada: int) -> dict` con llaves `proyecciones` (el dict de ESPN) y `semanal`, `snaps`, `jugadores` (texto CSV)
  - Cualquier función que reciba `temporada == 2025` lanza `ValueError("2025 está sellada …")`.
  - CLI: `fantasy historico [--raiz historico]` baja 2023 y 2024.

- [ ] **Step 1: Pruebas que fallan**

`tests/test_historico.py`:
```python
import pytest

from fantasy.ingesta import historico


def _get_falso(url, filtro=None):
    assert "leaguedefaults/3" in url and filtro["players"]["limit"] >= 1000
    return {"players": [{"id": 1, "player": {
        "id": 1, "fullName": "A", "defaultPositionId": 3, "proTeamId": 9, "extra": "x",
        "stats": [
            {"seasonId": 2024, "scoringPeriodId": 3, "statSourceId": 1, "statSplitTypeId": 1,
             "appliedTotal": 12.5, "stats": {"53": 5}},
            {"seasonId": 2024, "scoringPeriodId": 3, "statSourceId": 0, "statSplitTypeId": 1,
             "appliedTotal": 15.0, "stats": {}},
            {"seasonId": 2024, "scoringPeriodId": 0, "statSourceId": 1, "statSplitTypeId": 0,
             "appliedTotal": 200.0, "stats": {}},
            {"seasonId": 2023, "scoringPeriodId": 3, "statSourceId": 0, "statSplitTypeId": 1,
             "appliedTotal": 1.0, "stats": {}},
        ]}}]}


def test_bajar_recorta_lo_que_no_se_usa():
    d = historico.bajar_espn_historico(2024, get=_get_falso)
    p = d["players"][0]["player"]
    assert "extra" not in p
    assert [s["statSourceId"] for s in p["stats"]] == [1, 0]
    assert all("stats" not in s for s in p["stats"])


def test_2025_esta_sellada(tmp_path):
    with pytest.raises(ValueError, match="sellada"):
        historico.bajar_espn_historico(2025, get=_get_falso)
    with pytest.raises(ValueError, match="sellada"):
        historico.cargar_historico(tmp_path, 2025)


def test_guardar_y_cargar(tmp_path):
    espn = historico.bajar_espn_historico(2024, get=_get_falso)
    historico.guardar_historico(tmp_path, 2024, espn, {"semanal": "a\n1\n", "snaps": "b\n2\n",
                                                       "jugadores": "c\n3\n"})
    c = historico.cargar_historico(tmp_path, 2024)
    assert c["proyecciones"] == espn and c["snaps"] == "b\n2\n"
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_historico.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar**

`src/fantasy/ingesta/historico.py`:
```python
"""Histórico para entrenar el modelo: 2023–2024. 2025 está sellada (validación final)."""

import gzip
import json
from pathlib import Path

from fantasy.ingesta.espn import LECTURA, obtener_json

TEMPORADAS_ENTRENAMIENTO = (2023, 2024)
SELLADA = 2025
CAMPOS_JUGADOR = ("id", "fullName", "defaultPositionId", "proTeamId")
CAMPOS_STAT = ("seasonId", "scoringPeriodId", "statSourceId", "statSplitTypeId", "appliedTotal")
NFLVERSE = ("semanal", "snaps", "jugadores")


def _no_sellada(temporada: int) -> None:
    if temporada >= SELLADA:
        raise ValueError(f"{temporada}: 2025 está sellada para la validación final (decisión 20)")


def bajar_espn_historico(temporada: int, *, get=obtener_json) -> dict:
    _no_sellada(temporada)
    crudo = get(f"{LECTURA}/{temporada}/segments/0/leaguedefaults/3?view=kona_player_info",
                {"players": {"filterSlotIds": {"value": [0, 2, 4, 6]}, "limit": 1500,
                             "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})
    jugadores = []
    for pe in crudo.get("players", []):
        p = pe["player"]
        stats = [{k: s.get(k) for k in CAMPOS_STAT} for s in p.get("stats") or []
                 if s.get("seasonId") == temporada and s.get("statSplitTypeId") == 1
                 and s.get("statSourceId") in (0, 1)]
        jugadores.append({"id": pe["id"],
                          "player": {**{k: p.get(k) for k in CAMPOS_JUGADOR}, "stats": stats}})
    return {"players": jugadores}


def guardar_historico(raiz: Path, temporada: int, espn: dict, nflverse: dict[str, str]) -> None:
    _no_sellada(temporada)
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / f"espn_{temporada}.json.gz").write_bytes(
        gzip.compress(json.dumps(espn, ensure_ascii=False).encode("utf-8")))
    for nombre in NFLVERSE:
        (raiz / f"nflverse_{temporada}_{nombre}.csv.gz").write_bytes(
            gzip.compress(nflverse[nombre].encode("utf-8")))


def cargar_historico(raiz: Path, temporada: int) -> dict:
    _no_sellada(temporada)
    datos = {"proyecciones": json.loads(
        gzip.decompress((raiz / f"espn_{temporada}.json.gz").read_bytes()))}
    for nombre in NFLVERSE:
        datos[nombre] = gzip.decompress(
            (raiz / f"nflverse_{temporada}_{nombre}.csv.gz").read_bytes()).decode("utf-8")
    return datos
```

En `cli.py`, en `_parser()` añadir:
```python
    h = sub.add_parser("historico", help="baja 2023–2024 para entrenar el modelo")
    h.add_argument("--raiz", type=Path, default=Path("historico"))
```
y al inicio de `main`, después de `a = _parser().parse_args(argv)`:
```python
    if a.comando == "historico":
        from fantasy.ingesta import historico
        for t in historico.TEMPORADAS_ENTRENAMIENTO:
            historico.guardar_historico(a.raiz, t, historico.bajar_espn_historico(t),
                                        bajar_nflverse(t))
            print(f"Histórico {t} guardado en {a.raiz}")
        return 0
```

- [ ] **Step 4: Verificar**

Run: `uv run pytest tests/test_historico.py -q && uv run pytest -q`
Expected: 3 passed; suite verde.

- [ ] **Step 5: Bajar el histórico real (con red) y revisar tamaño**

Run: `uv run fantasy historico && du -sh historico && ls historico`
Expected: 8 archivos (`espn_2023.json.gz`, `espn_2024.json.gz`, 6 de nflverse), menos de 15 MB en total.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/ingesta/historico.py src/fantasy/cli.py tests/test_historico.py historico
git commit -m "feat: histórico 2023–2024 recortado y versionado para entrenar (2025 sellada)"
```

---

### Task 6: Variables sin fuga

**Files:**
- Create: `src/fantasy/modelo/__init__.py` (vacío), `src/fantasy/modelo/variables.py`
- Test: `tests/test_variables.py`

**Interfaces:**
- Consumes: `parsear_proyecciones`, `parsear_reales`, `nflverse.tablas`, `POSICIONES`.
- Produces:
  - `VARIABLES = ["proy_espn", "pts_prev", "snaps_prev", "targets_prev", "acarreos_prev", "n_prev"]`
  - `class FugaDeDatos(Exception)`
  - `filas(proy: pd.DataFrame, reales: pd.DataFrame, uso: pd.DataFrame, pos: pd.Series, temporada: int, semanas: list[int] | None = None) -> pd.DataFrame` con columnas `jugador_id, temporada, semana, pos, *VARIABLES, semana_fuente_max, real` (`real` NaN si no jugó o es futuro). `pos` es una Serie `jugador_id → "QB"|"RB"|"WR"|"TE"`.
  - `verificar_sin_fuga(f: pd.DataFrame) -> None`
  - `desde_crudos(crudos: dict, temporada: int, semanas: list[int] | None = None) -> pd.DataFrame` (usa `proyecciones` de ESPN y, si están, `semanal/snaps/jugadores`)

- [ ] **Step 1: Pruebas que fallan**

`tests/test_variables.py`:
```python
import pandas as pd
import pytest

from fantasy.modelo import variables as v


def _datos():
    proy = pd.DataFrame({"jugador_id": [1, 1, 1, 2, 2, 2], "semana": [1, 2, 3] * 2,
                         "puntos": [10.0, 11.0, 12.0, 5.0, 6.0, 7.0]})
    reales = pd.DataFrame({"jugador_id": [1, 1], "semana": [1, 2], "puntos": [20.0, 10.0]})
    uso = pd.DataFrame({"jugador_id": [1, 1], "semana": [1, 2], "snaps_pct": [0.8, 0.6],
                        "targets": [6, 4], "acarreos": [0, 2]})
    pos = pd.Series({1: "WR", 2: "RB"})
    return proy, reales, uso, pos


def test_solo_usa_semanas_anteriores():
    f = v.filas(*_datos(), 2026).set_index(["jugador_id", "semana"])
    s3 = f.loc[(1, 3)]
    assert s3.pts_prev == pytest.approx(15.0) and s3.n_prev == 2
    assert s3.snaps_prev == pytest.approx(0.7) and s3.targets_prev == pytest.approx(5.0)
    assert s3.semana_fuente_max == 2 and pd.isna(s3.real)
    assert f.loc[(1, 2)].pts_prev == pytest.approx(20.0) and f.loc[(1, 2)].real == 10.0
    v.verificar_sin_fuga(f.reset_index())


def test_sin_partidos_previos_no_deja_nan():
    # Review Focus 2 y 3: el jugador 2 nunca jugó y no tiene uso.
    f = v.filas(*_datos(), 2026).set_index(["jugador_id", "semana"])
    s = f.loc[(2, 3)]
    assert s.n_prev == 0 and s.pts_prev == pytest.approx(7.0)  # su proyección de ESPN
    assert s.snaps_prev == 0 and s.targets_prev == 0
    assert not f[v.VARIABLES].isna().any().any()


def test_fuga_detiene():
    f = v.filas(*_datos(), 2026)
    f.loc[0, "semana_fuente_max"] = f.loc[0, "semana"]
    with pytest.raises(v.FugaDeDatos):
        v.verificar_sin_fuga(f)


def test_desde_crudos_de_la_fixture():
    import pathlib

    from fantasy.almacen.instantaneas import cargar
    c = cargar(pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30")
    f = v.desde_crudos(c, 2026, semanas=[4])
    assert len(f) > 200 and (f.semana == 4).all()
    assert not f[v.VARIABLES].isna().any().any()
    assert (f.n_prev <= 3).all()
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_variables.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fantasy.modelo'`

- [ ] **Step 3: Implementar**

`src/fantasy/modelo/variables.py`:
```python
"""Filas para el modelo: para la semana w, solo información de semanas anteriores."""

import pandas as pd

from fantasy.ingesta import espn, nflverse

VARIABLES = ["proy_espn", "pts_prev", "snaps_prev", "targets_prev", "acarreos_prev", "n_prev"]


class FugaDeDatos(Exception):
    """Una variable usa información de la semana que se predice o posterior."""


def filas(proy, reales, uso, pos, temporada, semanas=None):
    semanas = sorted(semanas or proy.semana.unique())
    salida = []
    for w in semanas:
        base = proy.loc[proy.semana == w, ["jugador_id", "puntos"]].rename(
            columns={"puntos": "proy_espn"})
        antes = reales[reales.semana < w]
        g = antes.groupby("jugador_id").agg(pts_prev=("puntos", "mean"),
                                           n_prev=("puntos", "size"),
                                           fuente_r=("semana", "max"))
        u = uso[uso.semana < w].groupby("jugador_id").agg(
            snaps_prev=("snaps_pct", "mean"), targets_prev=("targets", "mean"),
            acarreos_prev=("acarreos", "mean"), fuente_u=("semana", "max"))
        f = base.merge(g, on="jugador_id", how="left").merge(u, on="jugador_id", how="left")
        f["n_prev"] = f["n_prev"].fillna(0).astype(int)
        f["pts_prev"] = f["pts_prev"].fillna(f["proy_espn"])
        f[["snaps_prev", "targets_prev", "acarreos_prev"]] = (
            f[["snaps_prev", "targets_prev", "acarreos_prev"]].fillna(0.0))
        f["semana_fuente_max"] = f[["fuente_r", "fuente_u"]].max(axis=1).fillna(0).astype(int)
        real = reales.loc[reales.semana == w, ["jugador_id", "puntos"]].rename(
            columns={"puntos": "real"})
        f = f.merge(real, on="jugador_id", how="left")
        f["temporada"], f["semana"] = temporada, w
        f["pos"] = f["jugador_id"].map(pos)
        salida.append(f)
    out = pd.concat(salida, ignore_index=True) if salida else pd.DataFrame()
    out = out[out["pos"].notna()]
    cols = ["jugador_id", "temporada", "semana", "pos", *VARIABLES, "semana_fuente_max", "real"]
    out = out[cols].reset_index(drop=True)
    verificar_sin_fuga(out)
    return out


def verificar_sin_fuga(f: pd.DataFrame) -> None:
    malas = f[f["semana_fuente_max"] >= f["semana"]]
    if len(malas):
        raise FugaDeDatos(f"{len(malas)} filas usan datos de su propia semana o posteriores")


def desde_crudos(crudos: dict, temporada: int, semanas=None) -> pd.DataFrame:
    proy = espn.parsear_proyecciones(crudos["proyecciones"], temporada)
    reales = espn.parsear_reales(crudos["proyecciones"], temporada)
    pos = pd.Series({pe["id"]: espn.POSICIONES.get(pe["player"].get("defaultPositionId"))
                     for pe in crudos["proyecciones"]["players"]}).dropna()
    if all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        uso = nflverse.tablas(crudos)
    else:
        uso = pd.DataFrame(columns=["jugador_id", "semana", "snaps_pct", "targets", "acarreos"])
    return filas(proy, reales, uso, pos, temporada, semanas)
```

- [ ] **Step 4: Verificar**

Run: `uv run pytest tests/test_variables.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/modelo tests/test_variables.py
git commit -m "feat: variables del modelo sin fuga (solo semanas anteriores)"
```

---

### Task 7: Ridge por posición

**Files:**
- Modify: `pyproject.toml` (dependencia `scikit-learn>=1.5`), `uv.lock`
- Create: `src/fantasy/modelo/ridge.py`
- Test: `tests/test_ridge.py`

**Interfaces:**
- Produces:
  - `@dataclass Modelo(por_pos: dict[str, dict], variables: list[str], entrenado_con: list[int], version: int = 1)`
  - `entrenar(f: pd.DataFrame, alpha: float = 10.0) -> Modelo` (usa filas con `real` no nulo y `proy_espn > 0`; llama `verificar_sin_fuga`)
  - `predecir(m: Modelo, f: pd.DataFrame) -> pd.Series` (índice de `f`; NaN para posiciones sin modelo)
  - `guardar(m: Modelo, ruta: Path) -> None`, `cargar(ruta: Path) -> Modelo` (lanza `ValueError` si `variables` no coincide con `VARIABLES`)

- [ ] **Step 1: Dependencia**

Run: `uv add "scikit-learn>=1.5"`
Expected: `pyproject.toml` y `uv.lock` actualizados.

- [ ] **Step 2: Pruebas que fallan**

`tests/test_ridge.py`:
```python
import numpy as np
import pandas as pd
import pytest

from fantasy.modelo import ridge
from fantasy.modelo.variables import VARIABLES, FugaDeDatos


def _sinteticas(n=400, semilla=0):
    r = np.random.default_rng(semilla)
    f = pd.DataFrame({
        "jugador_id": np.arange(n), "temporada": 2024, "semana": 5,
        "pos": np.where(np.arange(n) % 2, "WR", "RB"),
        "proy_espn": r.uniform(5, 20, n), "pts_prev": r.uniform(0, 25, n),
        "snaps_prev": r.uniform(0, 1, n), "targets_prev": r.uniform(0, 10, n),
        "acarreos_prev": r.uniform(0, 15, n), "n_prev": r.integers(0, 4, n),
        "semana_fuente_max": 4,
    })
    f["real"] = 1.0 * f.proy_espn + 0.5 * f.targets_prev + r.normal(0, 0.5, n)
    return f


def test_aprende_la_relacion():
    f = _sinteticas()
    m = ridge.entrenar(f, alpha=0.1)
    pred = ridge.predecir(m, f)
    assert np.abs(pred - f.real).mean() < 1.0
    assert set(m.por_pos) == {"RB", "WR"}


def test_guardar_y_cargar(tmp_path):
    f = _sinteticas()
    m = ridge.entrenar(f)
    ridge.guardar(m, tmp_path / "m.json")
    m2 = ridge.cargar(tmp_path / "m.json")
    assert np.allclose(ridge.predecir(m, f), ridge.predecir(m2, f))


def test_version_de_variables_distinta_falla(tmp_path):
    m = ridge.entrenar(_sinteticas())
    m.variables = ["otra"]
    ridge.guardar(m, tmp_path / "m.json")
    with pytest.raises(ValueError, match="variables"):
        ridge.cargar(tmp_path / "m.json")


def test_no_entrena_con_fuga():
    f = _sinteticas()
    f.loc[0, "semana_fuente_max"] = 5
    with pytest.raises(FugaDeDatos):
        ridge.entrenar(f)


def test_posicion_sin_modelo_da_nan():
    m = ridge.entrenar(_sinteticas())
    f = _sinteticas(4).assign(pos="QB")
    assert ridge.predecir(m, f).isna().all()
    assert VARIABLES == m.variables
```

- [ ] **Step 3: Verificar que fallan**

Run: `uv run pytest tests/test_ridge.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 4: Implementar**

`src/fantasy/modelo/ridge.py`:
```python
"""Ridge por posición sobre variables estandarizadas; se guarda como JSON legible."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from fantasy.modelo.variables import VARIABLES, verificar_sin_fuga


@dataclass
class Modelo:
    por_pos: dict[str, dict]
    variables: list[str] = field(default_factory=lambda: list(VARIABLES))
    entrenado_con: list[int] = field(default_factory=list)
    version: int = 1


def entrenar(f: pd.DataFrame, alpha: float = 10.0) -> Modelo:
    verificar_sin_fuga(f)
    datos = f[f["real"].notna() & (f["proy_espn"] > 0)]
    por_pos = {}
    for pos, g in datos.groupby("pos"):
        x = g[VARIABLES].to_numpy(dtype=float)
        media, escala = x.mean(axis=0), x.std(axis=0)
        escala[escala == 0] = 1.0
        r = Ridge(alpha=alpha).fit((x - media) / escala, g["real"].to_numpy(dtype=float))
        por_pos[pos] = {"coef": r.coef_.tolist(), "intercepto": float(r.intercept_),
                        "media": media.tolist(), "escala": escala.tolist(), "n": int(len(g))}
    return Modelo(por_pos=por_pos, entrenado_con=sorted(int(t) for t in datos.temporada.unique()))


def predecir(m: Modelo, f: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=f.index, dtype=float)
    for pos, p in m.por_pos.items():
        mask = f["pos"] == pos
        if not mask.any():
            continue
        x = (f.loc[mask, VARIABLES].to_numpy(dtype=float) - np.array(p["media"])) / np.array(
            p["escala"])
        pred[mask] = x @ np.array(p["coef"]) + p["intercepto"]
    return pred


def guardar(m: Modelo, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(asdict(m), indent=1), encoding="utf-8")


def cargar(ruta: Path) -> Modelo:
    m = Modelo(**json.loads(ruta.read_text(encoding="utf-8")))
    if m.variables != VARIABLES:
        raise ValueError(f"el modelo usa variables {m.variables}, se esperaban {VARIABLES}")
    return m
```

- [ ] **Step 5: Verificar**

Run: `uv run pytest tests/test_ridge.py -q && uv run pytest -q`
Expected: 5 passed; suite verde.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/fantasy/modelo/ridge.py tests/test_ridge.py
git commit -m "feat: ridge por posición con guardado en JSON"
```

---

### Task 8: Evaluación preliminar (walk-forward 2024) y entrenamiento

**Files:**
- Create: `src/fantasy/modelo/evaluar.py`
- Modify: `src/fantasy/cli.py` (subcomandos `entrenar` y `evaluar`)
- Test: `tests/test_evaluar.py`

**Interfaces:**
- Consumes: `variables.desde_crudos`, `ridge.*`, `historico.cargar_historico`.
- Produces:
  - `TOPES = {"QB": 12, "RB": 30, "WR": 30, "TE": 12}`
  - `relevantes(f: pd.DataFrame) -> pd.DataFrame` (por semana y posición, los top por `proy_espn`)
  - `walk_forward(previas: pd.DataFrame, actual: pd.DataFrame, semanas=range(3, 18), alpha=10.0) -> pd.DataFrame` con columnas `semana, pos, jugador_id, real, espn, modelo`
  - `resumen(pred: pd.DataFrame, semilla: int = 0, n: int = 2000) -> dict` con `mae_modelo, mae_espn, delta, ic95: (lo, hi), por_pos: {pos: (mae_modelo, mae_espn)}`
  - CLI: `fantasy entrenar [--raiz historico] [--salida modelos/modelo_v1.json]` y `fantasy evaluar --temporada 2024 [--raiz historico]` (con 2025 sale con error "sellada").

- [ ] **Step 1: Pruebas que fallan**

`tests/test_evaluar.py`:
```python
import numpy as np
import pandas as pd
import pytest

from fantasy.cli import main
from fantasy.modelo import evaluar


def _temporada(temporada, semilla):
    r = np.random.default_rng(semilla)
    filas = []
    for w in range(1, 18):
        for j in range(80):
            proy = 5 + (j % 20)
            filas.append({"jugador_id": j, "temporada": temporada, "semana": w,
                          "pos": ["QB", "RB", "WR", "TE"][j % 4], "proy_espn": proy,
                          "pts_prev": proy, "snaps_prev": 0.7, "targets_prev": j % 7,
                          "acarreos_prev": 0.0, "n_prev": w - 1, "semana_fuente_max": w - 1,
                          "real": proy + 0.8 * (j % 7) - 2 + r.normal(0, 1)})
    return pd.DataFrame(filas)


def test_modelo_que_corrige_a_espn_gana():
    pred = evaluar.walk_forward(_temporada(2023, 0), _temporada(2024, 1))
    res = evaluar.resumen(pred)
    assert set(pred.semana) == set(range(3, 18))
    assert res["delta"] < 0 and res["ic95"][1] < 0
    assert set(res["por_pos"]) == {"QB", "RB", "WR", "TE"}


def test_relevantes_respeta_topes():
    f = _temporada(2024, 0).rename(columns={})
    r = evaluar.relevantes(f[f.semana == 5])
    assert r.groupby("pos").size().to_dict() == {"QB": 12, "RB": 20, "TE": 12, "WR": 20}


def test_evaluar_2025_rechazado():
    assert main(["evaluar", "--temporada", "2025"]) == 2
```

(En `_temporada` hay 20 jugadores por posición, por eso RB y WR quedan en 20 aunque el tope sea 30.)

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_evaluar.py -q`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar `evaluar.py`**

```python
"""Evaluación preliminar semana por semana contra ESPN (no es la validación oficial)."""

import numpy as np
import pandas as pd

from fantasy.modelo import ridge

TOPES = {"QB": 12, "RB": 30, "WR": 30, "TE": 12}


def relevantes(f: pd.DataFrame) -> pd.DataFrame:
    partes = [g.nlargest(TOPES.get(pos, 0), "proy_espn")
              for (_, pos), g in f.groupby(["semana", "pos"])]
    return pd.concat(partes) if partes else f.iloc[0:0]


def walk_forward(previas, actual, semanas=range(3, 18), alpha=10.0):
    salida = []
    for w in semanas:
        entreno = pd.concat([previas, actual[actual.semana < w]], ignore_index=True)
        m = ridge.entrenar(entreno, alpha=alpha)
        prueba = relevantes(actual[(actual.semana == w) & actual.real.notna()])
        if prueba.empty:
            continue
        salida.append(pd.DataFrame({
            "semana": w, "pos": prueba.pos.values, "jugador_id": prueba.jugador_id.values,
            "real": prueba.real.values, "espn": prueba.proy_espn.values,
            "modelo": ridge.predecir(m, prueba).values}))
    return pd.concat(salida, ignore_index=True)


def resumen(pred, semilla=0, n=2000):
    pred = pred.dropna(subset=["modelo"])
    e = pred.assign(em=(pred.modelo - pred.real).abs(), ee=(pred.espn - pred.real).abs())
    por_semana = e.groupby("semana")[["em", "ee"]].sum()
    conteo = e.groupby("semana").size()
    rng = np.random.default_rng(semilla)
    semanas = por_semana.index.to_numpy()
    deltas = []
    for _ in range(n):
        s = rng.choice(semanas, size=len(semanas), replace=True)
        deltas.append((por_semana.loc[s, "em"].sum() - por_semana.loc[s, "ee"].sum())
                      / conteo.loc[s].sum())
    return {
        "mae_modelo": float(e.em.mean()), "mae_espn": float(e.ee.mean()),
        "delta": float(e.em.mean() - e.ee.mean()),
        "ic95": (float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))),
        "por_pos": {p: (float(g.em.mean()), float(g.ee.mean())) for p, g in e.groupby("pos")},
    }
```

- [ ] **Step 4: CLI**

En `_parser()`:
```python
    en = sub.add_parser("entrenar", help="entrena el modelo con 2023–2024")
    en.add_argument("--raiz", type=Path, default=Path("historico"))
    en.add_argument("--salida", type=Path, default=Path("modelos/modelo_v1.json"))
    ev = sub.add_parser("evaluar", help="walk-forward contra ESPN (preliminar)")
    ev.add_argument("--temporada", type=int, required=True)
    ev.add_argument("--raiz", type=Path, default=Path("historico"))
```
En `main`, junto al bloque de `historico`:
```python
    if a.comando in ("entrenar", "evaluar"):
        from fantasy.ingesta import historico
        from fantasy.modelo import evaluar, ridge, variables
        if a.comando == "evaluar" and a.temporada >= historico.SELLADA:
            print("2025 está sellada para la validación final (decisión 20).", file=sys.stderr)
            return 2
        tablas = {t: variables.desde_crudos(historico.cargar_historico(a.raiz, t), t)
                  for t in historico.TEMPORADAS_ENTRENAMIENTO}
        if a.comando == "entrenar":
            m = ridge.entrenar(pd.concat(tablas.values(), ignore_index=True))
            ridge.guardar(m, a.salida)
            print(f"Modelo guardado en {a.salida} ({', '.join(map(str, m.entrenado_con))})")
            return 0
        previas = pd.concat([f for t, f in tablas.items() if t < a.temporada], ignore_index=True)
        res = evaluar.resumen(evaluar.walk_forward(previas, tablas[a.temporada]))
        print(f"MAE modelo {res['mae_modelo']:.2f} · ESPN {res['mae_espn']:.2f} · "
              f"delta {res['delta']:+.2f} (IC95 {res['ic95'][0]:+.2f} a {res['ic95'][1]:+.2f})")
        for pos, (mm, me) in sorted(res["por_pos"].items()):
            print(f"  {pos}: modelo {mm:.2f} · ESPN {me:.2f}")
        return 0
```

- [ ] **Step 5: Verificar**

Run: `uv run pytest tests/test_evaluar.py -q && uv run pytest -q`
Expected: 3 passed; suite verde.

- [ ] **Step 6: Entrenar y evaluar con el histórico real**

Run: `uv run fantasy entrenar && uv run fantasy evaluar --temporada 2024 | tee docs/evaluacion_preliminar_2024.txt`
Expected: `modelos/modelo_v1.json` creado; una línea de MAE global y una por posición. Sea cual sea el resultado, se guarda tal cual (es preliminar y no decide nada).

- [ ] **Step 7: Commit**

```bash
git add src/fantasy/modelo/evaluar.py src/fantasy/cli.py tests/test_evaluar.py modelos docs/evaluacion_preliminar_2024.txt
git commit -m "feat: entrenamiento y evaluación preliminar walk-forward contra ESPN (2024)"
```

---

### Task 9: Segunda opinión en el reporte

**Files:**
- Create: `src/fantasy/proyeccion/modelo.py`
- Modify: `src/fantasy/reporte/armado.py`, plantilla, `src/fantasy/config.py` (`RUTA_MODELO = Path("modelos/modelo_v1.json")`)
- Test: `tests/test_segunda_opinion.py`

**Interfaces:**
- Produces:
  - `segunda_opinion(crudos: dict, temporada: int, semana: int, ruta: Path) -> tuple[dict[int, float], str | None]` → (predicción por jugador, aviso o None). Nunca lanza por modelo ausente o inválido: devuelve `({}, "<motivo>")`.
  - `armar(..., ruta_modelo: Path | None = None)`; cada fila de `alineacion` gana `modelo: float | None` y `discrepa: bool` (|modelo − proy| > 3.0).

- [ ] **Step 1: Pruebas que fallan**

`tests/test_segunda_opinion.py`:
```python
import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.modelo import ridge
from fantasy.modelo.variables import VARIABLES
from fantasy.proyeccion.modelo import segunda_opinion
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def _modelo_copia_espn(ruta):
    # Coeficiente 1 sobre proy_espn estandarizada con escala 1: predice exactamente ESPN + 5.
    p = {"coef": [1.0] + [0.0] * (len(VARIABLES) - 1), "intercepto": 5.0,
         "media": [0.0] * len(VARIABLES), "escala": [1.0] * len(VARIABLES), "n": 1}
    ridge.guardar(ridge.Modelo(por_pos={x: p for x in ("QB", "RB", "WR", "TE")}), ruta)


def test_segunda_opinion_con_modelo(tmp_path):
    _modelo_copia_espn(tmp_path / "m.json")
    pred, aviso = segunda_opinion(cargar(SEM4), 2026, 4, tmp_path / "m.json")
    assert aviso is None and len(pred) > 200


def test_sin_modelo_avisa_y_no_truena(tmp_path):
    # Review Focus 4
    pred, aviso = segunda_opinion(cargar(SEM4), 2026, 4, tmp_path / "no_existe.json")
    assert pred == {} and "modelo" in aviso
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=tmp_path / "no_existe.json")
    assert all(f["modelo"] is None for f in r.alineacion)
    assert any("modelo" in a.lower() for a in r.avisos)
    assert "Modelo" not in generar_html(r)


def test_columna_y_bandera(tmp_path):
    _modelo_copia_espn(tmp_path / "m.json")
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=tmp_path / "m.json")
    assert all(abs(f["modelo"] - f["proy"] - 5.0) < 0.11 for f in r.alineacion)
    assert all(f["discrepa"] for f in r.alineacion)  # +5 > 3
    html = generar_html(r)
    assert "Modelo" in html and "⚑" in html
```

- [ ] **Step 2: Verificar que fallan**

Run: `uv run pytest tests/test_segunda_opinion.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'fantasy.proyeccion.modelo'`

- [ ] **Step 3: Implementar**

`src/fantasy/proyeccion/modelo.py`:
```python
"""Segunda opinión: el modelo propio para la semana en curso. Nunca decide (decisión 15)."""

from pathlib import Path

from fantasy.modelo import ridge, variables


def segunda_opinion(crudos: dict, temporada: int, semana: int,
                    ruta: Path) -> tuple[dict[int, float], str | None]:
    if not ruta.exists():
        return {}, f"Sin modelo en {ruta}: no se muestra la segunda opinión."
    try:
        m = ridge.cargar(ruta)
    except (ValueError, KeyError, TypeError) as e:
        return {}, f"El modelo guardado no sirve ({e}): no se muestra la segunda opinión."
    f = variables.desde_crudos(crudos, temporada, semanas=[semana])
    if not all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        return {}, "Sin uso de nflverse: no se muestra la segunda opinión del modelo."
    pred = ridge.predecir(m, f)
    return {int(j): float(p) for j, p in zip(f.jugador_id, pred, strict=True)
            if p == p}, None
```

En `config.py` añadir:
```python
from pathlib import Path

RUTA_MODELO = Path("modelos/modelo_v1.json")
UMBRAL_DISCREPA = 3.0
```

En `armado.py`: importar `from fantasy.config import RUTA_MODELO, SEMANA_FINAL, TEMPORADA, UMBRAL_DISCREPA` y `from fantasy.proyeccion.modelo import segunda_opinion`; añadir el parámetro `ruta_modelo: Path | None = None` a `armar` (y `from pathlib import Path`); antes de armar `alineacion`:
```python
    modelo, aviso_modelo = segunda_opinion(crudos, TEMPORADA, semana, ruta_modelo or RUTA_MODELO)
    if aviso_modelo:
        avisos.append(aviso_modelo)
```
y en cada fila de `alineacion` añadir:
```python
        "modelo": round(modelo[j], 1) if j in modelo else None,
        "discrepa": j in modelo and abs(modelo[j] - float(idx.loc[j, "proy"])) > UMBRAL_DISCREPA,
```

En la plantilla, tabla de alineación: encabezado
`<tr><th>Lugar</th><th>Jugador</th><th class="num">Proy.</th>{% if alineacion and alineacion[0].modelo is not none %}<th class="num">Modelo</th>{% endif %}<th>Estado</th></tr>`
y en la fila, después de la celda de `f.proy`:
`{% if f.modelo is not none %}<td class="num">{{ f.modelo }}{% if f.discrepa %} ⚑{% endif %}</td>{% endif %}`
y bajo la tabla:
`{% if alineacion and alineacion[0].modelo is not none %}<p class="suave">Modelo: segunda opinión sin validar; no cambia la alineación. ⚑ = difiere de ESPN por más de 3 puntos.</p>{% endif %}`

- [ ] **Step 4: Verificar**

Run: `uv run pytest -q && uv run ruff check .`
Expected: todo pasa (las pruebas de la fase 0 siguen verdes: sin modelo en `modelos/` durante las pruebas antiguas, la columna simplemente no aparece; si `modelos/modelo_v1.json` ya existe por la tarea 8, las pruebas antiguas no dependen de la columna).

- [ ] **Step 5: Prueba de humo real**

Run: `uv run fantasy reporte --tipo martes --salida salida_prueba --sin-correo --forzar` y abre el HTML: columna Modelo con valores razonables (entre 0 y 40) y sección de intercambios. Luego `rm -rf salida_prueba`.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy tests/test_segunda_opinion.py
git commit -m "feat: segunda opinión del modelo en la alineación (no decide)"
```

---

### Task 10: README y cierre

**Files:**
- Modify: `README.md`, `.gitignore` (añadir `salida/`, `salida_prueba/`)

- [ ] **Step 1:** Añadir al README una sección "Modelo (preliminar)" con el contenido de `docs/evaluacion_preliminar_2024.txt` y una línea que diga que 2025 sigue sellado y que la validación oficial es la fase 3; y una sección "Comandos" con `fantasy historico`, `fantasy entrenar`, `fantasy evaluar --temporada 2024`.
- [ ] **Step 2:** `uv run pytest -q && uv run ruff check .` → verde.
- [ ] **Step 3: Commit**

```bash
git add README.md .gitignore
git commit -m "docs: modelo preliminar y comandos de la fase 1"
```
