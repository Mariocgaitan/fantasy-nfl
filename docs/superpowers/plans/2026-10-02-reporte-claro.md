# Reporte claro Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el reporte empiece con "Qué hacer" (🔴 urgente / 🟡 recomendado / ⚪ radar), diga lo mismo que la sesión (lugar vacío → respaldo o moneda de cambio) y explique cada sección en lenguaje simple.

**Architecture:** Un módulo nuevo `decision/lugar_libre.py` decide qué pedir con un lugar vacío o con un titular fuera sin reemplazo. Otro, `decision/acciones.py`, convierte lo que ya arma `reporte/armado.py` (dicts) en una lista ordenada de `Accion`. La plantilla HTML se reescribe alrededor de esa lista; el correo solo cuenta acciones.

**Tech Stack:** Python 3.12, pandas, Jinja2, pytest, ruff, uv.

**Spec:** `docs/superpowers/specs/2026-10-02-reporte-claro-design.md`

## Global Constraints

- No tocar `src/fantasy/modelo/`, `src/fantasy/ingesta/historico.py` ni `src/fantasy/proyeccion/modelo.py` (modelo congelado hasta la validación en vivo).
- `GANANCIA_SEMANAL_MIN = 1.0` puntos por semana; semanas restantes = `SEMANA_FINAL − semana + 1`.
- Waivers: 17:00 Sídney, todos los días menos martes.
- Horas visibles siempre en Sídney, formato `"sáb 17:00"` (`DIAS_CORTOS` de `armado`).
- Textos en español, sin jerga de la NFL sin explicar. Sin columna "Modelo" ni sello "SIN VALIDAR"; el pie dice "Decide la proyección de ESPN." o "Decide el modelo validado.".
- Cero costo; nada se ejecuta en ESPN.
- Comandos: `uv run pytest -q`, `uv run ruff check src tests`.
- Archivos con fin de línea LF (no escribir con `open(..., "w")` de Windows sin `newline=""`).

## Review Focus

1. **Plantilla llena (14/14) y titular fuera sin reemplazo:** el pedido urgente debe decir a quién soltar, y nunca a un bloqueado ni a un intocable (ADP < 60). → test en Task 4.
2. **Titular en semana de descanso (sin partido, `inicio_utc` NaT):** no debe tronar ni pedir respaldo para él. → test en Task 3.
3. **Ningún libre sirve de respaldo a tiempo:** el lugar vacío cae a moneda de cambio; si tampoco hay, no sale acción (no "Pide a None"). → test en Task 3.
4. **Reporte sin datos de nflverse (sin `rol`) y viernes sin intercambios:** "Qué hacer" sale igual y "Nada que hacer hoy" cuando aplica. → test en Task 5.
5. **Waiver que se procesa después del partido del titular:** para un urgente no sirve; hay que elegir un libre `LIBRE`. → test en Task 3.

---

## File Structure

- Create `src/fantasy/decision/lugar_libre.py` — elegir respaldo / moneda de cambio.
- Create `src/fantasy/decision/acciones.py` — `Accion` y reglas de urgencia (sobre dicts).
- Modify `src/fantasy/horario.py` — `proximo_waiver`.
- Modify `src/fantasy/ingesta/espn.py` — `tope_plantilla`.
- Modify `src/fantasy/decision/alineacion.py` — `Reemplazo.motivo`.
- Modify `src/fantasy/decision/agencia_libre.py` — `ganando_rol` con banca rival.
- Modify `src/fantasy/reporte/armado.py` — nuevos campos y cableado.
- Rewrite `src/fantasy/reporte/plantillas/reporte.html.j2`.
- Modify `src/fantasy/reporte/correo.py` — `resumen` por conteo.
- Create fixture `tests/fixtures/sem04_2026-10-02/` (instantánea del viernes, rama `datos`).
- Tests: `tests/test_horario.py`, `tests/test_espn_parsers.py`, `tests/test_alineacion.py`, `tests/test_agencia_libre.py`, `tests/test_lugar_libre.py` (nuevo), `tests/test_acciones.py` (nuevo), `tests/test_reporte_claro.py` (nuevo), y ajustes en `tests/test_reporte.py`, `tests/test_reporte_fase1.py`, `tests/test_segunda_opinion.py`, `tests/test_modelo_manda.py`, `tests/test_cli.py`.

---

### Task 1: Ayudantes — próximo waiver, tope de plantilla, motivo de "sin respaldo"

**Files:**
- Modify: `src/fantasy/horario.py`
- Modify: `src/fantasy/ingesta/espn.py`
- Modify: `src/fantasy/decision/alineacion.py`
- Test: `tests/test_horario.py`, `tests/test_espn_parsers.py`, `tests/test_alineacion.py`

**Interfaces:**
- Produces: `horario.proximo_waiver(ahora: pd.Timestamp) -> pd.Timestamp` (UTC); `espn.tope_plantilla(liga: dict) -> int`; `alineacion.Reemplazo.motivo: str | None` con valores `None` (hay suplente), `"sin_posicion"`, `"horario"`, `"ocupado"`.

- [ ] **Step 1: Write the failing tests**

En `tests/test_horario.py` agrega:

```python
def test_proximo_waiver_salta_el_martes():
    import pandas as pd

    from fantasy.horario import proximo_waiver
    # Viernes 2026-10-02 09:23 Sídney → viernes 17:00 Sídney.
    assert proximo_waiver(pd.Timestamp("2026-10-01 23:23", tz="UTC")) == \
        pd.Timestamp("2026-10-02 07:00", tz="UTC")
    # Martes 2026-10-06 18:00 Sídney (ya con horario de verano, UTC+11) → miércoles 17:00.
    assert proximo_waiver(pd.Timestamp("2026-10-06 07:00", tz="UTC")) == \
        pd.Timestamp("2026-10-07 06:00", tz="UTC")
    # Lunes 2026-10-05 17:30 Sídney → no hay martes → miércoles 17:00.
    assert proximo_waiver(pd.Timestamp("2026-10-05 06:30", tz="UTC")) == \
        pd.Timestamp("2026-10-07 06:00", tz="UTC")
```

En `tests/test_espn_parsers.py` agrega:

```python
def test_tope_plantilla_suma_titulares_y_banca_sin_ir(fixture_dir):
    from fantasy.almacen.instantaneas import cargar
    from fantasy.ingesta import espn
    assert espn.tope_plantilla(cargar(fixture_dir)["liga"]) == 14
    assert espn.tope_plantilla({"settings": {}}) == 14  # sin datos: el de la liga
```

En `tests/test_alineacion.py` agrega (usa los helpers del archivo si existen; si no, este test es autocontenido):

```python
def test_reemplazos_dicen_por_que_no_hay_suplente():
    import pandas as pd

    from fantasy.decision.alineacion import optima, reemplazos
    temprano = pd.Timestamp("2026-10-04 17:00", tz="UTC")
    tarde = pd.Timestamp("2026-10-05 00:20", tz="UTC")
    filas = [  # jugador_id, pos, esperado, inicio
        (1, "QB", 20, temprano), (2, "RB", 18, tarde), (3, "RB", 15, temprano),
        (4, "WR", 16, tarde), (5, "WR", 14, temprano), (6, "TE", 10, temprano),
        (7, "WR", 13, temprano), (8, "WR", 9, temprano),
    ]
    t = pd.DataFrame([{"jugador_id": j, "nombre": f"J{j}", "pos": p, "proy": e, "esperado": e,
                       "p_jugar": 1.0, "inicio_utc": i, "slot": "BANCA", "bloqueado": False,
                       "lesion": "ACTIVE"} for j, p, e, i in filas])
    al = optima(t)
    motivo = {r.titular: r.motivo for r in reemplazos(al, t)}
    assert motivo[2] == "sin_posicion"   # no hay RB en la banca
    assert motivo[4] == "horario"        # los WR de la banca juegan antes
    assert motivo[1] == "sin_posicion"   # no hay QB en la banca
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_horario.py tests/test_espn_parsers.py tests/test_alineacion.py -k "waiver or tope or por_que"`
Expected: FAIL (`ImportError: cannot import name 'proximo_waiver'`, `AttributeError: ... tope_plantilla`, `AttributeError: 'Reemplazo' object has no attribute 'motivo'`).

- [ ] **Step 3: Implement**

`src/fantasy/horario.py`, al final:

```python
WAIVERS = time(17, 0)  # hora de Sídney; todos los días menos martes


def proximo_waiver(ahora: pd.Timestamp) -> pd.Timestamp:
    """El próximo proceso de waivers después de `ahora`, en UTC."""
    local = ahora.astimezone(ZONA)
    for dias in range(8):
        dia = local.date() + timedelta(days=dias)
        if dia.weekday() == 1:  # martes: no hay proceso
            continue
        cuando = datetime.combine(dia, WAIVERS, tzinfo=ZONA)
        if cuando > local:
            return pd.Timestamp(cuando.astimezone(UTC))
    raise AssertionError("siempre hay un proceso de waivers en la semana")
```

`src/fantasy/ingesta/espn.py`, después de `rival_de`:

```python
SLOTS_PLANTILLA = ("0", "2", "4", "6", "23", "20")  # titulares + banca; el IR no cuenta


def tope_plantilla(liga: dict) -> int:
    """Lugares de la plantilla sin contar IR (14 en esta liga)."""
    cupos = ((liga.get("settings") or {}).get("rosterSettings") or {}).get("lineupSlotCounts")
    if not cupos:
        return MAX_PLANTILLA - 1
    return sum(int(cupos.get(s, 0)) for s in SLOTS_PLANTILLA)
```

`src/fantasy/decision/alineacion.py`: agrega el campo y el motivo.

```python
@dataclass(frozen=True)
class Reemplazo:
    slot: str
    titular: int
    suplente: int | None
    motivo: str | None = None  # sin suplente: "sin_posicion" | "horario" | "ocupado"
```

En `reemplazos`, reemplaza el cuerpo del `for` por:

```python
    for i, slot, j in movibles:
        f = idx.loc[j]
        de_su_pos = banca[banca.pos.isin(_posiciones(slot))]
        cand = de_su_pos[~de_su_pos.jugador_id.isin(usados)]
        if pd.notna(f.inicio_utc):
            cand = cand[cand.inicio_utc >= f.inicio_utc]
        mejor = cand.sort_values("esperado", ascending=False, kind="stable").head(1)
        suplente = int(mejor.jugador_id.iloc[0]) if len(mejor) else None
        motivo = None
        if suplente is None:
            a_tiempo = de_su_pos if pd.isna(f.inicio_utc) else \
                de_su_pos[de_su_pos.inicio_utc >= f.inicio_utc]
            motivo = ("sin_posicion" if de_su_pos.empty
                      else "horario" if a_tiempo.empty else "ocupado")
        else:
            usados.add(suplente)
        elegidos[i] = Reemplazo(slot, int(j), suplente, motivo)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest -q tests/test_horario.py tests/test_espn_parsers.py tests/test_alineacion.py`
Expected: PASS (todas).

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/horario.py src/fantasy/ingesta/espn.py src/fantasy/decision/alineacion.py tests/test_horario.py tests/test_espn_parsers.py tests/test_alineacion.py
git commit -m "feat: próximo waiver, tope de plantilla y motivo de 'sin respaldo'"
```

---

### Task 2: Ganando rol incluye la banca de los rivales

**Files:**
- Modify: `src/fantasy/decision/agencia_libre.py` (`COLUMNAS_ROL`, `ganando_rol`)
- Test: `tests/test_agencia_libre.py`

**Interfaces:**
- Produces: `ganando_rol(uso, jugadores, *, plantillas=None, equipo_id=None, ...)`; el DataFrame gana la columna `equipo_fantasy_id` (0 = libre). Con `plantillas` y `equipo_id`, también devuelve jugadores con `slot == "BANCA"` de equipos distintos de `equipo_id`.

- [ ] **Step 1: Write the failing test**

```python
def test_ganando_rol_incluye_la_banca_de_los_rivales():
    uso = pd.DataFrame({
        "jugador_id": [20, 20, 20, 21, 21, 21, 22, 22, 22, 23, 23, 23],
        "semana": [1, 2, 3] * 4,
        "snaps_pct": [0.10, 0.50, 0.60] * 4,
        "targets": [0, 4, 5] * 4, "acarreos": [0] * 12,
    })
    jug = _jug([
        {"jugador_id": 20, "nombre": "BancaRival", "pos": "RB", "equipo_fantasy_id": 3,
         "disponibilidad": "EQUIPO"},
        {"jugador_id": 21, "nombre": "TitularRival", "pos": "RB", "equipo_fantasy_id": 3,
         "disponibilidad": "EQUIPO"},
        {"jugador_id": 22, "nombre": "Mio", "pos": "RB", "equipo_fantasy_id": 5,
         "disponibilidad": "EQUIPO"},
        {"jugador_id": 23, "nombre": "Libre", "pos": "RB"},
    ])
    plantillas = pd.DataFrame({"equipo_id": [3, 3, 5], "jugador_id": [20, 21, 22],
                               "slot": ["BANCA", "RB", "BANCA"], "bloqueado": [False] * 3})
    r = al.ganando_rol(uso, jug, plantillas=plantillas, equipo_id=5)
    assert set(r.nombre) == {"BancaRival", "Libre"}
    assert dict(zip(r.nombre, r.equipo_fantasy_id)) == {"BancaRival": 3, "Libre": 0}
    # Sin plantillas se comporta como antes: solo libres.
    assert set(al.ganando_rol(uso, jug).nombre) == {"Libre"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest -q tests/test_agencia_libre.py -k banca_de_los_rivales`
Expected: FAIL (`TypeError: ganando_rol() got an unexpected keyword argument 'plantillas'`).

- [ ] **Step 3: Implement**

```python
COLUMNAS_ROL = ["jugador_id", "nombre", "pos", "disponibilidad", "equipo_fantasy_id",
                "snaps_antes", "snaps_ahora", "oport_antes", "oport_ahora", "dueno_pct",
                "dueno_cambio"]
```

Firma y filtro final de `ganando_rol`:

```python
def ganando_rol(uso, jugadores, *, plantillas=None, equipo_id=None, umbral_snaps=0.15,
                umbral_oport=3.0, max_cambio_dueno=1.0):
    """Libres a los que les sube el uso. Con `plantillas` y `equipo_id`, también los que están
    en la banca de un rival: su dueño aún no los valora y salen baratos en un intercambio."""
```

y reemplaza la línea `d = d[(d.disponibilidad != "EQUIPO") & (d.dueno_cambio <= max_cambio_dueno)]` por:

```python
    elegible = d.disponibilidad != "EQUIPO"
    if plantillas is not None and equipo_id is not None:
        banca_rival = set(plantillas.loc[(plantillas.slot == "BANCA")
                                         & (plantillas.equipo_id != equipo_id), "jugador_id"])
        elegible |= d.jugador_id.isin(banca_rival)
    d = d[elegible & (d.dueno_cambio <= max_cambio_dueno)]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q tests/test_agencia_libre.py`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/agencia_libre.py tests/test_agencia_libre.py
git commit -m "feat: ganando rol también muestra la banca de los rivales"
```

---

### Task 3: Lugar libre — respaldo o moneda de cambio

**Files:**
- Create: `src/fantasy/decision/lugar_libre.py`
- Test: `tests/test_lugar_libre.py`

**Interfaces:**
- Consumes: `agencia_libre.Valuador`, `alineacion.FLEX_POS`; tablas de `agencia_libre.tablas_por_semana` (columnas `jugador_id, pos, proy, esperado, inicio_utc, slot, bloqueado, lesion, disponibilidad`).
- Produces:

```python
@dataclass(frozen=True)
class Eleccion:
    jugador_id: int
    motivo: str               # "respaldo" | "moneda"
    cubre: int | None         # titular al que respalda (solo "respaldo")
    rival: int | None         # equipo al que más le sirve
    valor_rival: float        # mejora de la alineación de ese rival, de aquí al final

def elegir(jugadores, tablas, plantillas, equipo_id, semana, sin_respaldo, n_lugares, *,
           solo_respaldo=False, waiver=None, top=40) -> list[Eleccion]
```

`sin_respaldo`: `list[tuple[str, int]]` (slot, titular). `waiver`: `pd.Timestamp | None`; si se da, un candidato en `WAIVERS` solo sirve si `waiver < inicio del titular` (para urgentes).

- [ ] **Step 1: Write the failing tests**

`tests/test_lugar_libre.py`:

```python
import pandas as pd

from fantasy.decision import lugar_libre as ll

TEMPRANO = pd.Timestamp("2026-10-04 17:00", tz="UTC")
TARDE = pd.Timestamp("2026-10-05 00:20", tz="UTC")


def _caso(libres, rival_flojo_en="RB"):
    """Mario (5): QB 1, RB 2-3, WR 4-5, TE 6. Rival (3): flojo en `rival_flojo_en`.
    `libres`: [(id, pos, puntos por semana, inicio, disponibilidad)]."""
    mios = [(1, "QB", 20), (2, "RB", 18), (3, "RB", 15), (4, "WR", 16), (5, "WR", 14),
            (6, "TE", 10)]
    suyos = [(11, "QB", 20), (12, "RB", 3 if rival_flojo_en == "RB" else 15),
             (13, "RB", 14), (14, "WR", 15), (15, "WR", 3 if rival_flojo_en == "WR" else 14),
             (16, "TE", 9), (17, "TE", 8)]  # 17 ocupa el FLEX del rival
    filas = [dict(jugador_id=j, pos=p, pts=x, inicio=TEMPRANO, equipo_fantasy_id=5,
                  disponibilidad="EQUIPO") for j, p, x in mios]
    filas[1]["inicio"] = TARDE  # el RB titular 2 juega tarde
    filas += [dict(jugador_id=j, pos=p, pts=x, inicio=TEMPRANO, equipo_fantasy_id=3,
                   disponibilidad="EQUIPO") for j, p, x in suyos]
    filas += [dict(jugador_id=j, pos=p, pts=x, inicio=i, equipo_fantasy_id=0,
                   disponibilidad=d) for j, p, x, i, d in libres]
    jug = pd.DataFrame([{"jugador_id": f["jugador_id"], "nombre": f"J{f['jugador_id']}",
                         "pos": f["pos"], "equipo_nfl_id": 1, "lesion": "ACTIVE",
                         "equipo_fantasy_id": f["equipo_fantasy_id"],
                         "disponibilidad": f["disponibilidad"], "dueno_pct": 1.0,
                         "dueno_cambio": 0.0} for f in filas])
    tablas = {}
    for w in (4, 5):
        t = jug.copy()
        t["proy"] = [f["pts"] for f in filas]
        t["p_jugar"] = 1.0
        t["esperado"] = t.proy
        t["inicio_utc"] = [f["inicio"] for f in filas]
        t["slot"] = "BANCA"
        t["bloqueado"] = False
        tablas[w] = t
    plantillas = jug[jug.equipo_fantasy_id > 0].rename(
        columns={"equipo_fantasy_id": "equipo_id"})[["equipo_id", "jugador_id"]]
    return jug, tablas, plantillas


def test_respaldo_primero_si_un_titular_no_tiene_quien_lo_cubra():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE"), (22, "WR", 12, TEMPRANO, "LIBRE")])
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1)
    assert (e.jugador_id, e.motivo, e.cubre) == (21, "respaldo", 2)


def test_respaldo_debe_jugar_a_la_misma_hora_o_despues():
    # El único RB libre juega antes que el titular: no lo cubre → moneda de cambio.
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE")])
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1)
    assert e.motivo == "moneda" and e.jugador_id == 21 and e.rival == 3


def test_sin_faltantes_elige_moneda_de_cambio_por_valor_para_rivales():
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE"), (22, "WR", 12, TEMPRANO, "LIBRE")],
                            rival_flojo_en="RB")
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [], 1)
    assert (e.jugador_id, e.motivo, e.rival) == (21, "moneda", 3)
    assert e.valor_rival > 0


def test_dos_lugares_no_repiten_jugador():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE"), (22, "RB", 8, TARDE, "LIBRE")])
    elegidos = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 2)
    assert len({e.jugador_id for e in elegidos}) == 2
    assert elegidos[0].motivo == "respaldo"


def test_nadie_sirve_no_devuelve_nada():
    # Review Focus 3: ningún libre ayuda a nadie → lista vacía, no "Pide a None".
    jug, tablas, pl = _caso([])
    assert ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1) == []


def test_solo_respaldo_no_cae_a_moneda():
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE")])
    assert ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1, solo_respaldo=True) == []


def test_waiver_que_llega_tarde_no_sirve_para_un_urgente():
    # Review Focus 5: el de waivers se procesa después del partido → se elige el LIBRE.
    jug, tablas, pl = _caso([(21, "RB", 12, TARDE, "WAIVERS"), (22, "RB", 7, TARDE, "LIBRE")])
    despues = TARDE + pd.Timedelta(hours=1)
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1, solo_respaldo=True, waiver=despues)
    assert e.jugador_id == 22


def test_titular_que_descansa_no_pide_respaldo():
    # Review Focus 2: titular sin partido esta semana (NaT) se ignora.
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE")])
    for t in tablas.values():
        t.loc[t.jugador_id == 2, "inicio_utc"] = pd.NaT
    assert ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1, solo_respaldo=True) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_lugar_libre.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'fantasy.decision.lugar_libre'`).

- [ ] **Step 3: Implement** `src/fantasy/decision/lugar_libre.py`

```python
"""Qué pedir con un lugar vacío (o con un titular fuera): respaldo si a un titular nadie lo
cubre; si no, moneda de cambio (el libre que más mejora las alineaciones de los rivales)."""

from dataclasses import dataclass

import pandas as pd

from fantasy.decision.agencia_libre import Valuador
from fantasy.decision.alineacion import FLEX_POS

TOP_CANDIDATOS = 40


@dataclass(frozen=True)
class Eleccion:
    jugador_id: int
    motivo: str               # "respaldo" | "moneda"
    cubre: int | None         # titular al que respalda (solo "respaldo")
    rival: int | None         # equipo al que más le sirve
    valor_rival: float        # mejora de la alineación de ese rival, de aquí al final


def _posiciones(slot: str) -> tuple[str, ...]:
    return FLEX_POS if slot == "FLEX" else (slot,)


def _valor_para_rivales(cands, plantillas, equipo_id, valuador):
    """jugador → (suma de mejoras positivas, rival con la mayor, esa mejora)."""
    equipos = {int(e): set(g.jugador_id) for e, g in plantillas.groupby("equipo_id")
               if int(e) != equipo_id}
    base = {e: valuador.valor(s) for e, s in equipos.items()}
    out = {}
    for j in cands:
        mejoras = {e: valuador.valor(s | {j}) - base[e] for e, s in equipos.items()}
        rival = max(mejoras, key=mejoras.get) if mejoras else None
        out[j] = (sum(max(v, 0.0) for v in mejoras.values()), rival,
                  max(mejoras.values(), default=0.0))
    return out


def elegir(jugadores, tablas, plantillas, equipo_id, semana, sin_respaldo, n_lugares, *,
           solo_respaldo=False, waiver=None, top=TOP_CANDIDATOS) -> list[Eleccion]:
    if n_lugares <= 0:
        return []
    resto = pd.concat(tablas.values()).groupby("jugador_id")["proy"].sum()
    t0 = tablas[semana].set_index("jugador_id")
    sanos = jugadores[jugadores.disponibilidad.isin(["LIBRE", "WAIVERS"])
                      & (jugadores.lesion == "ACTIVE")]
    sanos = (sanos.assign(r=sanos.jugador_id.map(resto).fillna(0.0))
             .sort_values("r", ascending=False, kind="stable").head(top))
    valores = _valor_para_rivales([int(j) for j in sanos.jugador_id], plantillas, equipo_id,
                                  Valuador(tablas))
    pendientes = list(sin_respaldo)
    usados: set[int] = set()
    elegidos: list[Eleccion] = []
    for _ in range(n_lugares):
        e = _respaldo(sanos, t0, valores, pendientes, usados, waiver)
        if e is None and not solo_respaldo:
            e = _moneda(sanos, valores, usados)
        if e is None:
            break
        elegidos.append(e)
        usados.add(e.jugador_id)
        pendientes = [(s, t) for s, t in pendientes if t != e.cubre]
    return elegidos


def _respaldo(sanos, t0, valores, pendientes, usados, waiver):
    opciones = []
    for slot, titular in pendientes:
        inicio = t0.inicio_utc.get(titular)
        if inicio is None or pd.isna(inicio):
            continue  # descansa esta semana: no hay a quién cubrir
        for f in sanos.itertuples():
            j = int(f.jugador_id)
            if j in usados or f.pos not in _posiciones(slot):
                continue
            ini = t0.inicio_utc.get(j)
            if ini is None or pd.isna(ini) or ini < inicio or t0.proy.get(j, 0.0) <= 0:
                continue
            if waiver is not None and f.disponibilidad == "WAIVERS" and not waiver < inicio:
                continue
            suma, rival, mejora = valores[j]
            opciones.append(((f.r, suma), Eleccion(j, "respaldo", int(titular), rival, mejora)))
    if not opciones:
        return None
    return max(opciones, key=lambda x: x[0])[1]


def _moneda(sanos, valores, usados):
    cands = [(valores[int(j)][0], int(j)) for j in sanos.jugador_id
             if int(j) not in usados and valores[int(j)][0] > 0]
    if not cands:
        return None
    _, j = max(cands)
    _, rival, mejora = valores[j]
    return Eleccion(j, "moneda", None, rival, mejora)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q tests/test_lugar_libre.py`
Expected: PASS (8).

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/lugar_libre.py tests/test_lugar_libre.py
git commit -m "feat: lugar libre elige respaldo o moneda de cambio"
```

---

### Task 4: Acciones — reglas de urgencia

**Files:**
- Create: `src/fantasy/decision/acciones.py`
- Test: `tests/test_acciones.py`

**Interfaces:**
- Consumes (dicts que arma `armado` en Task 5):
  - `alineacion`: `{"slot","nombre","pos","lesion","estado","bloqueado","inicio_utc"}`
  - `reemplazos`: `{"titular","suplente","motivo","inicio_utc"}`
  - `pedidos`: `{"titular","nombre","pos","disponibilidad","limite","soltar"}` (titular fuera sin reemplazo; `soltar` puede ser `None`)
  - `lugares`: `{"nombre","pos","disponibilidad","motivo","cubre","rival","valor_rival","limite"}`
  - `agencia`: `{"pedir","pos","soltar","semanal"}`
  - `intercambios`: `{"rival","das","recibes","semanal","riesgo"}`
  - `rol`: `{"nombre","pos","dueno"}` (`dueno` = "" si libre)
- Produces:

```python
@dataclass(frozen=True)
class Accion:
    urgencia: str                 # "urgente" | "recomendado" | "radar"
    texto: str
    porque: str
    limite: pd.Timestamp | None   # UTC
    tipo: str

GANANCIA_SEMANAL_MIN = 1.0
def construir(*, cambios: list[str], limite_cambios: pd.Timestamp | None,
              alineacion: list[dict], reemplazos: list[dict], pedidos: list[dict],
              lugares: list[dict], agencia: list[dict], intercambios: list[dict],
              rol: list[dict], max_rol: int = 5) -> list[Accion]
def contar(acciones: list[Accion]) -> dict[str, int]
```

Orden de salida: urgentes por `limite` (None al final), luego recomendados, luego radar.

- [ ] **Step 1: Write the failing tests** `tests/test_acciones.py`

```python
import pandas as pd

from fantasy.decision import acciones as ac

T1 = pd.Timestamp("2026-10-04 17:00", tz="UTC")
T2 = pd.Timestamp("2026-10-05 00:20", tz="UTC")


def _vacio(**kw):
    base = dict(cambios=[], limite_cambios=None, alineacion=[], reemplazos=[], pedidos=[],
                lugares=[], agencia=[], intercambios=[], rol=[])
    return ac.construir(**{**base, **kw})


def test_nada_que_hacer():
    assert _vacio() == []
    assert ac.contar([]) == {"urgente": 0, "recomendado": 0, "radar": 0}


def test_alineacion_no_optima_es_urgente_con_el_primer_partido():
    [a] = _vacio(cambios=["Entra X", "Sale Y"], limite_cambios=T1)
    assert (a.urgencia, a.tipo, a.limite) == ("urgente", "alineacion", T1)
    assert "Entra X" in a.texto and "Sale Y" in a.texto


def test_titular_en_duda_con_suplente_es_urgente():
    al = [{"slot": "WR", "nombre": "A", "pos": "WR", "lesion": "QUESTIONABLE",
           "estado": "en duda", "bloqueado": False, "inicio_utc": T2}]
    rem = [{"titular": "A", "suplente": "B", "motivo": None, "inicio_utc": T2}]
    [a] = _vacio(alineacion=al, reemplazos=rem)
    assert a.urgencia == "urgente" and a.limite == T2
    assert a.texto == "Si A queda fuera, mete a B"


def test_pedido_urgente_dice_a_quien_soltar():
    # Review Focus 1: plantilla llena → el texto incluye a quién soltar.
    ped = [{"titular": "A", "nombre": "N", "pos": "RB", "disponibilidad": "WAIVERS",
            "limite": T1, "soltar": "Z"}]
    [a] = _vacio(pedidos=ped)
    assert a.urgencia == "urgente" and a.limite == T1
    assert "Pide a N (RB)" in a.texto and "suelta a Z" in a.texto
    assert "waivers" in a.texto and "A no juega" in a.porque


def test_lugar_vacio_respaldo_y_moneda_son_recomendados():
    lug = [{"nombre": "D", "pos": "RB", "disponibilidad": "LIBRE", "motivo": "respaldo",
            "cubre": "Gibbs", "rival": "PUTI", "valor_rival": 27.0, "limite": None},
           {"nombre": "E", "pos": "WR", "disponibilidad": "WAIVERS", "motivo": "moneda",
            "cubre": None, "rival": "Norway", "valor_rival": 17.0, "limite": T1}]
    a, b = _vacio(lugares=lug)
    assert a.urgencia == b.urgencia == "recomendado"
    assert "sin soltar a nadie" in a.texto and "entra al instante" in a.texto
    assert "Gibbs no tiene quien lo cubra" in a.porque
    assert "Norway" in b.porque and "+17" in b.porque and b.limite == T1


def test_agencia_por_semana_separa_recomendado_y_radar():
    ag = [{"pedir": "Daniels", "pos": "QB", "soltar": "Young", "semanal": 0.6},
          {"pedir": "Love", "pos": "QB", "soltar": "Young", "semanal": 0.4},
          {"pedir": "Goedert", "pos": "TE", "soltar": "Johnson", "semanal": 1.2}]
    acc = _vacio(agencia=ag)
    rec = [a for a in acc if a.urgencia == "recomendado"]
    radar = [a for a in acc if a.urgencia == "radar"]
    assert [a.texto for a in rec] == ["Pide a Goedert (TE), suelta a Johnson"]
    assert len(radar) == 1 and "Daniels" in radar[0].texto and "+0.6" in radar[0].texto


def test_intercambios_recomendados_y_rol_en_radar():
    x = [{"rival": "Smashers", "das": ["A", "B"], "recibes": ["C"], "semanal": 2.1,
          "riesgo": "medio"}]
    rol = [{"nombre": "W", "pos": "RB", "dueno": "Smashers"}, {"nombre": "L", "pos": "WR",
                                                              "dueno": ""}]
    acc = _vacio(intercambios=x, rol=rol)
    assert acc[0].urgencia == "recomendado" and "Propón a Smashers" in acc[0].texto
    assert "veto medio" in acc[0].porque
    radar = [a.texto for a in acc if a.urgencia == "radar"]
    assert any("banca de Smashers" in t for t in radar)
    assert any("está libre" in t for t in radar)


def test_orden_urgentes_por_hora():
    al = [{"slot": "WR", "nombre": "A", "pos": "WR", "lesion": "DOUBTFUL", "estado": "dudoso",
           "bloqueado": False, "inicio_utc": T2}]
    rem = [{"titular": "A", "suplente": "B", "motivo": None, "inicio_utc": T2}]
    acc = _vacio(cambios=["Entra X"], limite_cambios=T1, alineacion=al, reemplazos=rem)
    assert [a.limite for a in acc] == [T1, T2]
    assert ac.contar(acc) == {"urgente": 2, "recomendado": 0, "radar": 0}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_acciones.py`
Expected: FAIL (`ModuleNotFoundError: No module named 'fantasy.decision.acciones'`).

- [ ] **Step 3: Implement** `src/fantasy/decision/acciones.py`

```python
"""Del reporte armado a una lista de acciones: 🔴 urgente, 🟡 recomendado, ⚪ en el radar."""

from dataclasses import dataclass

import pandas as pd

GANANCIA_SEMANAL_MIN = 1.0
EN_DUDA = ("QUESTIONABLE", "DOUBTFUL", "DAY_TO_DAY")
ORDEN = {"urgente": 0, "recomendado": 1, "radar": 2}
COMO_ENTRA = {"LIBRE": "libre, entra al instante",
              "WAIVERS": "waivers: se procesa a las 17:00"}


@dataclass(frozen=True)
class Accion:
    urgencia: str                 # "urgente" | "recomendado" | "radar"
    texto: str
    porque: str
    limite: pd.Timestamp | None   # UTC
    tipo: str


def construir(*, cambios, limite_cambios, alineacion, reemplazos, pedidos, lugares, agencia,
              intercambios, rol, max_rol=5) -> list[Accion]:
    acc: list[Accion] = []
    if cambios:
        acc.append(Accion("urgente", "Cambia tu alineación: " + " · ".join(cambios),
                          "tu alineación actual no es la mejor según ESPN", limite_cambios,
                          "alineacion"))
    suplente = {r["titular"]: r["suplente"] for r in reemplazos}
    for f in alineacion:
        if f["lesion"] in EN_DUDA and not f["bloqueado"] and suplente.get(f["nombre"]):
            acc.append(Accion("urgente", f"Si {f['nombre']} queda fuera, mete a "
                                         f"{suplente[f['nombre']]}",
                              f"{f['nombre']} está {f['estado']}; ESPN confirma quién no juega "
                              "~90 minutos antes del partido", f["inicio_utc"], "inactivo"))
    for p in pedidos:
        soltar = f", suelta a {p['soltar']}" if p.get("soltar") else ""
        acc.append(Accion("urgente", f"Pide a {p['nombre']} ({p['pos']}){soltar} "
                                     f"({COMO_ENTRA[p['disponibilidad']]})",
                          f"{p['titular']} no juega y no tienes quien lo reemplace",
                          p["limite"], "pedir"))
    for x in lugares:
        if x["motivo"] == "respaldo":
            porque = f"{x['cubre']} no tiene quien lo cubra si queda fuera"
        else:
            porque = (f"le sirve a {x['rival']} (+{x['valor_rival']:.0f} en su alineación) "
                      "para un intercambio")
        acc.append(Accion("recomendado", f"Pide a {x['nombre']} ({x['pos']}) sin soltar a "
                                         f"nadie ({COMO_ENTRA[x['disponibilidad']]})",
                          porque, x["limite"], "lugar"))
    buenas, flojas, vistas = [], [], set()
    for a in sorted(agencia, key=lambda a: -a["semanal"]):
        if a["semanal"] >= GANANCIA_SEMANAL_MIN:
            if a["pos"] not in vistas:
                vistas.add(a["pos"])
                buenas.append(a)
        else:
            flojas.append(a)
    for a in buenas:
        acc.append(Accion("recomendado", f"Pide a {a['pedir']} ({a['pos']}), suelta a "
                                         f"{a['soltar']}", f"+{a['semanal']:.1f} puntos por "
                                                           "semana", None, "agencia"))
    for x in intercambios:
        acc.append(Accion("recomendado", f"Propón a {x['rival']}: das {', '.join(x['das'])} "
                                         f"por {', '.join(x['recibes'])}",
                          f"+{x['semanal']:.1f} puntos por semana · riesgo de veto "
                          f"{x['riesgo']} · propón uno a la vez", None, "intercambio"))
    if flojas:
        a = flojas[0]
        acc.append(Accion("radar", f"Agencia libre: el mejor cambio ({a['pedir']} por "
                                   f"{a['soltar']}) gana +{a['semanal']:.1f} por semana",
                          "no vale la pena", None, "agencia"))
    for x in rol[:max_rol]:
        if x["dueno"]:
            acc.append(Accion("radar", f"{x['nombre']} ({x['pos']}), en la banca de "
                                       f"{x['dueno']}, está ganando rol",
                              "objetivo barato para el próximo intercambio", None, "rol"))
        else:
            acc.append(Accion("radar", f"{x['nombre']} ({x['pos']}) está ganando rol y está "
                                       "libre", "pídelo si se abre un lugar", None, "rol"))
    lejos = pd.Timestamp.max.tz_localize("UTC")
    return sorted(acc, key=lambda a: (ORDEN[a.urgencia],
                                      a.limite if a.urgencia == "urgente" and a.limite is not None
                                      else lejos))


def contar(acciones: list[Accion]) -> dict[str, int]:
    n = dict.fromkeys(ORDEN, 0)
    for a in acciones:
        n[a.urgencia] += 1
    return n
```

Nota: `sorted` es estable, así que los recomendados y el radar conservan el orden de inserción.

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q tests/test_acciones.py`
Expected: PASS (8).

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/acciones.py tests/test_acciones.py
git commit -m "feat: acciones con urgencia a partir del reporte"
```

---

### Task 5: Armado — cablear plantilla, lugares, pedidos, ganancia semanal y acciones

**Files:**
- Modify: `src/fantasy/reporte/armado.py`
- Create: `tests/fixtures/sem04_2026-10-02/` (8 archivos de la rama `datos`)
- Test: `tests/test_reporte_claro.py` (nuevo)

**Interfaces:**
- Consumes: Task 1 (`proximo_waiver`, `tope_plantilla`, `Reemplazo.motivo`), Task 2 (`ganando_rol(..., plantillas=, equipo_id=)`), Task 3 (`lugar_libre.elegir`), Task 4 (`acciones.construir`, `acciones.contar`).
- Produces en `Reporte`: `acciones: list[Accion]`, `plantilla: list[dict]` (`{"lugar","nombre","pos","proy","estado","hora"}`, lugar ∈ TITULARES ∪ {"Banca","IR"}), `lugares_libres: int`, `tope: int`; `reemplazos[i]["motivo"]`; `agencia[i]["semanal"]`; `intercambios[i]["semanal"]`; `rol[i]["dueno"]` (nombre del equipo o "").
- Produces función de módulo `hora_sidney(ts: pd.Timestamp | None) -> str` (`"sáb 17:00"`, `"descansa"` si None/NaT).

- [ ] **Step 1: Copiar la instantánea del viernes como fixture**

```bash
d=instantaneas/2026/sem04/2026-10-02T09-23
mkdir -p tests/fixtures/sem04_2026-10-02
for f in $(git ls-tree --name-only origin/datos $d/); do git show "origin/datos:$f" > "tests/fixtures/sem04_2026-10-02/$(basename $f)"; done
ls tests/fixtures/sem04_2026-10-02
```

Expected: `agentes_libres.json.gz calendario.json.gz juegos.csv.gz jugadores.csv.gz liga.json.gz proyecciones.json.gz semanal.csv.gz snaps.csv.gz`.

- [ ] **Step 2: Write the failing tests** `tests/test_reporte_claro.py`

```python
import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte.armado import armar, hora_sidney

VIE = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-10-02"
AHORA = pd.Timestamp("2026-10-01 23:23", tz="UTC")


def _r(tipo="viernes"):
    return armar(cargar(VIE), AHORA, tipo, 5)


def test_viernes_real_pide_respaldo_para_el_lugar_vacio():
    r = _r()
    assert (r.tope, r.lugares_libres) == (14, 1)
    lugar = [a for a in r.acciones if a.tipo == "lugar"]
    assert len(lugar) == 1 and lugar[0].urgencia == "recomendado"
    assert any(n in lugar[0].porque for n in ("Jahmyr Gibbs", "Ashton Jeanty",
                                              "Amon-Ra St. Brown"))


def test_viernes_real_daniels_no_es_recomendado():
    r = _r()
    rec = [a.texto for a in r.acciones if a.urgencia == "recomendado"]
    assert not any("Daniels" in t for t in rec)
    assert all(a["semanal"] < 1.0 for a in r.agencia if a["pedir"] == "Jayden Daniels")


def test_plantilla_completa_con_banca():
    r = _r()
    lugares = [f["lugar"] for f in r.plantilla]
    assert lugares[:7] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]
    assert lugares.count("Banca") == 6
    assert all(f["hora"] for f in r.plantilla)


def test_sin_respaldo_trae_motivo():
    r = _r()
    gibbs = next(x for x in r.reemplazos if x["titular"] == "Jahmyr Gibbs")
    assert gibbs["suplente"] is None and gibbs["motivo"] == "sin_posicion"


def test_rol_dice_de_quien_es():
    r = _r()
    assert all("dueno" in x for x in r.rol)


def test_martes_intercambios_con_ganancia_semanal():
    r = _r("martes")
    assert all("semanal" in x for x in r.intercambios)


def test_sin_nflverse_sale_igual():
    # Review Focus 4
    crudos = cargar(VIE)
    for k in ("semanal", "snaps", "jugadores"):
        crudos.pop(k, None)
    r = armar(crudos, AHORA, "viernes", 5)
    assert r.rol == [] and r.acciones is not None


def test_hora_sidney():
    assert hora_sidney(pd.Timestamp("2026-10-02 07:00", tz="UTC")) == "vie 17:00"
    assert hora_sidney(None) == "descansa"
    assert hora_sidney(pd.NaT) == "descansa"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest -q tests/test_reporte_claro.py`
Expected: FAIL (`ImportError: cannot import name 'hora_sidney'`).

- [ ] **Step 4: Implement in `src/fantasy/reporte/armado.py`**

Imports nuevos:

```python
from fantasy.decision import acciones as acciones_mod
from fantasy.decision import lugar_libre
from fantasy.decision.acciones import Accion
from fantasy.horario import ZONA, proximo_waiver, semana_objetivo
```

Función de módulo (reemplaza a la `hora` interna):

```python
def hora_sidney(v) -> str:
    if v is None or pd.isna(v):
        return "descansa"
    local = v.tz_convert(ZONA)
    return f"{DIAS_CORTOS[local.weekday()]} {local:%H:%M}"
```

Campos nuevos en `Reporte` (después de `avisos`):

```python
    acciones: list[Accion] = field(default_factory=list)
    plantilla: list[dict] = field(default_factory=list)
    lugares_libres: int = 0
    tope: int = 14
```

Dentro de `armar`:

1. En cada dict de `alineacion` agrega `"jugador_id": j, "inicio_utc": idx.loc[j, "inicio_utc"], "hora": hora_sidney(idx.loc[j, "inicio_utc"])`.
2. Cambios con límite:

```python
    cambian = list(al.ids() ^ actuales)
    inicios = [idx.loc[j, "inicio_utc"] for j in cambian if j in idx.index
               and pd.notna(idx.loc[j, "inicio_utc"])]
    limite_cambios = min(inicios) if inicios else None
```

3. `remp`: reemplaza `hora(...)` por `hora_sidney(idx.loc[..., "inicio_utc"])` y agrega `"motivo": r.motivo, "inicio_utc": idx.loc[r.titular, "inicio_utc"]`.
4. Ganancia semanal:

```python
    semanas = SEMANA_FINAL - semana + 1
```

y en cada dict de `agencia` e `intercambios`: `"semanal": round(float(x.ganancia) / semanas, 1)`.
5. Plantilla, tope y lugares:

```python
    tope = espn.tope_plantilla(liga)
    en_ir = set(mia.loc[mia.slot == "IR", "jugador_id"])
    lugares_libres = max(tope - len(mis_ids - en_ir), 0)
    titulares = {j for _, j in al.slots}
    plantilla = [{"lugar": s, "nombre": idx.loc[j, "nombre"], "pos": idx.loc[j, "pos"],
                  "proy": round(float(idx.loc[j, "proy"]), 1),
                  "estado": estado(idx.loc[j, "lesion"]),
                  "hora": hora_sidney(idx.loc[j, "inicio_utc"])} for s, j in al.slots]
    for j in sorted(mis_ids - titulares, key=lambda j: -float(idx.loc[j, "proy"])):
        plantilla.append({"lugar": "IR" if j in en_ir else "Banca",
                          "nombre": idx.loc[j, "nombre"], "pos": idx.loc[j, "pos"],
                          "proy": round(float(idx.loc[j, "proy"]), 1),
                          "estado": estado(idx.loc[j, "lesion"]),
                          "hora": hora_sidney(idx.loc[j, "inicio_utc"])})
```

6. Pedidos urgentes (titular fuera sin reemplazo) y lugares:

```python
    equipos = {t["id"]: t["name"].strip() for t in liga["teams"]}
    sin_respaldo = [(r.slot, r.titular) for r in reemplazos(al, tm) if r.suplente is None]
    fuera = [(s, j) for s, j in al.slots
             if idx.loc[j, "lesion"] in ("OUT", "INJURY_RESERVE", "SUSPENSION")
             and not idx.loc[j, "bloqueado"]]
    waiver = proximo_waiver(ahora)
    pedidos = []
    for s, j in fuera:
        elegidos = lugar_libre.elegir(jugadores, tablas, plantillas, equipo_id, semana,
                                      [(s, j)], 1, solo_respaldo=True, waiver=waiver)
        if not elegidos:
            continue
        e = elegidos[0]
        disp = por_id.loc[e.jugador_id, "disponibilidad"]
        soltar = None
        if lugares_libres == 0:
            banca = [b for b in mis_ids - titulares
                     if b not in intocables and not idx.loc[b, "bloqueado"]]
            resto = pd.concat(tablas.values()).groupby("jugador_id")["proy"].sum()
            soltar = nombres[min(banca, key=lambda b: resto.get(b, 0.0))] if banca else None
        pedidos.append({"titular": idx.loc[j, "nombre"], "nombre": nombres[e.jugador_id],
                        "pos": por_id.loc[e.jugador_id, "pos"], "disponibilidad": disp,
                        "limite": waiver if disp == "WAIVERS" else idx.loc[j, "inicio_utc"],
                        "soltar": soltar})
    lugares = [{
        "nombre": nombres[e.jugador_id], "pos": por_id.loc[e.jugador_id, "pos"],
        "disponibilidad": por_id.loc[e.jugador_id, "disponibilidad"], "motivo": e.motivo,
        "cubre": idx.loc[e.cubre, "nombre"] if e.cubre else None,
        "rival": equipos.get(e.rival), "valor_rival": round(e.valor_rival, 1),
        "limite": waiver if por_id.loc[e.jugador_id, "disponibilidad"] == "WAIVERS" else None,
    } for e in lugar_libre.elegir(jugadores, tablas, plantillas, equipo_id, semana,
                                  sin_respaldo, lugares_libres - len(pedidos))]
```

(`por_id` y `nombres` ya existen; mueve su definición antes de este bloque. Mueve también `equipos = ...` fuera del `if tipo == "martes"` y bórralo de ahí.)

7. Rol con dueño:

```python
        rol = (agencia_libre.ganando_rol(uso, jugadores, plantillas=plantillas,
                                         equipo_id=equipo_id)
               .head(8).round(2).to_dict("records"))
        for x in rol:
            x["dueno"] = equipos.get(int(x["equipo_fantasy_id"]), "")
```

8. Acciones, al final antes del `return`:

```python
    lista = acciones_mod.construir(
        cambios=cambios, limite_cambios=limite_cambios, alineacion=alineacion,
        reemplazos=remp, pedidos=pedidos, lugares=lugares, agencia=agencia,
        intercambios=propuestas, rol=rol)
```

y pasa `acciones=lista, plantilla=plantilla, lugares_libres=lugares_libres, tope=tope` al `Reporte(...)`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest -q tests/test_reporte_claro.py tests/test_reporte.py tests/test_reporte_fase1.py`
Expected: `test_reporte_claro.py` PASS. Si algo de `test_reporte*.py` falla por textos del HTML/correo, se arregla en las Tasks 6–7 (anótalo); fallos de `armar` se arreglan aquí.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/reporte/armado.py tests/test_reporte_claro.py tests/fixtures/sem04_2026-10-02
git commit -m "feat: el reporte arma plantilla, lugares libres, ganancia semanal y acciones"
```

---

### Task 6: La página

**Files:**
- Rewrite: `src/fantasy/reporte/plantillas/reporte.html.j2`
- Modify: `src/fantasy/reporte/html.py` (filtro `hora`)
- Test: `tests/test_reporte_claro.py`; ajustes en `tests/test_reporte.py`, `tests/test_reporte_fase1.py`, `tests/test_segunda_opinion.py`, `tests/test_modelo_manda.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: `Reporte` de Task 5; `hora_sidney`.

- [ ] **Step 1: Write the failing tests** (agrega a `tests/test_reporte_claro.py`)

```python
from fantasy.reporte.html import generar_html


def test_pagina_empieza_con_que_hacer():
    html = generar_html(_r())
    assert html.index("Qué hacer") < html.index("Tu plantilla")
    assert "Recomendado" in html and "sin soltar a nadie" in html
    assert "Lugares libres: 1 de 14" in html


def test_pagina_sin_modelo_ni_sello():
    html = generar_html(_r())
    assert "Modelo" not in html and "SIN VALIDAR" not in html
    assert "Decide la proyección de ESPN." in html


def test_pagina_explica_sin_respaldo_y_columnas_de_rol():
    html = generar_html(_r())
    assert "no tienes RB en la banca" in html
    assert "% de las jugadas de ataque" in html and "pases + carreras" in html


def test_pagina_ganancia_por_semana():
    html = generar_html(_r())
    assert "por semana" in html


def test_nada_que_hacer_hoy():
    r = _r()
    r.acciones = []
    assert "Nada que hacer hoy." in generar_html(r)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest -q tests/test_reporte_claro.py -k "pagina or nada"`
Expected: FAIL (la plantilla vieja no tiene "Qué hacer").

- [ ] **Step 3: Implement**

`src/fantasy/reporte/html.py`:

```python
from fantasy.reporte.armado import DIAS, Reporte, hora_sidney

_ENTORNO = Environment(loader=PackageLoader("fantasy.reporte", "plantillas"),
                       autoescape=select_autoescape(["html", "j2"]))
_ENTORNO.filters["hora"] = hora_sidney


def generar_html(r: Reporte) -> str:
    return _ENTORNO.get_template("reporte.html.j2").render(dia=DIAS[r.tipo], **asdict(r))
```

(`asdict` convierte cada `Accion` en dict; Jinja lee `a.texto` igual en dicts.)

`src/fantasy/reporte/plantillas/reporte.html.j2` — conserva el `<head>` actual (tokens de color, viewport, tabla) y reemplaza `.sinvalidar` por:

```css
  .urgente { border-left:4px solid var(--aviso); padding-left:10px; }
  .recomendado { border-left:4px solid #c9a227; padding-left:10px; }
  .radar { color:var(--suave); }
  ul.acciones { list-style:none; padding:0; }
  ul.acciones li { margin:0 0 10px; }
```

Cuerpo completo:

```html
<body>
<h1>BanKAI · semana {{ semana }}</h1>
<p class="suave">Reporte {{ dia }} · generado {{ generado }} (Sídney)</p>

<h2>Qué hacer</h2>
{% set urg = acciones | selectattr("urgencia", "eq", "urgente") | list %}
{% set rec = acciones | selectattr("urgencia", "eq", "recomendado") | list %}
{% set rad = acciones | selectattr("urgencia", "eq", "radar") | list %}
{% if not urg and not rec %}<p><strong>Nada que hacer hoy.</strong></p>{% endif %}
{% if urg %}<h3>🔴 Urgente</h3><ul class="acciones">
  {% for a in urg %}<li class="urgente"><strong>{{ a.texto }}</strong>{% if a.limite %} — antes del {{ a.limite | hora }}{% endif %}<br><small>{{ a.porque }}</small></li>{% endfor %}
</ul>{% endif %}
{% if rec %}<h3>🟡 Recomendado</h3><ul class="acciones">
  {% for a in rec %}<li class="recomendado"><strong>{{ a.texto }}</strong>{% if a.limite %} — antes del {{ a.limite | hora }}{% endif %}<br><small>{{ a.porque }}</small></li>{% endfor %}
</ul>{% endif %}
{% if rad %}<h3>⚪ En el radar</h3><ul class="acciones">
  {% for a in rad %}<li class="radar">{{ a.texto }} <small>— {{ a.porque }}</small></li>{% endfor %}
</ul>{% endif %}

<h2>Tu plantilla</h2>
<p class="suave">Lugares libres: {{ lugares_libres }} de {{ tope }} · puntos esperados de los titulares: {{ esperado }}</p>
<table>
  <tr><th>Lugar</th><th>Jugador</th><th class="num">Puntos</th><th>Estado</th><th>Juega</th></tr>
  {% for f in plantilla %}
  <tr><td>{{ f.lugar }}</td><td>{{ f.nombre }} <small>{{ f.pos }}</small></td>
      <td class="num">{{ f.proy }}</td><td>{{ f.estado }}</td><td>{{ f.hora }}</td></tr>
  {% endfor %}
</table>
<p class="suave">Puntos: lo que ESPN espera que haga esta semana.</p>

<h2>Si alguien queda fuera</h2>
<table>
  <tr><th>Titular</th><th>Juega</th><th>Entra</th></tr>
  {% for x in reemplazos %}
  <tr><td>{{ x.titular }}</td><td>{{ x.hora }}</td>
      <td>{% if x.suplente %}{{ x.suplente }} <small>{{ x.hora_suplente }}</small>{% if x.lesion_suplente != "ACTIVE" %} <strong>{{ x.estado_suplente }}</strong>{% endif %}
          {% elif x.motivo == "sin_posicion" %}<span class="suave">nadie: no tienes {{ x.slot if x.slot != "FLEX" else "RB/WR/TE" }} en la banca</span>
          {% elif x.motivo == "horario" %}<span class="suave">nadie: tus suplentes juegan antes que él (ya estarán bloqueados)</span>
          {% else %}<span class="suave">nadie: tu suplente ya cubre a otro titular</span>{% endif %}</td></tr>
  {% endfor %}
</table>

<h2>Agencia libre</h2>
{% if agencia %}
<table>
  <tr><th>Pedir</th><th>Soltar</th><th class="num">Por semana</th></tr>
  {% for a in agencia %}
  <tr><td>{{ a.pedir }} <small>{{ a.pos }}</small>{% if a.lesion != "ACTIVE" %} <strong>{{ a.estado }}</strong>{% endif %}</td><td>{{ a.soltar }}</td><td class="num">+{{ a.semanal }}</td></tr>
  {% endfor %}
</table>
<p class="suave">Cada fila es un cambio posible (harías uno como máximo): pides al de la izquierda y sueltas al de la derecha. Por semana: puntos extra en promedio de aquí a la semana 17. Menos de 1 por semana no vale la pena.</p>
{% else %}<p>Ningún agente libre mejora tu plantilla.</p>{% endif %}

{% if intercambios %}
<h2>Intercambios</h2>
<table>
  <tr><th>Rival</th><th>Das</th><th>Recibes</th><th class="num">Por semana</th><th>Veto</th></tr>
  {% for x in intercambios %}
  <tr><td>{{ x.rival }}</td><td>{{ x.das | join(", ") }}</td>
      <td>{{ x.recibes | join(", ") }}{% if x.lesiones %} <strong>{{ x.lesiones | join(", ") }}</strong>{% endif %}
          {% if x.relleno %}<br><small>y pides (agencia libre o waivers): {{ x.relleno | join(", ") }}</small>{% endif %}
          {% if x.sueltas %}<br><small>y sueltas: {{ x.sueltas | join(", ") }}</small>{% endif %}</td>
      <td class="num">+{{ x.semanal }}</td><td>{{ x.riesgo }}</td></tr>
  {% endfor %}
</table>
<p class="suave">Una propuesta por rival; propón una a la vez. Veto: qué tan disparejo se ve el trato contando solo lo que cada jugador rinde por encima del mejor libre de su posición (sin validar). Ninguna es con tu rival de esta semana.</p>
{% endif %}

<h2>Ganando rol</h2>
{% if rol %}
<table>
  <tr><th>Jugador</th><th>Dónde está</th><th class="num">Snaps</th><th class="num">Oport.</th><th class="num">Dueños %</th></tr>
  {% for x in rol %}
  <tr><td>{{ x.nombre }} <small>{{ x.pos }}</small></td>
      <td>{% if x.dueno %}banca de {{ x.dueno }}{% else %}libre{% endif %}</td>
      <td class="num">{{ (x.snaps_antes*100)|round|int }}→{{ (x.snaps_ahora*100)|round|int }}%</td>
      <td class="num">{{ x.oport_antes }}→{{ x.oport_ahora }}</td><td class="num">{{ x.dueno_pct|round(1) }}</td></tr>
  {% endfor %}
</table>
<p class="suave">Snaps: % de las jugadas de ataque de su equipo en que estuvo en la cancha (antes → ahora). Oport.: veces por partido que el balón fue para él (pases + carreras). Dueños %: % de ligas de ESPN en el mundo que lo tienen; bajo = el mercado no lo ha notado. Libre: pídelo si se abre un lugar. Banca de un rival: objetivo barato para un intercambio.</p>
{% else %}<p>Nadie viene ganando rol de forma clara.</p>{% endif %}

<p class="suave">{% if validado %}Decide el modelo validado ({{ validado }}).{% else %}Decide la proyección de ESPN.{% endif %}</p>
{% if avisos %}<h2>Avisos</h2><ul>{% for a in avisos %}<li>{{ a }}</li>{% endfor %}</ul>{% endif %}
</body>
</html>
```

Nota: la fila "sin_posicion" usa `x.slot`, que `remp` ya trae (`"slot": r.slot`).

- [ ] **Step 4: Ajustar pruebas viejas acopladas al HTML**

- `tests/test_reporte.py::test_html_marca_sin_validar`: cambia `"SIN VALIDAR" in html` por `"Decide la proyección de ESPN." in html` y `"sin respaldo útil" in html` por `"nadie:" in html`.
- `tests/test_modelo_manda.py`: `"SIN VALIDAR" in generar_html(r)` → `"Decide la proyección de ESPN." in generar_html(r)`; `"VALIDADO" in html and "SIN VALIDAR" not in html` → `"Decide el modelo validado" in html`.
- `tests/test_segunda_opinion.py::test_columna_y_bandera`: el reporte ya no muestra el modelo; deja las aserciones sobre `r.alineacion` y cambia la del HTML por `assert "Modelo" not in generar_html(r)`. `test_tabla_alineada_si_un_titular_no_tiene_modelo`: reemplaza la regex por `assert "Modelo" not in generar_html(r)` (la columna ya no existe).
- `tests/test_reporte_fase1.py::test_martes_trae_intercambios`: `"propón una a la vez" in html` se mantiene (sigue en la nota de intercambios).
- `tests/test_cli.py`: `"SIN VALIDAR" in html` → `"Decide la proyección de ESPN." in html`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest -q tests/test_reporte_claro.py tests/test_reporte.py tests/test_reporte_fase1.py tests/test_segunda_opinion.py tests/test_modelo_manda.py tests/test_cli.py`
Expected: PASS, salvo las pruebas del correo (`resumen`), que se ajustan en Task 7.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/reporte/html.py src/fantasy/reporte/plantillas/reporte.html.j2 tests
git commit -m "feat: la página empieza con 'Qué hacer' y explica cada sección"
```

---

### Task 7: El correo solo avisa

**Files:**
- Modify: `src/fantasy/reporte/correo.py` (`resumen`)
- Test: `tests/test_reporte_claro.py`; ajustes en `tests/test_reporte.py`, `tests/test_reporte_fase1.py`

**Interfaces:**
- Consumes: `acciones.contar`, `Reporte.acciones`, `hora_sidney`.

- [ ] **Step 1: Write the failing tests** (agrega a `tests/test_reporte_claro.py`)

```python
from fantasy.decision.acciones import Accion
from fantasy.reporte import correo


def test_correo_cuenta_y_lista_urgentes():
    r = _r()
    r.acciones = [Accion("urgente", "Cambia tu alineación: Entra X", "p",
                         pd.Timestamp("2026-10-04 17:00", tz="UTC"), "alineacion"),
                  Accion("recomendado", "Pide a D", "p", None, "lugar"),
                  Accion("radar", "R", "p", None, "rol")]
    texto = correo.resumen(r)
    assert texto.splitlines()[0] == "Reporte del viernes (semana 4): 1 urgente, 1 recomendada."
    assert "🔴 Cambia tu alineación: Entra X — antes del lun 04:00" in texto
    assert "Pide a D" not in texto


def test_correo_nada_que_hacer():
    r = _r()
    r.acciones = [Accion("radar", "R", "p", None, "rol")]
    assert correo.resumen(r) == "Reporte del viernes (semana 4): nada que hacer."
```

(El 2026-10-04 17:00 UTC es lunes 04:00 en Sídney, ya con horario de verano.)

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest -q tests/test_reporte_claro.py -k correo`
Expected: FAIL.

- [ ] **Step 3: Implement** — reemplaza `resumen` en `src/fantasy/reporte/correo.py`:

```python
from fantasy.decision.acciones import contar
from fantasy.reporte.armado import DIAS, Reporte, hora_sidney


def resumen(r: Reporte) -> str:
    n = contar(r.acciones)
    cabeza = f"Reporte {DIAS[r.tipo]} (semana {r.semana})"
    if not n["urgente"] and not n["recomendado"]:
        return f"{cabeza}: nada que hacer."
    partes = []
    if n["urgente"]:
        partes.append(f"{n['urgente']} urgente{'s' if n['urgente'] > 1 else ''}")
    if n["recomendado"]:
        partes.append(f"{n['recomendado']} recomendada{'s' if n['recomendado'] > 1 else ''}")
    lineas = [f"{cabeza}: {', '.join(partes)}."]
    for a in r.acciones:
        if a.urgencia == "urgente":
            limite = f" — antes del {hora_sidney(a.limite)}" if a.limite is not None else ""
            lineas.append(f"🔴 {a.texto}{limite}")
    return "\n".join(lineas)
```

Quita el import de `estado` si queda sin uso.

- [ ] **Step 4: Ajustar pruebas viejas del correo**

- `tests/test_reporte.py::test_resumen_y_envio_por_gmail`: `texto.startswith("Semana 3 · reporte del viernes · SIN VALIDAR")` → `texto.startswith("Reporte del viernes (semana 3)")`.
- `tests/test_reporte.py::test_correo_dice_si_el_sugerido_esta_lesionado`: bórrala (el correo ya no detalla agencia libre; la lesión se ve en la página — `test_agencia_libre_muestra_la_lesion` lo cubre).
- `tests/test_reporte_fase1.py::test_martes_trae_intercambios`: `"Intercambio:" in correo.resumen(r)` → `"Reporte del martes (semana 4)" in correo.resumen(r)`.
- `tests/test_reporte_fase1.py::test_correo_avisa_lesiones_y_relleno`: bórrala (el detalle de intercambios vive en la página; `test_martes_trae_intercambios` verifica que salen ahí).

- [ ] **Step 5: Run the full suite and lint**

Run: `uv run ruff check src tests && uv run pytest -q`
Expected: `All checks passed!` y todas las pruebas pasan.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/reporte/correo.py tests
git commit -m "feat: el correo solo avisa cuántas acciones hay y lista las urgentes"
```

---

### Task 8: Verificación con el reporte real y documentación

**Files:**
- Modify: `docs/ESTADO.md`, `README.md` (si describe el reporte)

- [ ] **Step 1: Generar el reporte del viernes con la instantánea real**

```bash
uv run fantasy reporte --tipo viernes --salida "$TMP/claro" --sin-correo --forzar --instantanea tests/fixtures/sem04_2026-10-02
```

(`--instantanea` corre sin red desde esa carpeta y no guarda una instantánea nueva.)

Expected: escribe `reportes/2026-sem04-viernes.html`. Ábrelo y verifica a ojo: "Qué hacer" arriba, 🟡 con el lugar vacío (respaldo de Gibbs/Jeanty/Amon-Ra), Daniels solo en ⚪ o en la tabla, "Lugares libres: 1 de 14", sin "Modelo".

- [ ] **Step 2: Actualizar `docs/ESTADO.md`**

En la tabla "Dónde estamos", fila de la Fase 0, cambia "Qué hace" a: `Martes 19:00, viernes 08:00 y domingo 20:00 (Sídney): "Qué hacer" con urgencia (🔴/🟡/⚪), plantilla con lugares libres, plan si alguien queda fuera, agencia libre e intercambios por semana, ganando rol (libres y banca de rivales). Página en GitHub Pages + aviso por Gmail.` Y agrega en "Cómo operar" o al final: `Sincronía: en la sesión se corre este mismo reporte; si la sesión recomienda algo distinto, se dice por qué y se anota.`

- [ ] **Step 3: Commit**

```bash
git add docs/ESTADO.md README.md
git commit -m "docs: el reporte claro en el estado del proyecto"
```

- [ ] **Step 4: PR**

```bash
git push -u origin reporte-claro
gh pr create --base main --title "Reporte claro: qué hacer con urgencia" --body "Implementa docs/superpowers/specs/2026-10-02-reporte-claro-design.md: Qué hacer con urgencia (🔴/🟡/⚪), lugar libre (respaldo o moneda de cambio), plantilla con banca, motivo de sin respaldo, ganancia por semana, ganando rol con banca de rivales, correo como aviso. Pruebas: uv run pytest -q y ruff limpios. No toca el modelo."
```
