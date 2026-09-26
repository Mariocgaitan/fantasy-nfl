# Fase 0 — Reporte provisional: plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el martes 2026-09-29 a las 19:00 (Sídney) GitHub Actions genere solo el
reporte de la semana 4 de BanKAI (alineación óptima, reemplazos condicionales, agencia
libre, quién gana rol), lo publique en GitHub Pages y avise por correo vía ntfy.

**Architecture:** Paquete Python `fantasy` con módulos pequeños que se pasan DataFrames
de columnas fijas: `ingesta` (ESPN, nflverse) → `almacen` (instantáneas crudas en la rama
`datos`) → `proyeccion` (ESPN manda) → `decision` → `reporte` (HTML + correo). Un único
punto de entrada `fantasy reporte` corre igual local y en Actions, y con `--instantanea`
corre sin red.

**Tech Stack:** Python 3.12, uv, pandas, Jinja2, tzdata, pytest, ruff, GitHub Actions,
GitHub Pages, ntfy.sh.

**Spec:** `docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md` (fase 0).
Requisitos y decisiones: `PROYECTO.md`.

## Global Constraints

- Cero costo: solo servicios gratis (GitHub en repo público, ntfy.sh, API pública de ESPN, nflverse).
- Nada escribe en ESPN en esta fase: solo lectura.
- Cada reporte dice arriba **"SIN VALIDAR — decide la proyección de ESPN"**.
- Liga: `TEMPORADA = 2026`, `LIGA_ID = 898754986`, `EQUIPO_ID = 5` (BanKAI).
- Titulares: QB×1, RB×2, WR×2, TE×1, FLEX×1 (RB/WR/TE). Sin K ni D/ST.
- Reportes (hora de Sídney, `Australia/Sydney`): martes 19:00, viernes 08:00, domingo 20:00; tolerancia de retraso 90 min.
- Semanas valoradas: desde la semana objetivo hasta la 17, todas con el mismo peso.
- P(jugar): ACTIVE 1.0, QUESTIONABLE 0.75, DOUBTFUL 0.25, DAY_TO_DAY 0.5, OUT/INJURY_RESERVE/SUSPENSION 0.0, estado desconocido 0.5.
- Regla (a): umbral de 2.0 puntos de proyección.
- Nunca decidir en silencio con datos incompletos: `DatosInvalidos` → sin reporte, correo con la causa, exit 1.
- Textos visibles para Mario en español.
- Secretos (`NTFY_TOPIC`, `NTFY_EMAIL`) solo como secretos de GitHub; nunca en el código ni en los logs.

## Review Focus

1. **Un jugador que aparece a la vez en una plantilla y en la lista de agentes libres** (las dos se bajan en momentos distintos): tiene que contar como del equipo y no sugerirse como alta. Prueba en la tarea 2.
2. **Un jugador sin proyección para una semana** (descanso o id ausente): cuenta 0 y no truena. Prueba en la tarea 5.
3. **Jugadores bloqueados en la banca o en el FLEX** a media jornada: el optimizador los deja donde están y nunca sugiere soltarlos. Pruebas en las tareas 6 y 7.
4. **El reporte del martes cuando ESPN todavía no avanza de semana**: tiene que ser de la semana siguiente. Prueba en la tarea 8.
5. **El cron corre dos veces para el mismo reporte** (dos horas UTC programadas, o un reintento): la segunda corrida no lo regenera ni reenvía el correo. Prueba en la tarea 10.

---

## Estructura de archivos

```
pyproject.toml, .python-version, uv.lock
src/fantasy/
  __init__.py
  config.py              constantes de la liga
  esquemas.py            columnas fijas + DatosInvalidos + validar()
  ingesta/__init__.py
  ingesta/espn.py        HTTP con reintentos + parsers de ESPN
  ingesta/nflverse.py    descarga + uso semanal por jugador
  almacen/__init__.py
  almacen/instantaneas.py  guardar/cargar respuestas crudas (.json(.gz)/.csv(.gz))
  proyeccion/__init__.py
  proyeccion/riesgo.py   P(jugar) por estado
  proyeccion/espn.py     tabla por semana (proy, p_jugar, esperado, inicio_utc)
  decision/__init__.py
  decision/alineacion.py óptima, regla (a), reemplazos (b)
  decision/agencia_libre.py  altas/bajas por valor semana a semana, ganando rol
  horario.py             qué reporte toca, semana objetivo
  reporte/__init__.py
  reporte/armado.py      crudos → Reporte (orquestación pura)
  reporte/html.py        Reporte → HTML (Jinja2)
  reporte/plantillas/reporte.html.j2
  reporte/correo.py      ntfy → correo
  cli.py                 `fantasy reporte`
tests/
  conftest.py            fixtures de la semana 3
  fixtures/sem03_2026-09-25/  (ya existe: liga.json, calendario.json, agentes_libres.json,
                               proyecciones.json, semanal.csv, snaps.csv, jugadores.csv)
  test_*.py
.github/workflows/ci.yml, reporte.yml
README.md
```

Las fixtures son datos reales. `liga.json` y `calendario.json` son del viernes 2026-09-25
a las 02:26 UTC, en pleno partido del jueves de la semana 3 (Watson y Golden bloqueados).
`proyecciones.json` y `agentes_libres.json` son del 2026-09-26 (por eso Collins aparece OUT).

---

### Task 1: Esqueleto del proyecto, esquemas y CI

**Files:**
- Create: `pyproject.toml`, `.python-version`, `src/fantasy/__init__.py`, `src/fantasy/config.py`, `src/fantasy/esquemas.py`, `tests/conftest.py`, `tests/test_esquemas.py`, `.github/workflows/ci.yml`
- Create (vacíos): `src/fantasy/ingesta/__init__.py`, `src/fantasy/almacen/__init__.py`, `src/fantasy/proyeccion/__init__.py`, `src/fantasy/decision/__init__.py`, `src/fantasy/reporte/__init__.py`

**Interfaces:**
- Produces: `fantasy.config.{TEMPORADA, LIGA_ID, EQUIPO_ID, SEMANA_FINAL}`; `fantasy.esquemas.{PLANTILLAS, JUGADORES, PROYECCIONES, PARTIDOS, USO, DatosInvalidos, validar(df, columnas, nombre) -> pd.DataFrame}`; fixture pytest `fixture_dir -> Path`.

- [ ] **Step 1: Crear `pyproject.toml` y `.python-version`**

```toml
[project]
name = "fantasy"
version = "0.1.0"
description = "Recomendador semanal para la liga CACHORRITAS (ESPN fantasy NFL)"
requires-python = ">=3.12"
dependencies = ["pandas>=2.2", "jinja2>=3.1", "tzdata>=2024.1"]

[project.scripts]
fantasy = "fantasy.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/fantasy"]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"
```

`.python-version`:
```
3.12
```

- [ ] **Step 2: Crear `config.py` y los `__init__.py`**

`src/fantasy/__init__.py`, `src/fantasy/ingesta/__init__.py`, `src/fantasy/almacen/__init__.py`, `src/fantasy/proyeccion/__init__.py`, `src/fantasy/decision/__init__.py`, `src/fantasy/reporte/__init__.py`: archivos vacíos.

`src/fantasy/config.py`:
```python
"""Constantes de la liga CACHORRITAS."""

TEMPORADA = 2026
LIGA_ID = 898754986
EQUIPO_ID = 5  # BanKAI
SEMANA_FINAL = 17  # última semana de playoffs de la liga
```

- [ ] **Step 3: Escribir la prueba que falla**

`tests/conftest.py`:
```python
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "sem03_2026-09-25"


@pytest.fixture
def fixture_dir() -> Path:
    return FIXTURES
```

`tests/test_esquemas.py`:
```python
import pandas as pd
import pytest

from fantasy.esquemas import PROYECCIONES, DatosInvalidos, validar


def test_validar_devuelve_columnas_en_orden():
    df = pd.DataFrame({"puntos": [1.0], "semana": [3], "jugador_id": [7], "extra": [0]})
    out = validar(df, PROYECCIONES, "proyecciones")
    assert list(out.columns) == ["jugador_id", "semana", "puntos"]


def test_validar_falla_si_falta_columna():
    with pytest.raises(DatosInvalidos, match="proyecciones: faltan columnas"):
        validar(pd.DataFrame({"semana": [3]}), PROYECCIONES, "proyecciones")
```

- [ ] **Step 4: Correr y ver que falla**

Run: `uv sync && uv run pytest tests/test_esquemas.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'fantasy.esquemas'`

- [ ] **Step 5: Implementar `esquemas.py`**

```python
"""Columnas fijas de las tablas que se pasan entre módulos."""

import pandas as pd

PLANTILLAS = ["equipo_id", "jugador_id", "slot", "bloqueado"]
JUGADORES = [
    "jugador_id", "nombre", "pos", "equipo_nfl_id", "lesion",
    "equipo_fantasy_id", "disponibilidad", "dueno_pct", "dueno_cambio",
]
PROYECCIONES = ["jugador_id", "semana", "puntos"]
PARTIDOS = ["equipo_nfl_id", "semana", "inicio_utc", "rival_nfl_id"]
USO = ["jugador_id", "semana", "snaps_pct", "targets", "acarreos"]


class DatosInvalidos(Exception):
    """Los datos de una fuente no alcanzan para decidir."""


def validar(df: pd.DataFrame, columnas: list[str], nombre: str) -> pd.DataFrame:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise DatosInvalidos(f"{nombre}: faltan columnas {faltan}")
    return df[columnas].reset_index(drop=True)
```

- [ ] **Step 6: Correr y ver que pasa**

Run: `uv run pytest tests/test_esquemas.py -v`
Expected: 2 passed

- [ ] **Step 7: CI**

`.github/workflows/ci.yml`:
```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:
permissions:
  contents: read
jobs:
  pruebas:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run pytest -q
```

Run: `uv run ruff check .`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .python-version uv.lock src tests/conftest.py tests/test_esquemas.py .github/workflows/ci.yml
git commit -m "feat: esqueleto del paquete, esquemas de tablas y CI"
```

---

### Task 2: Parsers de ESPN

**Files:**
- Create: `src/fantasy/ingesta/espn.py`
- Test: `tests/test_espn_parsers.py`

**Interfaces:**
- Consumes: `esquemas.*`, fixture `fixture_dir`.
- Produces (en `fantasy.ingesta.espn`):
  - `POSICIONES: dict[int, str]`, `SLOTS: dict[int, str]`
  - `semana_actual(liga: dict) -> int`
  - `validar_liga(liga: dict) -> None` (lanza `DatosInvalidos`)
  - `parsear_plantillas(liga: dict) -> pd.DataFrame` (PLANTILLAS; `slot` ∈ QB/RB/WR/TE/FLEX/BANCA/IR/OTRO)
  - `parsear_proyecciones(proyecciones: dict, temporada: int) -> pd.DataFrame` (PROYECCIONES)
  - `parsear_jugadores(proyecciones: dict, liga: dict, libres: dict) -> pd.DataFrame` (JUGADORES; `disponibilidad` ∈ EQUIPO/WAIVERS/LIBRE; `equipo_fantasy_id` 0 si no tiene dueño)
  - `parsear_calendario(calendario: dict) -> pd.DataFrame` (PARTIDOS; `inicio_utc` tz-aware UTC)

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_espn_parsers.py`:
```python
import json

import pandas as pd
import pytest

from fantasy.esquemas import DatosInvalidos
from fantasy.ingesta import espn

WATSON, GOLDEN = 4248528, 4701936  # bloqueados: jugaron el jueves de la semana 3


def _cargar(fixture_dir, nombre):
    return json.loads((fixture_dir / nombre).read_text(encoding="utf-8"))


@pytest.fixture
def crudos(fixture_dir):
    return {n: _cargar(fixture_dir, f"{n}.json")
            for n in ("liga", "calendario", "agentes_libres", "proyecciones")}


def _id(jugadores, nombre):
    return int(jugadores.loc[jugadores.nombre == nombre, "jugador_id"].iloc[0])


def test_semana_actual(crudos):
    assert espn.semana_actual(crudos["liga"]) == 3


def test_plantillas_de_bankai(crudos):
    p = espn.parsear_plantillas(crudos["liga"])
    mia = p[p.equipo_id == 5]
    assert len(mia) == 14
    assert p.equipo_id.nunique() == 8
    assert sorted(mia.slot.value_counts().items()) == [
        ("BANCA", 7), ("FLEX", 1), ("QB", 1), ("RB", 2), ("TE", 1), ("WR", 2)]
    assert set(mia[mia.bloqueado].jugador_id) == {WATSON, GOLDEN}


def test_liga_incompleta_falla(crudos):
    liga = dict(crudos["liga"], teams=crudos["liga"]["teams"][:7])
    with pytest.raises(DatosInvalidos, match="7 equipos"):
        espn.parsear_plantillas(liga)


def test_proyecciones_semanales(crudos):
    j = espn.parsear_jugadores(crudos["proyecciones"], crudos["liga"], crudos["agentes_libres"])
    pr = espn.parsear_proyecciones(crudos["proyecciones"], 2026)
    shough = pr[pr.jugador_id == _id(j, "Tyler Shough")].set_index("semana").puntos
    assert shough[3] == pytest.approx(18.83, abs=0.01)
    assert shough[8] == 0.0  # descanso de los Saints
    assert set(range(1, 19)) <= set(shough.index)


def test_jugadores_disponibilidad_y_lesion(crudos):
    j = espn.parsear_jugadores(crudos["proyecciones"], crudos["liga"], crudos["agentes_libres"])
    fila = j[j.nombre == "Tyler Shough"].iloc[0]
    assert (fila.pos, fila.equipo_fantasy_id, fila.disponibilidad) == ("QB", 5, "EQUIPO")
    assert j[j.nombre == "Nico Collins"].iloc[0].lesion == "OUT"
    assert set(j.pos) <= {"QB", "RB", "WR", "TE"}
    assert j.jugador_id.is_unique
    libres = j[j.disponibilidad != "EQUIPO"]
    assert len(libres) > 50 and (libres.equipo_fantasy_id == 0).all()


def test_jugador_en_plantilla_y_en_libres_cuenta_como_del_equipo(crudos):
    # Review Focus 1: las dos listas se bajan en momentos distintos.
    libres = json.loads(json.dumps(crudos["agentes_libres"]))
    liga = crudos["liga"]
    entrada = liga["teams"][4]["roster"]["entries"][0]
    duplicado = {"id": entrada["playerId"], "status": "WAIVERS", "player": {"ownership": {}}}
    libres["players"].append(duplicado)
    j = espn.parsear_jugadores(crudos["proyecciones"], liga, libres)
    fila = j[j.jugador_id == entrada["playerId"]].iloc[0]
    assert fila.disponibilidad == "EQUIPO" and fila.equipo_fantasy_id == 5


def test_calendario(crudos):
    c = espn.parsear_calendario(crudos["calendario"])
    gb = c[(c.equipo_nfl_id == 9) & (c.semana == 3)].iloc[0]
    assert gb.inicio_utc == pd.Timestamp("2026-09-25 00:15", tz="UTC")
    assert c[(c.equipo_nfl_id == 18) & (c.semana == 8)].empty  # NO descansa en la 8
```


- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_espn_parsers.py -v`
Expected: FAIL con `ImportError: cannot import name 'espn'`

- [ ] **Step 3: Implementar los parsers**

`src/fantasy/ingesta/espn.py`:
```python
"""Lectura de la API pública de ESPN fantasy: descarga y parsers."""

import pandas as pd

from fantasy.esquemas import (
    JUGADORES, PARTIDOS, PLANTILLAS, PROYECCIONES, DatosInvalidos, validar,
)

POSICIONES = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
SLOTS = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 23: "FLEX", 20: "BANCA", 21: "IR"}
EQUIPOS_LIGA = 8
MAX_PLANTILLA = 15  # 14 + IR


def semana_actual(liga: dict) -> int:
    return int(liga["scoringPeriodId"])


def validar_liga(liga: dict) -> None:
    equipos = liga.get("teams") or []
    if len(equipos) != EQUIPOS_LIGA:
        raise DatosInvalidos(f"liga: {len(equipos)} equipos, se esperaban {EQUIPOS_LIGA}")
    for t in equipos:
        n = len((t.get("roster") or {}).get("entries") or [])
        if not 1 <= n <= MAX_PLANTILLA:
            raise DatosInvalidos(f"liga: el equipo {t.get('id')} tiene {n} jugadores")


def parsear_plantillas(liga: dict) -> pd.DataFrame:
    validar_liga(liga)
    filas = [
        {
            "equipo_id": t["id"],
            "jugador_id": e["playerId"],
            "slot": SLOTS.get(e["lineupSlotId"], "OTRO"),
            "bloqueado": bool(e["playerPoolEntry"].get("lineupLocked", False)),
        }
        for t in liga["teams"]
        for e in t["roster"]["entries"]
    ]
    return validar(pd.DataFrame(filas, columns=PLANTILLAS), PLANTILLAS, "plantillas")


def parsear_proyecciones(proyecciones: dict, temporada: int) -> pd.DataFrame:
    filas = [
        {"jugador_id": pe["id"], "semana": int(s["scoringPeriodId"]),
         "puntos": float(s.get("appliedTotal") or 0.0)}
        for pe in proyecciones.get("players", [])
        for s in pe["player"].get("stats") or []
        if s.get("seasonId") == temporada and s.get("statSourceId") == 1
        and s.get("statSplitTypeId") == 1 and s.get("scoringPeriodId", 0) > 0
    ]
    df = pd.DataFrame(filas, columns=PROYECCIONES)
    if df.empty:
        raise DatosInvalidos("proyecciones: ESPN no devolvió proyecciones semanales")
    return validar(df, PROYECCIONES, "proyecciones")


def _dueno_pct(jugador: dict) -> tuple[float, float]:
    o = jugador.get("ownership") or {}
    return float(o.get("percentOwned", 0.0)), float(o.get("percentChange", 0.0))


def parsear_jugadores(proyecciones: dict, liga: dict, libres: dict) -> pd.DataFrame:
    dueno: dict[int, int] = {}
    propiedad: dict[int, tuple[float, float]] = {}
    for t in liga["teams"]:
        for e in t["roster"]["entries"]:
            dueno[e["playerId"]] = t["id"]
            propiedad[e["playerId"]] = _dueno_pct(e["playerPoolEntry"]["player"])
    en_waivers = set()
    for pe in libres.get("players", []):
        propiedad.setdefault(pe["id"], _dueno_pct(pe.get("player") or {}))
        if pe.get("status") == "WAIVERS":
            en_waivers.add(pe["id"])
    filas = []
    for pe in proyecciones.get("players", []):
        p = pe["player"]
        pos = POSICIONES.get(p.get("defaultPositionId"))
        if pos is None:
            continue
        jid = pe["id"]
        equipo = dueno.get(jid, 0)
        if equipo:
            disponibilidad = "EQUIPO"
        else:
            disponibilidad = "WAIVERS" if jid in en_waivers else "LIBRE"
        pct, cambio = propiedad.get(jid, (0.0, 0.0))
        filas.append({
            "jugador_id": jid, "nombre": p.get("fullName", str(jid)), "pos": pos,
            "equipo_nfl_id": int(p.get("proTeamId") or 0),
            "lesion": p.get("injuryStatus") or "ACTIVE",
            "equipo_fantasy_id": equipo, "disponibilidad": disponibilidad,
            "dueno_pct": pct, "dueno_cambio": cambio,
        })
    df = pd.DataFrame(filas, columns=JUGADORES).drop_duplicates("jugador_id")
    return validar(df, JUGADORES, "jugadores")


def parsear_calendario(calendario: dict) -> pd.DataFrame:
    filas = []
    for t in calendario["settings"]["proTeams"]:
        if t["id"] == 0:
            continue
        for semana, juegos in (t.get("proGamesByScoringPeriod") or {}).items():
            for g in juegos:
                local = g["homeProTeamId"] == t["id"]
                filas.append({
                    "equipo_nfl_id": t["id"], "semana": int(semana),
                    "inicio_utc": pd.Timestamp(g["date"], unit="ms", tz="UTC"),
                    "rival_nfl_id": g["awayProTeamId"] if local else g["homeProTeamId"],
                })
    return validar(pd.DataFrame(filas, columns=PARTIDOS), PARTIDOS, "calendario")
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_espn_parsers.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/ingesta/espn.py tests/test_espn_parsers.py
git commit -m "feat: parsers de ESPN (plantillas, proyecciones semanales, jugadores, calendario)"
```

---

### Task 3: Descarga de ESPN con reintentos

**Files:**
- Modify: `src/fantasy/ingesta/espn.py` (añadir al final)
- Test: `tests/test_espn_descarga.py`

**Interfaces:**
- Consumes: `validar_liga`, `DatosInvalidos`.
- Produces:
  - `obtener_json(url: str, filtro: dict | None = None, *, abrir=urllib.request.urlopen, intentos: int = 3, espera: float = 2.0, dormir=time.sleep) -> dict`
  - `bajar_espn(temporada: int, liga_id: int, *, get=obtener_json) -> dict[str, dict]` con llaves `liga`, `calendario`, `agentes_libres`, `proyecciones`.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_espn_descarga.py`:
```python
import io
import json
import urllib.error

import pytest

from fantasy.esquemas import DatosInvalidos
from fantasy.ingesta import espn


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def abridor(respuestas, vistos):
    def abrir(req, timeout):
        vistos.append(req)
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return Respuesta(json.dumps(r).encode())
    return abrir


def test_reintenta_errores_de_servidor_y_manda_filtro():
    vistos = []
    err = urllib.error.HTTPError("u", 503, "caido", {}, None)
    datos = espn.obtener_json("https://x", {"a": 1}, abrir=abridor([err, {"ok": 1}], vistos),
                              dormir=lambda s: None)
    assert datos == {"ok": 1}
    assert len(vistos) == 2
    assert json.loads(vistos[0].get_header("X-fantasy-filter")) == {"a": 1}


def test_error_4xx_no_se_reintenta():
    vistos = []
    err = urllib.error.HTTPError("u", 400, "mal", {}, None)
    with pytest.raises(DatosInvalidos, match="400"):
        espn.obtener_json("https://x", abrir=abridor([err], vistos), dormir=lambda s: None)
    assert len(vistos) == 1


def test_se_rinde_tras_tres_intentos():
    err = urllib.error.URLError("sin red")
    with pytest.raises(DatosInvalidos, match="3 intentos"):
        espn.obtener_json("https://x", abrir=abridor([err, err, err], []), dormir=lambda s: None)


def test_bajar_espn_pide_proyecciones_en_lotes(fixture_dir):
    liga = json.loads((fixture_dir / "liga.json").read_text(encoding="utf-8"))
    libres = json.loads((fixture_dir / "agentes_libres.json").read_text(encoding="utf-8"))
    llamadas = []

    def get(url, filtro=None):
        llamadas.append((url, filtro))
        if "view=mTeam" in url:
            return liga
        if "proTeamSchedules" in url:
            return {"settings": {"proTeams": []}}
        if "leagues/" in url and "kona_player_info" in url:
            return libres
        ids = filtro["players"]["filterIds"]["value"]
        return {"players": [{"id": i, "player": {"stats": []}} for i in ids]}

    crudos = espn.bajar_espn(2026, 898754986, get=get)
    lotes = [f for u, f in llamadas if "leaguedefaults/3" in u]
    total = len({e["playerId"] for t in liga["teams"] for e in t["roster"]["entries"]}
                | {p["id"] for p in libres["players"]})
    assert all(len(f["players"]["filterIds"]["value"]) <= 50 for f in lotes)
    assert len(crudos["proyecciones"]["players"]) == total
    assert set(crudos) == {"liga", "calendario", "agentes_libres", "proyecciones"}
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_espn_descarga.py -v`
Expected: FAIL con `AttributeError: module 'fantasy.ingesta.espn' has no attribute 'obtener_json'`

- [ ] **Step 3: Implementar**

Añadir al principio de `src/fantasy/ingesta/espn.py`, junto a los imports:
```python
import json
import time
import urllib.error
import urllib.request
```

Añadir al final:
```python
LECTURA = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons"
AGENTE = "fantasy-nfl (github.com/Mariocgaitan/fantasy-nfl)"
LOTE = 50


def obtener_json(url, filtro=None, *, abrir=urllib.request.urlopen, intentos=3, espera=2.0,
                 dormir=time.sleep) -> dict:
    headers = {"User-Agent": AGENTE}
    if filtro is not None:
        headers["X-Fantasy-Filter"] = json.dumps(filtro)
    ultimo: Exception | None = None
    for i in range(intentos):
        try:
            with abrir(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise DatosInvalidos(f"ESPN respondió {e.code} en {url}") from e
            ultimo = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo = e
        if i < intentos - 1:
            dormir(espera * 2**i)
    raise DatosInvalidos(f"ESPN no respondió tras {intentos} intentos: {ultimo}")


def bajar_espn(temporada: int, liga_id: int, *, get=obtener_json) -> dict[str, dict]:
    base = f"{LECTURA}/{temporada}/segments/0"
    liga = get(f"{base}/leagues/{liga_id}?view=mTeam&view=mRoster&view=mSettings&view=mMatchup")
    validar_liga(liga)
    calendario = get(f"{LECTURA}/{temporada}?view=proTeamSchedules_wl")
    libres = get(f"{base}/leagues/{liga_id}?view=kona_player_info", {"players": {
        "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
        "filterSlotIds": {"value": [0, 2, 4, 6]},
        "limit": 150,
        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
    }})
    ids = sorted({e["playerId"] for t in liga["teams"] for e in t["roster"]["entries"]}
                 | {pe["id"] for pe in libres.get("players", [])})
    jugadores: list[dict] = []
    for i in range(0, len(ids), LOTE):
        filtro = {"players": {"filterIds": {"value": ids[i:i + LOTE]}}}
        jugadores += get(f"{base}/leaguedefaults/3?view=kona_player_info", filtro)["players"]
    return {"liga": liga, "calendario": calendario, "agentes_libres": libres,
            "proyecciones": {"players": jugadores}}
```

(Con `filterIds` no se manda `limit`: ESPN responde 400. Las proyecciones de todas las semanas solo salen de `leaguedefaults/3`; el endpoint de la liga solo da la semana en curso.)

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_espn_descarga.py -v`
Expected: 4 passed

- [ ] **Step 5: Prueba de humo contra ESPN real (manual, con red)**

Run: `uv run python -c "from fantasy.ingesta.espn import *; c=bajar_espn(2026,898754986); print(len(parsear_proyecciones(c['proyecciones'],2026)), semana_actual(c['liga']))"`
Expected: más de 3000 filas y la semana actual (3 o 4).

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/ingesta/espn.py tests/test_espn_descarga.py
git commit -m "feat: descarga de ESPN con reintentos y proyecciones en lotes"
```

---

### Task 4: nflverse (uso semanal) e instantáneas

**Files:**
- Create: `src/fantasy/ingesta/nflverse.py`, `src/fantasy/almacen/instantaneas.py`
- Test: `tests/test_nflverse.py`, `tests/test_instantaneas.py`

**Interfaces:**
- Produces:
  - `nflverse.bajar_nflverse(temporada: int, *, abrir=urllib.request.urlopen) -> dict[str, str]` con llaves `semanal`, `snaps`, `jugadores` (CSV como texto, ya recortado a las columnas usadas)
  - `nflverse.uso_semanal(semanal: pd.DataFrame, snaps: pd.DataFrame, jugadores: pd.DataFrame) -> pd.DataFrame` (USO; `jugador_id` = id de ESPN, `snaps_pct` en 0–1)
  - `nflverse.tablas(crudos: dict[str, str]) -> pd.DataFrame` (USO desde los textos CSV)
  - `instantaneas.guardar(raiz: Path, temporada: int, semana: int, momento: datetime, crudos: dict) -> Path`
  - `instantaneas.cargar(carpeta: Path) -> dict[str, dict | str]` (lee `.json`, `.json.gz`, `.csv`, `.csv.gz`; la llave es el nombre sin extensión)

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_nflverse.py`:
```python
import pandas as pd
import pytest

from fantasy.ingesta import nflverse

WASHINGTON = 4432620  # id ESPN de Parker Washington


def test_uso_semanal_une_estadisticas_y_snaps(fixture_dir):
    u = nflverse.uso_semanal(
        pd.read_csv(fixture_dir / "semanal.csv"),
        pd.read_csv(fixture_dir / "snaps.csv"),
        pd.read_csv(fixture_dir / "jugadores.csv"),
    )
    pw = u[u.jugador_id == WASHINGTON].set_index("semana")
    assert pw.loc[2, "targets"] == 12
    assert pw.loc[2, "snaps_pct"] == pytest.approx(0.81)
    assert pw.loc[1, "snaps_pct"] == pytest.approx(0.61)
    assert u.jugador_id.dtype == "int64"
    assert u.snaps_pct.between(0, 1).all()


def test_tablas_desde_texto(fixture_dir):
    crudos = {n: (fixture_dir / f"{n}.csv").read_text(encoding="utf-8")
              for n in ("semanal", "snaps", "jugadores")}
    assert WASHINGTON in set(nflverse.tablas(crudos).jugador_id)
```

`tests/test_instantaneas.py`:
```python
from datetime import datetime

from fantasy.almacen import instantaneas


def test_guardar_y_cargar_ida_y_vuelta(tmp_path):
    crudos = {"liga": {"teams": [1, 2]}, "semanal": "a,b\n1,2\n"}
    carpeta = instantaneas.guardar(tmp_path, 2026, 4, datetime(2026, 9, 29, 19, 0), crudos)
    assert carpeta == tmp_path / "instantaneas" / "2026" / "sem04" / "2026-09-29T19-00"
    assert sorted(p.name for p in carpeta.iterdir()) == ["liga.json.gz", "semanal.csv.gz"]
    assert instantaneas.cargar(carpeta) == crudos


def test_cargar_lee_fixtures_sin_comprimir(fixture_dir):
    crudos = instantaneas.cargar(fixture_dir)
    assert {"liga", "calendario", "agentes_libres", "proyecciones",
            "semanal", "snaps", "jugadores"} <= set(crudos)
    assert isinstance(crudos["semanal"], str)
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_nflverse.py tests/test_instantaneas.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar `nflverse.py`**

```python
"""Uso semanal por jugador (snaps, targets, acarreos) desde nflverse."""

import io
import urllib.error
import urllib.request

import pandas as pd

from fantasy.esquemas import USO, DatosInvalidos, validar

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
ARCHIVOS = {
    "semanal": "stats_player/stats_player_week_{t}.csv",
    "snaps": "snap_counts/snap_counts_{t}.csv",
    "jugadores": "players/players.csv",
}
COLUMNAS = {
    "semanal": ["player_id", "player_display_name", "position", "team", "season", "week",
                "season_type", "carries", "targets", "receptions", "fantasy_points_ppr"],
    "snaps": ["season", "week", "player", "pfr_player_id", "position", "team",
              "offense_snaps", "offense_pct"],
    "jugadores": ["gsis_id", "pfr_id", "espn_id", "display_name", "position"],
}
POSICIONES = ["QB", "RB", "WR", "TE"]


def bajar_nflverse(temporada: int, *, abrir=urllib.request.urlopen) -> dict[str, str]:
    crudos = {}
    for nombre, ruta in ARCHIVOS.items():
        url = f"{BASE}/{ruta.format(t=temporada)}"
        try:
            with abrir(url, timeout=60) as r:
                df = pd.read_csv(io.BytesIO(r.read()), low_memory=False)
        except (urllib.error.URLError, TimeoutError, pd.errors.ParserError) as e:
            raise DatosInvalidos(f"nflverse: no se pudo bajar {nombre}: {e}") from e
        df = df[[c for c in COLUMNAS[nombre] if c in df.columns]]
        if "position" in df.columns:
            df = df[df["position"].isin(POSICIONES)]
        if nombre == "jugadores":
            df = df[df["espn_id"].notna()]
        crudos[nombre] = df.to_csv(index=False)
    return crudos


def uso_semanal(semanal: pd.DataFrame, snaps: pd.DataFrame,
                jugadores: pd.DataFrame) -> pd.DataFrame:
    ids = jugadores.dropna(subset=["espn_id"])
    s = semanal[semanal["season_type"] == "REG"].merge(
        ids[["gsis_id", "espn_id"]], left_on="player_id", right_on="gsis_id")
    s = s.groupby(["espn_id", "week"], as_index=False)[["targets", "carries"]].sum()
    n = snaps.merge(ids[["pfr_id", "espn_id"]], left_on="pfr_player_id", right_on="pfr_id")
    n = n.groupby(["espn_id", "week"], as_index=False)["offense_pct"].max()
    u = s.merge(n, on=["espn_id", "week"], how="outer").fillna(0)
    u = u.rename(columns={"espn_id": "jugador_id", "week": "semana",
                          "offense_pct": "snaps_pct", "carries": "acarreos"})
    u["jugador_id"] = u["jugador_id"].astype("int64")
    u["semana"] = u["semana"].astype("int64")
    return validar(u, USO, "uso")


def tablas(crudos: dict[str, str]) -> pd.DataFrame:
    leer = {n: pd.read_csv(io.StringIO(crudos[n]), low_memory=False)
            for n in ("semanal", "snaps", "jugadores")}
    return uso_semanal(leer["semanal"], leer["snaps"], leer["jugadores"])
```

- [ ] **Step 4: Implementar `instantaneas.py`**

```python
"""Instantáneas: las respuestas crudas de cada corrida, comprimidas y fechadas."""

import gzip
import json
from datetime import datetime
from pathlib import Path


def guardar(raiz: Path, temporada: int, semana: int, momento: datetime,
            crudos: dict) -> Path:
    carpeta = (raiz / "instantaneas" / str(temporada) / f"sem{semana:02d}"
               / momento.strftime("%Y-%m-%dT%H-%M"))
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, valor in crudos.items():
        if isinstance(valor, str):
            (carpeta / f"{nombre}.csv.gz").write_bytes(gzip.compress(valor.encode("utf-8")))
        else:
            datos = json.dumps(valor, ensure_ascii=False).encode("utf-8")
            (carpeta / f"{nombre}.json.gz").write_bytes(gzip.compress(datos))
    return carpeta


def cargar(carpeta: Path) -> dict[str, dict | str]:
    crudos: dict[str, dict | str] = {}
    for f in sorted(carpeta.iterdir()):
        nombre = f.name
        comprimido = nombre.endswith(".gz")
        base = nombre[:-3] if comprimido else nombre
        if not base.endswith((".json", ".csv")):
            continue
        datos = f.read_bytes()
        texto = (gzip.decompress(datos) if comprimido else datos).decode("utf-8")
        if base.endswith(".json"):
            crudos[base[:-5]] = json.loads(texto)
        else:
            crudos[base[:-4]] = texto
    return crudos
```

- [ ] **Step 5: Correr y ver que pasan**

Run: `uv run pytest tests/test_nflverse.py tests/test_instantaneas.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/fantasy/ingesta/nflverse.py src/fantasy/almacen/instantaneas.py tests/test_nflverse.py tests/test_instantaneas.py
git commit -m "feat: uso semanal desde nflverse e instantáneas crudas comprimidas"
```

---

### Task 5: Proyección y riesgo (tabla por semana)

**Files:**
- Create: `src/fantasy/proyeccion/riesgo.py`, `src/fantasy/proyeccion/espn.py`
- Test: `tests/test_proyeccion.py`

**Interfaces:**
- Consumes: tablas JUGADORES, PROYECCIONES, PARTIDOS.
- Produces:
  - `riesgo.p_jugar(estado: str | None) -> float`
  - `proyeccion.espn.tabla_semana(jugadores, proyecciones, partidos, semana: int, *, con_lesion: bool) -> pd.DataFrame` = columnas de JUGADORES + `proy`, `p_jugar`, `esperado`, `inicio_utc` (NaT si descansa).

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_proyeccion.py`:
```python
import pandas as pd
import pytest

from fantasy.proyeccion.espn import tabla_semana
from fantasy.proyeccion.riesgo import p_jugar


def test_p_jugar():
    assert p_jugar("ACTIVE") == 1.0
    assert p_jugar(None) == 1.0
    assert p_jugar("QUESTIONABLE") == 0.75
    assert p_jugar("DOUBTFUL") == 0.25
    assert p_jugar("OUT") == 0.0
    assert p_jugar("ALGO_NUEVO") == 0.5


def _jugadores():
    return pd.DataFrame({
        "jugador_id": [1, 2, 3], "nombre": ["A", "B", "C"], "pos": ["QB", "WR", "RB"],
        "equipo_nfl_id": [18, 9, 99], "lesion": ["ACTIVE", "QUESTIONABLE", "ACTIVE"],
        "equipo_fantasy_id": [5, 5, 0], "disponibilidad": ["EQUIPO", "EQUIPO", "LIBRE"],
        "dueno_pct": [90.0, 50.0, 1.0], "dueno_cambio": [0.0, 0.0, 0.0],
    })


def test_tabla_semana_con_lesion_y_sin_proyeccion():
    proy = pd.DataFrame({"jugador_id": [1, 2], "semana": [4, 4], "puntos": [20.0, 10.0]})
    partidos = pd.DataFrame({"equipo_nfl_id": [18, 9], "semana": [4, 4],
                             "inicio_utc": pd.to_datetime(["2026-10-04 17:00", "2026-10-02 00:15"],
                                                          utc=True),
                             "rival_nfl_id": [1, 2]})
    t = tabla_semana(_jugadores(), proy, partidos, 4, con_lesion=True).set_index("jugador_id")
    assert t.loc[2, "esperado"] == pytest.approx(7.5)
    assert t.loc[3, "proy"] == 0.0 and t.loc[3, "esperado"] == 0.0  # Review Focus 2
    assert pd.isna(t.loc[3, "inicio_utc"])  # su equipo no juega (descanso)
    sin = tabla_semana(_jugadores(), proy, partidos, 4, con_lesion=False).set_index("jugador_id")
    assert sin.loc[2, "esperado"] == 10.0
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_proyeccion.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

`src/fantasy/proyeccion/riesgo.py`:
```python
"""Probabilidad de jugar según el estado de lesión de ESPN (valores sin validar)."""

P_JUGAR = {
    "ACTIVE": 1.0, "QUESTIONABLE": 0.75, "DOUBTFUL": 0.25, "DAY_TO_DAY": 0.5,
    "OUT": 0.0, "INJURY_RESERVE": 0.0, "SUSPENSION": 0.0,
}
DESCONOCIDO = 0.5


def p_jugar(estado: str | None) -> float:
    return P_JUGAR.get(estado or "ACTIVE", DESCONOCIDO)
```

`src/fantasy/proyeccion/espn.py`:
```python
"""Proyección que manda en la etapa provisional: la de ESPN."""

import pandas as pd

from fantasy.proyeccion.riesgo import p_jugar


def tabla_semana(jugadores: pd.DataFrame, proyecciones: pd.DataFrame, partidos: pd.DataFrame,
                 semana: int, *, con_lesion: bool) -> pd.DataFrame:
    pr = proyecciones.loc[proyecciones.semana == semana, ["jugador_id", "puntos"]]
    t = jugadores.merge(pr, on="jugador_id", how="left").rename(columns={"puntos": "proy"})
    t["proy"] = t["proy"].fillna(0.0)
    t["p_jugar"] = t["lesion"].map(p_jugar) if con_lesion else 1.0
    t["esperado"] = t["proy"] * t["p_jugar"]
    ini = partidos.loc[partidos.semana == semana, ["equipo_nfl_id", "inicio_utc"]]
    return t.merge(ini, on="equipo_nfl_id", how="left")
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_proyeccion.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/proyeccion tests/test_proyeccion.py
git commit -m "feat: tabla semanal con proyección de ESPN y probabilidad de jugar"
```

---

### Task 6: Alineación óptima, regla (a) y reemplazos (b)

**Files:**
- Create: `src/fantasy/decision/alineacion.py`
- Test: `tests/test_alineacion.py`

**Interfaces:**
- Consumes: tabla de `tabla_semana` más columnas `slot` (slot actual en ESPN: QB/RB/WR/TE/FLEX/BANCA/IR) y `bloqueado` (bool).
- Produces:
  - `CUPOS`, `FLEX_POS`, `TITULARES = ("QB", "RB", "WR", "TE", "FLEX")`
  - `@dataclass(frozen=True) Alineacion(slots: tuple[tuple[str, int], ...], esperado: float)` con método `ids() -> set[int]`; `slots` ordenado QB, RB, RB, WR, WR, TE, FLEX
  - `optima(t: pd.DataFrame) -> Alineacion`
  - `aplicar_regla_duda(al: Alineacion, t: pd.DataFrame, umbral: float = 2.0) -> Alineacion`
  - `@dataclass(frozen=True) Reemplazo(slot: str, titular: int, suplente: int | None)`
  - `reemplazos(al: Alineacion, t: pd.DataFrame) -> list[Reemplazo]` (omite titulares bloqueados)

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_alineacion.py`:
```python
import itertools
import json

import pandas as pd
import pytest

from fantasy.decision.alineacion import (
    CUPOS, FLEX_POS, aplicar_regla_duda, optima, reemplazos,
)
from fantasy.ingesta import espn
from fantasy.proyeccion.espn import tabla_semana


@pytest.fixture
def semana3(fixture_dir):
    c = {n: json.loads((fixture_dir / f"{n}.json").read_text(encoding="utf-8"))
         for n in ("liga", "calendario", "agentes_libres", "proyecciones")}
    j = espn.parsear_jugadores(c["proyecciones"], c["liga"], c["agentes_libres"])
    t = tabla_semana(j, espn.parsear_proyecciones(c["proyecciones"], 2026),
                     espn.parsear_calendario(c["calendario"]), 3, con_lesion=True)
    p = espn.parsear_plantillas(c["liga"])
    mia = p[p.equipo_id == 5][["jugador_id", "slot", "bloqueado"]]
    return t.merge(mia, on="jugador_id")


def nombres(t, ids):
    return set(t.set_index("jugador_id").loc[list(ids), "nombre"])


def test_optima_semana3_coincide_con_la_alineacion_de_mario(semana3):
    al = optima(semana3)
    actuales = semana3[semana3.slot.isin(["QB", "RB", "WR", "TE", "FLEX"])].jugador_id
    assert al.ids() == set(actuales)
    assert nombres(semana3, al.ids()) == {
        "Tyler Shough", "Jahmyr Gibbs", "Ashton Jeanty", "Parker Washington",
        "Christian Watson", "Trey McBride", "James Cook III"}
    assert [s for s, _ in al.slots] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]


def test_bloqueado_en_la_banca_no_entra(semana3):
    # Review Focus 3: Golden jugó el jueves desde la banca y ya no se puede mover.
    t = semana3.copy()
    t.loc[t.nombre == "Matthew Golden", "proy"] = 40.0
    t.loc[t.nombre == "Matthew Golden", "esperado"] = 40.0
    assert "Matthew Golden" not in nombres(t, optima(t).ids())


def test_bloqueado_en_flex_se_queda_en_flex():
    t = pd.DataFrame({
        "jugador_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "nombre": list("ABCDEFGH"),
        "pos": ["QB", "RB", "RB", "WR", "WR", "TE", "WR", "RB"],
        "esperado": [20, 15, 14, 13, 12, 10, 5, 30.0],
        "slot": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BANCA"],
        "bloqueado": [False] * 6 + [True, False],
    })
    al = optima(t)
    assert ("FLEX", 7) in al.slots
    assert 8 in al.ids()  # el RB de 30 desplaza al RB de 14
    assert 3 not in al.ids()


def test_optima_es_exacta_contra_enumeracion(semana3):
    t = semana3[~semana3.bloqueado].reset_index(drop=True)
    mejor = 0.0
    por_pos = {p: t[t.pos == p] for p in CUPOS}
    for qb in itertools.combinations(por_pos["QB"].jugador_id, 1):
        for rb in itertools.combinations(por_pos["RB"].jugador_id, 2):
            for wr in itertools.combinations(por_pos["WR"].jugador_id, 2):
                for te in itertools.combinations(por_pos["TE"].jugador_id, 1):
                    usados = set(qb + rb + wr + te)
                    resto = t[t.pos.isin(FLEX_POS) & ~t.jugador_id.isin(usados)]
                    flex = resto.esperado.max() if len(resto) else 0.0
                    total = t[t.jugador_id.isin(usados)].esperado.sum() + flex
                    mejor = max(mejor, total)
    assert optima(t).esperado == pytest.approx(mejor)


def test_regla_duda_prefiere_al_sano_si_la_diferencia_es_chica():
    # El RB de 12 se queda con el FLEX; la pelea es entre el WR en duda (5) y el WR sano (8).
    t = pd.DataFrame({
        "jugador_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "nombre": list("ABCDEFGH"),
        "pos": ["QB", "RB", "RB", "WR", "WR", "TE", "RB", "WR"],
        "proy": [20, 15, 14, 13, 5.0, 10, 12, 3.5],
        "lesion": ["ACTIVE"] * 4 + ["QUESTIONABLE", "ACTIVE", "ACTIVE", "ACTIVE"],
        "slot": ["BANCA"] * 8, "bloqueado": [False] * 8,
    })
    t["p_jugar"] = t.lesion.map({"ACTIVE": 1.0, "QUESTIONABLE": 0.75})
    t["esperado"] = t.proy * t.p_jugar
    al = optima(t)
    assert 5 in al.ids()  # 3.75 esperado le gana a 3.5
    al2 = aplicar_regla_duda(al, t)
    assert 5 not in al2.ids() and 8 in al2.ids()  # 5.0 - 3.5 < 2.0


def test_reemplazos_respetan_horarios(semana3):
    al = optima(semana3)
    idx = semana3.set_index("jugador_id")
    r = {idx.loc[x.titular, "nombre"]: (idx.loc[x.suplente, "nombre"] if x.suplente else None)
         for x in reemplazos(al, semana3)}
    assert r["Tyler Shough"] is None        # ningún QB útil juega a la par o después
    assert r["Trey McBride"] is None        # no hay TE en la banca
    assert r["Jahmyr Gibbs"] == "Breece Hall"
    assert r["Ashton Jeanty"] == "D'Andre Swift"  # Hall juega antes que Jeanty
    assert r["Parker Washington"] == "Malik Nabers"
    assert r["James Cook III"] == "Breece Hall"
    assert "Christian Watson" not in r      # ya está bloqueado
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_alineacion.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

`src/fantasy/decision/alineacion.py`:
```python
"""Alineación óptima, regla de jugadores en duda y reemplazos condicionales."""

from dataclasses import dataclass

import pandas as pd

CUPOS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_POS = ("RB", "WR", "TE")
TITULARES = ("QB", "RB", "WR", "TE", "FLEX")
EN_DUDA = ("QUESTIONABLE", "DOUBTFUL", "DAY_TO_DAY")
UMBRAL_DUDA = 2.0


@dataclass(frozen=True)
class Alineacion:
    slots: tuple[tuple[str, int], ...]
    esperado: float

    def ids(self) -> set[int]:
        return {j for _, j in self.slots}


@dataclass(frozen=True)
class Reemplazo:
    slot: str
    titular: int
    suplente: int | None


def _armar(elegidos: list[tuple[str, int]], t: pd.DataFrame) -> Alineacion:
    orden = {s: i for i, s in enumerate(TITULARES)}
    elegidos = sorted(elegidos, key=lambda x: orden[x[0]])
    esperado = float(t.set_index("jugador_id").loc[[j for _, j in elegidos], "esperado"].sum())
    return Alineacion(tuple((s, int(j)) for s, j in elegidos), esperado)


def optima(t: pd.DataFrame) -> Alineacion:
    """Exacta: con cupos por posición y un solo FLEX, llenar cada posición con sus mejores
    y el FLEX con el mejor sobrante es óptimo. Los bloqueados quedan donde están."""
    fijos = t[t.bloqueado & t.slot.isin(TITULARES)]
    libres = t[~t.bloqueado].sort_values("esperado", ascending=False, kind="stable")
    elegidos = [(s, int(j)) for s, j in zip(fijos.slot, fijos.jugador_id)]
    usados = {j for _, j in elegidos}
    for pos, n in CUPOS.items():
        faltan = n - sum(1 for s, _ in elegidos if s == pos)
        cand = libres[(libres.pos == pos) & ~libres.jugador_id.isin(usados)].head(max(faltan, 0))
        for j in cand.jugador_id:
            elegidos.append((pos, int(j)))
            usados.add(int(j))
    if not any(s == "FLEX" for s, _ in elegidos):
        cand = libres[libres.pos.isin(FLEX_POS) & ~libres.jugador_id.isin(usados)].head(1)
        for j in cand.jugador_id:
            elegidos.append(("FLEX", int(j)))
    return _armar(elegidos, t)


def _posiciones(slot: str) -> tuple[str, ...]:
    return FLEX_POS if slot == "FLEX" else (slot,)


def aplicar_regla_duda(al: Alineacion, t: pd.DataFrame, umbral: float = UMBRAL_DUDA) -> Alineacion:
    idx = t.set_index("jugador_id")
    slots = list(al.slots)
    usados = al.ids()
    for i, (slot, j) in enumerate(slots):
        f = idx.loc[j]
        if f.bloqueado or f.lesion not in EN_DUDA:
            continue
        alt = t[~t.bloqueado & t.pos.isin(_posiciones(slot)) & (t.lesion == "ACTIVE")
                & ~t.jugador_id.isin(usados)]
        if alt.empty:
            continue
        mejor = alt.sort_values("proy", ascending=False, kind="stable").iloc[0]
        if f.proy - mejor.proy < umbral:
            slots[i] = (slot, int(mejor.jugador_id))
            usados = (usados - {j}) | {int(mejor.jugador_id)}
    return _armar(slots, t)


def reemplazos(al: Alineacion, t: pd.DataFrame) -> list[Reemplazo]:
    """Para cada titular movible, el mejor suplente que juega a la misma hora o después."""
    idx = t.set_index("jugador_id")
    banca = t[~t.jugador_id.isin(al.ids()) & ~t.bloqueado & (t.proy > 0) & (t.p_jugar > 0)
              & t.inicio_utc.notna()]
    salida = []
    for slot, j in al.slots:
        f = idx.loc[j]
        if f.bloqueado:
            continue
        cand = banca[banca.pos.isin(_posiciones(slot))]
        if pd.notna(f.inicio_utc):
            cand = cand[cand.inicio_utc >= f.inicio_utc]
        mejor = cand.sort_values("esperado", ascending=False, kind="stable").head(1)
        suplente = int(mejor.jugador_id.iloc[0]) if len(mejor) else None
        salida.append(Reemplazo(slot, int(j), suplente))
    return salida
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_alineacion.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/alineacion.py tests/test_alineacion.py
git commit -m "feat: alineación óptima exacta, regla de duda y reemplazos condicionales"
```

---

### Task 7: Agencia libre (altas, bajas y ganando rol)

**Files:**
- Create: `src/fantasy/decision/agencia_libre.py`
- Test: `tests/test_agencia_libre.py`

**Interfaces:**
- Consumes: `tabla_semana`, `optima`, `CUPOS`, `SEMANA_FINAL`.
- Produces:
  - `tablas_por_semana(jugadores, proyecciones, partidos, plantilla_mia: pd.DataFrame, semana: int, ahora: pd.Timestamp) -> dict[int, pd.DataFrame]` (cada tabla trae `slot` y `bloqueado`; en la semana objetivo, bloqueado = el de ESPN para los míos y "ya empezó su partido" para los demás; en semanas futuras, nadie bloqueado)
  - `valor_plantilla(ids: set[int], tablas: dict[int, pd.DataFrame]) -> float`
  - `recomendar(jugadores, tablas, mis_ids: set[int], semana: int, *, max_candidatos=30, max_sugerencias=5) -> pd.DataFrame` columnas `pedir, soltar, pos, ganancia` (ids; `ganancia` > 0; ordenado de mayor a menor)
  - `ganando_rol(uso: pd.DataFrame, jugadores: pd.DataFrame, *, umbral_snaps=0.15, umbral_oport=3.0, max_cambio_dueno=1.0) -> pd.DataFrame` columnas `jugador_id, nombre, pos, disponibilidad, snaps_antes, snaps_ahora, oport_antes, oport_ahora, dueno_pct, dueno_cambio`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_agencia_libre.py`:
```python
import json

import pandas as pd
import pytest

from fantasy.decision import agencia_libre as al
from fantasy.ingesta import espn


def _jug(filas):
    base = {"equipo_nfl_id": 1, "lesion": "ACTIVE", "equipo_fantasy_id": 0,
            "disponibilidad": "LIBRE", "dueno_pct": 1.0, "dueno_cambio": 0.0}
    return pd.DataFrame([{**base, **f} for f in filas])


def _tabla(jug, puntos):
    t = jug.copy()
    t["proy"] = t.jugador_id.map(puntos).fillna(0.0)
    t["p_jugar"] = 1.0
    t["esperado"] = t["proy"]
    t["inicio_utc"] = pd.Timestamp("2026-10-04 17:00", tz="UTC")
    t["slot"] = "BANCA"
    t["bloqueado"] = False
    return t


def _mia():
    filas = [
        {"jugador_id": 1, "nombre": "QB1", "pos": "QB"},
        {"jugador_id": 2, "nombre": "RB1", "pos": "RB"},
        {"jugador_id": 3, "nombre": "RB2", "pos": "RB"},
        {"jugador_id": 4, "nombre": "WR1", "pos": "WR"},
        {"jugador_id": 5, "nombre": "WR2", "pos": "WR"},
        {"jugador_id": 6, "nombre": "TE1", "pos": "TE"},
        {"jugador_id": 7, "nombre": "RB3", "pos": "RB"},
        {"jugador_id": 8, "nombre": "WR3", "pos": "WR"},
    ]
    return [dict(f, equipo_fantasy_id=5, disponibilidad="EQUIPO") for f in filas]


def test_alta_que_entra_de_titular_da_la_ganancia_exacta():
    jug = _jug(_mia() + [{"jugador_id": 99, "nombre": "LIBRE", "pos": "WR"}])
    puntos = {1: 20, 2: 15, 3: 14, 4: 13, 5: 12, 6: 10, 7: 11, 8: 2, 99: 16}
    tablas = {4: _tabla(jug, puntos), 5: _tabla(jug, puntos)}
    r = al.recomendar(jug, tablas, set(range(1, 9)), 4)
    top = r.iloc[0]
    # Entra de WR y el WR2 (12) pasa al FLEX en lugar del RB3 (11): +5 por semana, 2 semanas.
    assert (top.pedir, top.soltar) == (99, 8)
    assert top.ganancia == pytest.approx(10.0)
    assert (r.ganancia > 0).all() and r.ganancia.is_monotonic_decreasing


def test_seguro_cuando_no_hay_respaldo_en_la_posicion():
    jug = _jug(_mia() + [{"jugador_id": 98, "nombre": "QB LIBRE", "pos": "QB"}])
    puntos = {1: 20, 2: 15, 3: 14, 4: 13, 5: 12, 6: 10, 7: 11, 8: 2, 98: 15}
    tablas = {w: _tabla(jug, puntos) for w in (4, 5, 6)}
    r = al.recomendar(jug, tablas, set(range(1, 9)), 4)
    fila = r[r.pedir == 98].iloc[0]
    # No entra de titular (0 por alineación), pero cubre la única QB: 0.15 * 15 * 3 semanas.
    assert fila.ganancia == pytest.approx(0.15 * 15 * 3)
    assert fila.soltar == 8


def test_nunca_suelta_a_un_bloqueado():
    jug = _jug(_mia() + [{"jugador_id": 99, "nombre": "LIBRE", "pos": "WR"}])
    puntos = {1: 20, 2: 15, 3: 14, 4: 13, 5: 12, 6: 10, 7: 11, 8: 2, 99: 16}
    t4 = _tabla(jug, puntos)
    t4.loc[t4.jugador_id == 8, "bloqueado"] = True
    r = al.recomendar(jug, {4: t4}, set(range(1, 9)), 4)
    assert 8 not in set(r.soltar)


def test_semana3_real_no_suelta_bloqueados_ni_pide_a_duenos(fixture_dir):
    c = {n: json.loads((fixture_dir / f"{n}.json").read_text(encoding="utf-8"))
         for n in ("liga", "calendario", "agentes_libres", "proyecciones")}
    j = espn.parsear_jugadores(c["proyecciones"], c["liga"], c["agentes_libres"])
    p = espn.parsear_plantillas(c["liga"])
    mia = p[p.equipo_id == 5]
    tablas = al.tablas_por_semana(
        j, espn.parsear_proyecciones(c["proyecciones"], 2026),
        espn.parsear_calendario(c["calendario"]), mia, 3,
        pd.Timestamp("2026-09-25 02:26", tz="UTC"))
    assert set(tablas) == set(range(3, 18))
    r = al.recomendar(j, tablas, set(mia.jugador_id), 3, max_candidatos=10)
    nombres = j.set_index("jugador_id").nombre
    assert not {"Christian Watson", "Matthew Golden"} & set(nombres[r.soltar])
    assert set(j.set_index("jugador_id").loc[r.pedir, "disponibilidad"]) <= {"LIBRE", "WAIVERS"}
    assert len(r) >= 1


def test_ganando_rol_marca_al_que_sube_sin_que_el_mercado_lo_note():
    uso = pd.DataFrame({
        "jugador_id": [10, 10, 10, 11, 11, 11, 12, 12, 12],
        "semana": [1, 2, 3] * 3,
        "snaps_pct": [0.30, 0.60, 0.70, 0.80, 0.80, 0.80, 0.20, 0.60, 0.70],
        "targets": [1, 5, 6, 7, 7, 7, 1, 5, 6], "acarreos": [0] * 9,
    })
    jug = _jug([
        {"jugador_id": 10, "nombre": "Sube", "pos": "WR", "dueno_cambio": 0.2},
        {"jugador_id": 11, "nombre": "Igual", "pos": "WR"},
        {"jugador_id": 12, "nombre": "YaLoVieron", "pos": "WR", "dueno_cambio": 12.0},
    ])
    r = al.ganando_rol(uso, jug)
    assert list(r.nombre) == ["Sube"]
    assert r.iloc[0].snaps_antes == pytest.approx(0.30)
    assert r.iloc[0].snaps_ahora == pytest.approx(0.65)


def test_ganando_rol_sin_historia_devuelve_vacio():
    uso = pd.DataFrame({"jugador_id": [10], "semana": [1], "snaps_pct": [0.5],
                        "targets": [3], "acarreos": [0]})
    assert al.ganando_rol(uso, _jug([{"jugador_id": 10, "nombre": "X", "pos": "WR"}])).empty
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_agencia_libre.py -v`
Expected: FAIL con `ImportError`

- [ ] **Step 3: Implementar**

`src/fantasy/decision/agencia_libre.py`:
```python
"""Agencia libre: a quién pedir, a quién soltar y quién viene ganando rol."""

import pandas as pd

from fantasy.config import SEMANA_FINAL
from fantasy.decision.alineacion import CUPOS, optima
from fantasy.proyeccion.espn import tabla_semana

SEGURO = 0.15          # fracción de sus puntos que vale un respaldo (sin validar)
SEMANAS_SEGURO = 3
SEGURO_POS = ("QB", "TE")  # RB y WR ya se cubren entre sí por el FLEX
COLUMNAS_ROL = ["jugador_id", "nombre", "pos", "disponibilidad", "snaps_antes", "snaps_ahora",
                "oport_antes", "oport_ahora", "dueno_pct", "dueno_cambio"]


def tablas_por_semana(jugadores, proyecciones, partidos, plantilla_mia, semana, ahora):
    tablas = {}
    for w in range(semana, SEMANA_FINAL + 1):
        t = tabla_semana(jugadores, proyecciones, partidos, w, con_lesion=(w == semana))
        if w == semana:
            t = t.merge(plantilla_mia[["jugador_id", "slot", "bloqueado"]],
                        on="jugador_id", how="left")
            empezo = t["inicio_utc"].notna() & (t["inicio_utc"] <= ahora)
            t["bloqueado"] = t["bloqueado"].where(t["bloqueado"].notna(), empezo).astype(bool)
            t["slot"] = t["slot"].fillna("BANCA")
        else:
            t["slot"] = "BANCA"
            t["bloqueado"] = False
        tablas[w] = t
    return tablas


def valor_plantilla(ids: set[int], tablas: dict[int, pd.DataFrame]) -> float:
    return sum(optima(t[t.jugador_id.isin(ids)]).esperado for t in tablas.values())


def _seguro(cand: pd.Series, ids: set[int], jugadores: pd.DataFrame,
            tablas: dict[int, pd.DataFrame], semana: int) -> float:
    pos = cand.pos
    if pos not in SEGURO_POS:
        return 0.0
    sanos = jugadores[jugadores.jugador_id.isin(ids) & (jugadores.pos == pos)
                      & (jugadores.lesion == "ACTIVE")]
    if len(sanos) > CUPOS.get(pos, 0):
        return 0.0
    semanas = [w for w in range(semana, semana + SEMANAS_SEGURO) if w in tablas]
    puntos = sum(float(tablas[w].loc[tablas[w].jugador_id == cand.jugador_id, "proy"].sum())
                 for w in semanas)
    return SEGURO * puntos


def recomendar(jugadores, tablas, mis_ids, semana, *, max_candidatos=30, max_sugerencias=5):
    futuro = pd.concat(tablas.values())
    total = futuro.groupby("jugador_id")["proy"].sum()
    libres = jugadores[jugadores.disponibilidad.isin(["LIBRE", "WAIVERS"])
                       & ~jugadores.jugador_id.isin(mis_ids)]
    libres = libres.assign(total=libres.jugador_id.map(total).fillna(0.0))
    candidatos = libres.sort_values("total", ascending=False).head(max_candidatos)
    t0 = tablas[semana]
    bloqueados = set(t0.loc[t0.bloqueado & t0.jugador_id.isin(mis_ids), "jugador_id"])
    soltables = [j for j in mis_ids if j not in bloqueados]
    base = valor_plantilla(mis_ids, tablas)
    filas = []
    for _, cand in candidatos.iterrows():
        for s in soltables:
            nuevos = (mis_ids - {s}) | {int(cand.jugador_id)}
            ganancia = valor_plantilla(nuevos, tablas) - base
            ganancia += _seguro(cand, mis_ids - {s}, jugadores, tablas, semana)
            filas.append({"pedir": int(cand.jugador_id), "soltar": int(s),
                          "pos": cand.pos, "ganancia": ganancia})
    r = pd.DataFrame(filas, columns=["pedir", "soltar", "pos", "ganancia"])
    r = r[r.ganancia > 0].sort_values("ganancia", ascending=False, kind="stable")
    r = r.drop_duplicates("pedir")
    return r.head(max_sugerencias).reset_index(drop=True)


def ganando_rol(uso, jugadores, *, umbral_snaps=0.15, umbral_oport=3.0, max_cambio_dueno=1.0):
    semanas = sorted(uso.semana.unique())
    if len(semanas) < 2:
        return pd.DataFrame(columns=COLUMNAS_ROL)
    recientes = semanas[-2:] if len(semanas) >= 3 else semanas[-1:]
    u = uso.assign(oport=uso.targets + uso.acarreos, reciente=uso.semana.isin(recientes))
    g = u.groupby(["jugador_id", "reciente"])[["snaps_pct", "oport"]].mean().unstack("reciente")
    g = g.dropna()
    if g.empty:
        return pd.DataFrame(columns=COLUMNAS_ROL)
    d = pd.DataFrame({
        "snaps_antes": g[("snaps_pct", False)], "snaps_ahora": g[("snaps_pct", True)],
        "oport_antes": g[("oport", False)], "oport_ahora": g[("oport", True)],
    }).reset_index()
    sube = ((d.snaps_ahora - d.snaps_antes >= umbral_snaps)
            | (d.oport_ahora - d.oport_antes >= umbral_oport))
    d = d[sube].merge(jugadores, on="jugador_id")
    d = d[(d.disponibilidad != "EQUIPO") & (d.dueno_cambio <= max_cambio_dueno)]
    d = d.assign(delta=d.snaps_ahora - d.snaps_antes).sort_values("delta", ascending=False)
    return d[COLUMNAS_ROL].reset_index(drop=True)
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_agencia_libre.py -v`
Expected: 6 passed. `test_semana3_real_...` recorre 15 semanas × 10 candidatos × 12 soltables; si tarda más de 60 s, mide con `--durations=5` antes de optimizar `optima`.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/agencia_libre.py tests/test_agencia_libre.py
git commit -m "feat: agencia libre por valor semana a semana y detección de rol"
```

---

### Task 8: Horario y semana objetivo

**Files:**
- Create: `src/fantasy/horario.py`
- Test: `tests/test_horario.py`

**Interfaces:**
- Produces:
  - `ZONA = ZoneInfo("Australia/Sydney")`
  - `reporte_que_toca(ahora: datetime) -> str | None` ("martes" | "viernes" | "domingo")
  - `semana_objetivo(semana_espn: int, partidos: pd.DataFrame, ahora: pd.Timestamp) -> int`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_horario.py`:
```python
from datetime import datetime, timezone

import pandas as pd
import pytest

from fantasy.horario import reporte_que_toca, semana_objetivo


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


@pytest.mark.parametrize("momento,esperado", [
    ("2026-09-29T09:00", "martes"),    # 19:00 AEST
    ("2026-09-29T08:00", None),        # 18:00 AEST: todavía no
    ("2026-10-06T08:00", "martes"),    # 19:00 AEDT (después del 4-oct)
    ("2026-10-06T09:00", "martes"),    # 20:00 AEDT: dentro de la tolerancia
    ("2026-10-06T10:31", None),        # 21:31: fuera de la tolerancia
    ("2026-10-01T22:00", "viernes"),   # viernes 2-oct 08:00 AEST
    ("2026-10-04T09:00", "domingo"),   # domingo 4-oct 20:00 AEDT (primer día de verano)
    ("2026-11-03T08:00", "martes"),    # EE. UU. ya cambió de horario; Sídney no se mueve
    ("2026-09-30T09:00", None),        # miércoles
])
def test_reporte_que_toca(momento, esperado):
    assert reporte_que_toca(utc(momento)) == esperado


def test_semana_objetivo_avanza_cuando_ya_empezo_el_ultimo_partido(fixture_dir):
    # Review Focus 4
    import json

    from fantasy.ingesta.espn import parsear_calendario
    cal = json.loads((fixture_dir / "calendario.json").read_text(encoding="utf-8"))
    p = parsear_calendario(cal)
    assert semana_objetivo(3, p, pd.Timestamp("2026-09-25 02:26", tz="UTC")) == 3
    assert semana_objetivo(3, p, pd.Timestamp("2026-09-29 09:00", tz="UTC")) == 4
    assert semana_objetivo(4, p, pd.Timestamp("2026-09-29 09:00", tz="UTC")) == 4
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_horario.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar**

`src/fantasy/horario.py`:
```python
"""Cuándo toca cada reporte (hora de Sídney) y de qué semana es."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

ZONA = ZoneInfo("Australia/Sydney")
REPORTES = {  # día de la semana (lunes = 0), hora local
    "martes": (1, time(19, 0)),
    "viernes": (4, time(8, 0)),
    "domingo": (6, time(20, 0)),
}
TOLERANCIA = timedelta(minutes=90)


def reporte_que_toca(ahora: datetime) -> str | None:
    local = ahora.astimezone(ZONA)
    for tipo, (dia, hora) in REPORTES.items():
        if local.weekday() != dia:
            continue
        objetivo = datetime.combine(local.date(), hora, tzinfo=ZONA)
        if objetivo <= local < objetivo + TOLERANCIA:
            return tipo
    return None


def semana_objetivo(semana_espn: int, partidos: pd.DataFrame, ahora: pd.Timestamp) -> int:
    ultimo = partidos.loc[partidos.semana == semana_espn, "inicio_utc"].max()
    return semana_espn + 1 if pd.notna(ultimo) and ultimo <= ahora else semana_espn
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_horario.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/horario.py tests/test_horario.py
git commit -m "feat: horario de reportes en hora de Sídney y semana objetivo"
```

---

### Task 9: Armado del reporte, HTML y correo

**Files:**
- Create: `src/fantasy/reporte/armado.py`, `src/fantasy/reporte/html.py`, `src/fantasy/reporte/plantillas/reporte.html.j2`, `src/fantasy/reporte/correo.py`
- Test: `tests/test_reporte.py`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces:
  - `armado.Reporte` (dataclass) con campos `tipo: str, semana: int, generado: str, esperado: float, alineacion: list[dict], cambios: list[str], reemplazos: list[dict], agencia: list[dict], rol: list[dict], avisos: list[str]`
  - `armado.armar(crudos: dict, ahora: pd.Timestamp, tipo: str, equipo_id: int, avisos: list[str] | None = None) -> Reporte`
  - `html.generar_html(r: Reporte) -> str`
  - `correo.resumen(r: Reporte) -> str`
  - `correo.enviar(tema: str, destino: str, titulo: str, cuerpo: str, enlace: str | None, *, abrir=urllib.request.urlopen) -> None`

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_reporte.py`:
```python
import urllib.parse

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte import correo
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

AHORA = pd.Timestamp("2026-09-25 02:26", tz="UTC")


def test_armar_semana3(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    assert r.semana == 3
    assert [f["slot"] for f in r.alineacion] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]
    assert r.cambios == []  # la alineación de Mario ya era la óptima
    shough = next(x for x in r.reemplazos if x["titular"] == "Tyler Shough")
    assert shough["suplente"] is None
    assert len(r.agencia) >= 1
    assert all(a["ganancia"] > 0 for a in r.agencia)


def test_armar_martes_es_de_la_semana_siguiente(fixture_dir):
    r = armar(cargar(fixture_dir), pd.Timestamp("2026-09-29 09:00", tz="UTC"), "martes", 5)
    assert r.semana == 4
    assert not any(f["bloqueado"] for f in r.alineacion)


def test_html_marca_sin_validar(fixture_dir):
    html = generar_html(armar(cargar(fixture_dir), AHORA, "viernes", 5))
    assert "SIN VALIDAR" in html
    assert "Tyler Shough" in html
    assert "sin respaldo útil" in html
    assert '<meta name="viewport"' in html


def test_resumen_y_envio(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    texto = correo.resumen(r)
    assert texto.startswith("Semana 3 · reporte del viernes · SIN VALIDAR")
    vistos = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def abrir(req, timeout):
        vistos.append(req)
        return Resp()

    correo.enviar("tema-secreto", "yo@example.com", "Fantasy · semana 3", texto,
                  "https://x/reportes/a.html", abrir=abrir)
    req = vistos[0]
    q = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
    assert req.full_url.startswith("https://ntfy.sh/tema-secreto?")
    assert q["email"] == ["yo@example.com"] and q["click"] == ["https://x/reportes/a.html"]
    assert req.data.decode("utf-8") == texto and req.get_method() == "POST"
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_reporte.py -v`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementar `armado.py`**

```python
"""De respuestas crudas a un Reporte listo para pintar. Sin red ni disco."""

from dataclasses import dataclass, field

import pandas as pd

from fantasy.config import TEMPORADA
from fantasy.decision import agencia_libre
from fantasy.decision.alineacion import TITULARES, aplicar_regla_duda, optima, reemplazos
from fantasy.horario import ZONA, semana_objetivo
from fantasy.ingesta import espn, nflverse

DIAS = {"martes": "del martes", "viernes": "del viernes", "domingo": "del domingo"}


@dataclass
class Reporte:
    tipo: str
    semana: int
    generado: str
    esperado: float
    alineacion: list[dict]
    cambios: list[str]
    reemplazos: list[dict]
    agencia: list[dict]
    rol: list[dict]
    avisos: list[str] = field(default_factory=list)


def armar(crudos: dict, ahora: pd.Timestamp, tipo: str, equipo_id: int,
          avisos: list[str] | None = None) -> Reporte:
    avisos = list(avisos or [])
    liga = crudos["liga"]
    plantillas = espn.parsear_plantillas(liga)
    jugadores = espn.parsear_jugadores(crudos["proyecciones"], liga, crudos["agentes_libres"])
    proyecciones = espn.parsear_proyecciones(crudos["proyecciones"], TEMPORADA)
    partidos = espn.parsear_calendario(crudos["calendario"])
    semana = semana_objetivo(espn.semana_actual(liga), partidos, ahora)

    mia = plantillas[plantillas.equipo_id == equipo_id]
    if semana != espn.semana_actual(liga):  # semana nueva: nada bloqueado todavía
        mia = mia.assign(bloqueado=False)
    tablas = agencia_libre.tablas_por_semana(jugadores, proyecciones, partidos, mia, semana, ahora)
    t = tablas[semana]
    mis_ids = set(mia.jugador_id)
    tm = t[t.jugador_id.isin(mis_ids)]
    al = aplicar_regla_duda(optima(tm), tm)
    idx = tm.set_index("jugador_id")

    alineacion = [{
        "slot": s, "nombre": idx.loc[j, "nombre"], "pos": idx.loc[j, "pos"],
        "proy": round(float(idx.loc[j, "proy"]), 1), "lesion": idx.loc[j, "lesion"],
        "bloqueado": bool(idx.loc[j, "bloqueado"]),
    } for s, j in al.slots]
    actuales = set(tm.loc[tm.slot.isin(TITULARES), "jugador_id"])
    entran = [idx.loc[j, "nombre"] for j in al.ids() - actuales]
    salen = [idx.loc[j, "nombre"] for j in actuales - al.ids()]
    cambios = [f"Entra {e}" for e in sorted(entran)] + [f"Sale {s}" for s in sorted(salen)]

    def hora(j):
        v = idx.loc[j, "inicio_utc"]
        return v.tz_convert(ZONA).strftime("%a %H:%M") if pd.notna(v) else "descansa"

    remp = [{
        "slot": r.slot, "titular": idx.loc[r.titular, "nombre"], "hora": hora(r.titular),
        "suplente": idx.loc[r.suplente, "nombre"] if r.suplente else None,
        "hora_suplente": hora(r.suplente) if r.suplente else None,
    } for r in reemplazos(al, tm)]

    nombres = jugadores.set_index("jugador_id").nombre
    agencia = [{
        "pedir": nombres[x.pedir], "pos": x.pos, "soltar": nombres[x.soltar],
        "ganancia": round(float(x.ganancia), 1),
    } for x in agencia_libre.recomendar(jugadores, tablas, mis_ids, semana).itertuples()]

    rol: list[dict] = []
    if all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        uso = nflverse.tablas(crudos)
        rol = agencia_libre.ganando_rol(uso, jugadores).head(8).round(2).to_dict("records")
        ultima = int(uso.semana.max()) if len(uso) else 0
        avisos.append(f"Uso de jugadores (nflverse) hasta la semana {ultima}.")
    else:
        avisos.append("Sin datos de uso de nflverse: no se calculó quién gana rol.")

    return Reporte(
        tipo=tipo, semana=semana,
        generado=ahora.tz_convert(ZONA).strftime("%Y-%m-%d %H:%M"),
        esperado=round(al.esperado, 1), alineacion=alineacion, cambios=cambios,
        reemplazos=remp, agencia=agencia, rol=rol, avisos=avisos,
    )
```

- [ ] **Step 4: Implementar `html.py` y la plantilla**

`src/fantasy/reporte/html.py`:
```python
"""Reporte → HTML estático (GitHub Pages)."""

from dataclasses import asdict

from jinja2 import Environment, PackageLoader, select_autoescape

from fantasy.reporte.armado import DIAS, Reporte

_ENTORNO = Environment(loader=PackageLoader("fantasy.reporte", "plantillas"),
                       autoescape=select_autoescape(["html", "j2"]))


def generar_html(r: Reporte) -> str:
    return _ENTORNO.get_template("reporte.html.j2").render(dia=DIAS[r.tipo], **asdict(r))
```

`src/fantasy/reporte/plantillas/reporte.html.j2`:
```html
<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BanKAI · semana {{ semana }}</title>
<style>
  :root { --fondo:#fafaf7; --texto:#1c1c1a; --suave:#6b6b66; --aviso:#b3261e; --linea:#e3e2dc; }
  @media (prefers-color-scheme: dark) {
    :root { --fondo:#161615; --texto:#ecebe6; --suave:#a3a29c; --aviso:#ff8a80; --linea:#34332f; }
  }
  body { background:var(--fondo); color:var(--texto); font:16px/1.45 system-ui, sans-serif;
         margin:0 auto; max-width:720px; padding:16px; }
  .sinvalidar { border:2px solid var(--aviso); color:var(--aviso); padding:8px 12px;
                font-weight:700; border-radius:6px; }
  table { width:100%; border-collapse:collapse; margin:8px 0 20px; }
  td, th { border-bottom:1px solid var(--linea); padding:6px 4px; text-align:left; }
  .num { text-align:right; font-variant-numeric:tabular-nums; }
  small, .suave { color:var(--suave); }
</style>
</head>
<body>
<p class="sinvalidar">SIN VALIDAR — decide la proyección de ESPN</p>
<h1>Semana {{ semana }} · reporte {{ dia }}</h1>
<p class="suave">Generado {{ generado }} (Sídney) · proyección de titulares {{ esperado }}</p>

<h2>Alineación</h2>
{% if cambios %}<p><strong>Cambios:</strong> {{ cambios | join(" · ") }}</p>
{% else %}<p>Tu alineación actual ya es la óptima.</p>{% endif %}
<table>
  <tr><th>Lugar</th><th>Jugador</th><th class="num">Proy.</th><th>Estado</th></tr>
  {% for f in alineacion %}
  <tr><td>{{ f.slot }}</td><td>{{ f.nombre }} <small>{{ f.pos }}</small>{% if f.bloqueado %} 🔒{% endif %}</td>
      <td class="num">{{ f.proy }}</td><td>{{ f.lesion }}</td></tr>
  {% endfor %}
</table>

<h2>Si alguien queda inactivo</h2>
<table>
  <tr><th>Titular</th><th>Juega</th><th>Entra</th></tr>
  {% for r in reemplazos %}
  <tr><td>{{ r.titular }}</td><td>{{ r.hora }}</td>
      <td>{% if r.suplente %}{{ r.suplente }} <small>{{ r.hora_suplente }}</small>{% else %}<span class="suave">sin respaldo útil</span>{% endif %}</td></tr>
  {% endfor %}
</table>

<h2>Agencia libre</h2>
{% if agencia %}
<table>
  <tr><th>Pedir</th><th>Soltar</th><th class="num">Ganancia</th></tr>
  {% for a in agencia %}
  <tr><td>{{ a.pedir }} <small>{{ a.pos }}</small></td><td>{{ a.soltar }}</td><td class="num">+{{ a.ganancia }}</td></tr>
  {% endfor %}
</table>
<p class="suave">Ganancia: puntos proyectados extra de aquí a la semana 17.</p>
{% else %}<p>Ningún agente libre mejora tu plantilla.</p>{% endif %}

<h2>Ganando rol</h2>
{% if rol %}
<table>
  <tr><th>Jugador</th><th class="num">Snaps</th><th class="num">Oport.</th><th class="num">Dueños %</th></tr>
  {% for x in rol %}
  <tr><td>{{ x.nombre }} <small>{{ x.pos }}</small></td>
      <td class="num">{{ (x.snaps_antes*100)|round|int }}→{{ (x.snaps_ahora*100)|round|int }}%</td>
      <td class="num">{{ x.oport_antes }}→{{ x.oport_ahora }}</td><td class="num">{{ x.dueno_pct|round(1) }}</td></tr>
  {% endfor %}
</table>
{% else %}<p>Nadie libre viene ganando rol de forma clara.</p>{% endif %}

{% if avisos %}<h2>Avisos</h2><ul>{% for a in avisos %}<li>{{ a }}</li>{% endfor %}</ul>{% endif %}
</body>
</html>
```

- [ ] **Step 5: Implementar `correo.py`**

```python
"""Aviso por correo a través del reenvío de ntfy.sh (sin cuenta ni contraseña)."""

import urllib.parse
import urllib.request

from fantasy.reporte.armado import DIAS, Reporte


def resumen(r: Reporte) -> str:
    lineas = [f"Semana {r.semana} · reporte {DIAS[r.tipo]} · SIN VALIDAR (decide ESPN)"]
    lineas.append("Alineación: " + (" · ".join(r.cambios) if r.cambios else "sin cambios"))
    if r.agencia:
        a = r.agencia[0]
        lineas.append(f"Agencia libre: pedir {a['pedir']}, soltar {a['soltar']} (+{a['ganancia']})")
    sin = [x["titular"] for x in r.reemplazos if x["suplente"] is None]
    if sin:
        lineas.append("Sin respaldo útil: " + ", ".join(sin))
    return "\n".join(lineas)


def enviar(tema: str, destino: str, titulo: str, cuerpo: str, enlace: str | None, *,
           abrir=urllib.request.urlopen) -> None:
    params = {"title": titulo, "email": destino}
    if enlace:
        params["click"] = enlace
    url = f"https://ntfy.sh/{tema}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, data=cuerpo.encode("utf-8"), method="POST")
    with abrir(req, timeout=30):
        pass
```

- [ ] **Step 6: Correr y ver que pasan**

Run: `uv run pytest tests/test_reporte.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add src/fantasy/reporte tests/test_reporte.py
git commit -m "feat: armado del reporte, HTML para Pages y correo vía ntfy"
```

---

### Task 10: CLI `fantasy reporte`

**Files:**
- Create: `src/fantasy/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `bajar_espn`, `bajar_nflverse`, `guardar`, `cargar`, `armar`, `generar_html`, `resumen`, `enviar`, `reporte_que_toca`.
- Produces: `main(argv: list[str] | None = None, *, entorno: dict | None = None, enviar_fn=None) -> int`. Escribe `<salida>/reportes/<TEMPORADA>-semNN-<tipo>.html` y `<salida>/index.html`. Lee `NTFY_TOPIC`, `NTFY_EMAIL` y `PAGES_URL` del entorno.

- [ ] **Step 1: Escribir las pruebas que fallan**

`tests/test_cli.py`:
```python
import json
import shutil

from fantasy.cli import main

AHORA = "2026-09-25T02:26:00+00:00"
ENTORNO = {"NTFY_TOPIC": "t", "NTFY_EMAIL": "yo@example.com", "PAGES_URL": "https://p/"}


def _args(fixture_dir, salida, *extra):
    return ["reporte", "--tipo", "viernes", "--instantanea", str(fixture_dir),
            "--salida", str(salida), "--ahora", AHORA, *extra]


def test_corrida_completa_sin_red(fixture_dir, tmp_path):
    enviados = []
    codigo = main(_args(fixture_dir, tmp_path), entorno=ENTORNO,
                  enviar_fn=lambda *a, **k: enviados.append(a))
    assert codigo == 0
    html = (tmp_path / "reportes" / "2026-sem03-viernes.html").read_text(encoding="utf-8")
    assert "SIN VALIDAR" in html
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == html
    assert len(enviados) == 1
    assert enviados[0][4] == "https://p/reportes/2026-sem03-viernes.html"


def test_segunda_corrida_no_repite_ni_reenvia(fixture_dir, tmp_path):
    # Review Focus 5
    enviados = []
    envio = lambda *a, **k: enviados.append(a)  # noqa: E731
    assert main(_args(fixture_dir, tmp_path), entorno=ENTORNO, enviar_fn=envio) == 0
    destino = tmp_path / "reportes" / "2026-sem03-viernes.html"
    antes = destino.stat().st_mtime_ns
    assert main(_args(fixture_dir, tmp_path), entorno=ENTORNO, enviar_fn=envio) == 0
    assert destino.stat().st_mtime_ns == antes
    assert len(enviados) == 1


def test_auto_fuera_de_horario_no_hace_nada(fixture_dir, tmp_path):
    codigo = main(["reporte", "--tipo", "auto", "--instantanea", str(fixture_dir),
                   "--salida", str(tmp_path), "--ahora", "2026-09-30T09:00:00+00:00"],
                  entorno={}, enviar_fn=None)
    assert codigo == 0
    assert not (tmp_path / "reportes").exists()


def test_datos_invalidos_avisan_y_salen_con_error(fixture_dir, tmp_path):
    roto = tmp_path / "roto"
    shutil.copytree(fixture_dir, roto)
    liga = json.loads((roto / "liga.json").read_text(encoding="utf-8"))
    liga["teams"] = liga["teams"][:7]
    (roto / "liga.json").write_text(json.dumps(liga), encoding="utf-8")
    enviados = []
    codigo = main(_args(roto, tmp_path / "out"), entorno=ENTORNO,
                  enviar_fn=lambda *a, **k: enviados.append(a))
    assert codigo == 1
    assert "NO generado" in enviados[0][2]
    assert not (tmp_path / "out" / "reportes").exists()
```

- [ ] **Step 2: Correr y ver que fallan**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'fantasy.cli'`

- [ ] **Step 3: Implementar**

`src/fantasy/cli.py`:
```python
"""Punto de entrada: `fantasy reporte`."""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from fantasy.almacen import instantaneas
from fantasy.config import EQUIPO_ID, LIGA_ID, TEMPORADA
from fantasy.esquemas import DatosInvalidos
from fantasy.horario import ZONA, reporte_que_toca
from fantasy.ingesta.espn import bajar_espn
from fantasy.ingesta.nflverse import bajar_nflverse
from fantasy.reporte import correo
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fantasy")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("reporte", help="genera el reporte que toca")
    r.add_argument("--tipo", default="auto", choices=["auto", "martes", "viernes", "domingo"])
    r.add_argument("--salida", type=Path, default=Path("salida"))
    r.add_argument("--instantanea", type=Path, help="corre sin red desde esta carpeta")
    r.add_argument("--ahora", help="momento ISO con zona (para pruebas)")
    r.add_argument("--forzar", action="store_true", help="regenera aunque ya exista")
    r.add_argument("--sin-correo", action="store_true")
    return p


def main(argv: list[str] | None = None, *, entorno: dict | None = None, enviar_fn=None) -> int:
    a = _parser().parse_args(argv)
    entorno = dict(os.environ) if entorno is None else entorno
    enviar_fn = enviar_fn or correo.enviar
    ahora = datetime.fromisoformat(a.ahora) if a.ahora else datetime.now(timezone.utc)
    tipo = reporte_que_toca(ahora) if a.tipo == "auto" else a.tipo
    if tipo is None:
        print("No toca reporte a esta hora.")
        return 0
    tema, destino = entorno.get("NTFY_TOPIC"), entorno.get("NTFY_EMAIL")
    avisar = bool(tema and destino and not a.sin_correo)
    try:
        avisos: list[str] = []
        if a.instantanea:
            crudos = instantaneas.cargar(a.instantanea)
        else:
            crudos = bajar_espn(TEMPORADA, LIGA_ID)
            try:
                crudos |= bajar_nflverse(TEMPORADA)
            except DatosInvalidos as e:
                avisos.append(f"nflverse no disponible: {e}")
        reporte = armar(crudos, pd.Timestamp(ahora), tipo, EQUIPO_ID, avisos)
    except DatosInvalidos as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if avisar:
            enviar_fn(tema, destino, "Fantasy: reporte NO generado", str(e), None)
        return 1

    nombre = f"{TEMPORADA}-sem{reporte.semana:02d}-{tipo}.html"
    archivo = a.salida / "reportes" / nombre
    if archivo.exists() and not a.forzar:
        print(f"Ya existe {archivo}; no se repite.")
        return 0
    if not a.instantanea:
        instantaneas.guardar(a.salida, TEMPORADA, reporte.semana, ahora.astimezone(ZONA), crudos)
    html = generar_html(reporte)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(html, encoding="utf-8")
    (a.salida / "index.html").write_text(html, encoding="utf-8")
    print(f"Reporte escrito en {archivo}")
    if avisar:
        enlace = entorno.get("PAGES_URL", "").rstrip("/") + f"/reportes/{nombre}"
        titulo = f"Fantasy · semana {reporte.semana} · {tipo}"
        enviar_fn(tema, destino, titulo, correo.resumen(reporte), enlace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Correr y ver que pasan**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 4 passed

- [ ] **Step 5: Prueba de humo real (con red, sin correo)**

Run: `uv run fantasy reporte --tipo martes --salida salida_prueba --sin-correo --forzar`
Expected: `Reporte escrito en salida_prueba/reportes/2026-sem04-martes.html` (o sem03 si todavía no termina la semana 3). Abre el HTML y revisa que los nombres, las proyecciones y los reemplazos tengan sentido. Después borra la carpeta: `rm -rf salida_prueba`.

- [ ] **Step 6: Suite completa y commit**

Run: `uv run pytest -q && uv run ruff check .`
Expected: todo pasa.

```bash
git add src/fantasy/cli.py tests/test_cli.py
git commit -m "feat: comando fantasy reporte con idempotencia y aviso de fallas"
```

---

### Task 11: Despliegue — rama `datos`, Pages, secretos y workflow programado

**Files:**
- Create: `.github/workflows/reporte.yml`, `README.md`

**Interfaces:**
- Consumes: `fantasy reporte` (tarea 10).
- Produces: reporte automático en `https://mariocgaitan.github.io/fantasy-nfl/`.

- [ ] **Step 1: Workflow**

`.github/workflows/reporte.yml`:
```yaml
name: reporte
on:
  schedule:
    # Las dos horas UTC posibles de cada reporte (Sídney con y sin horario de verano).
    # El script solo trabaja si en Sídney es la hora correcta y el reporte no existe.
    - cron: "0 8 * * 2"    # martes 19:00 AEDT
    - cron: "0 9 * * 2"    # martes 19:00 AEST
    - cron: "0 21 * * 4"   # viernes 08:00 AEDT
    - cron: "0 22 * * 4"   # viernes 08:00 AEST
    - cron: "0 9 * * 0"    # domingo 20:00 AEDT
    - cron: "0 10 * * 0"   # domingo 20:00 AEST
  workflow_dispatch:
    inputs:
      tipo:
        description: "auto | martes | viernes | domingo"
        default: "auto"
      forzar:
        type: boolean
        default: false
permissions:
  contents: write
concurrency:
  group: reporte
  cancel-in-progress: false
jobs:
  reporte:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/checkout@v4
        with:
          ref: datos
          path: datos
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --frozen
      - name: Generar reporte
        env:
          NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}
          NTFY_EMAIL: ${{ secrets.NTFY_EMAIL }}
          PAGES_URL: https://mariocgaitan.github.io/fantasy-nfl
        run: |
          ARGS="--tipo ${{ inputs.tipo || 'auto' }} --salida datos"
          if [ "${{ inputs.forzar }}" = "true" ]; then ARGS="$ARGS --forzar"; fi
          uv run fantasy reporte $ARGS
      - name: Publicar en la rama datos
        working-directory: datos
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add -A
          if git diff --cached --quiet; then echo "Sin cambios"; exit 0; fi
          git commit -m "reporte $(date -u +%Y-%m-%dT%H:%MZ)"
          git push
```

- [ ] **Step 2: README**

`README.md`:
```markdown
# fantasy-nfl

Recomendador semanal para una liga de fantasy NFL en ESPN (8 equipos, PPR):
alineación, reemplazos condicionales y agencia libre, con intercambios y un modelo
propio validado contra ESPN en las fases siguientes.

- Qué y por qué: [`PROYECTO.md`](PROYECTO.md)
- Diseño: [`docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md`](docs/superpowers/specs/2026-09-26-sistema-fantasy-design.md)
- Reporte publicado: https://mariocgaitan.github.io/fantasy-nfl/

**Estado: provisional, sin validar.** Decide la proyección de ESPN; el modelo propio
solo mandará cuando le gane a ESPN en un backtest 2024–2025 sin fuga de datos.

## Uso

    uv sync
    uv run pytest
    uv run fantasy reporte --tipo martes --salida salida --sin-correo

Con `--instantanea <carpeta>` corre sin red a partir de datos guardados.
```

- [ ] **Step 3: Crear la rama `datos` y activar Pages**

```bash
git switch --orphan datos
git rm -rf --cached . >/dev/null 2>&1 || true
printf "Rama de datos: instantáneas y reportes publicados por GitHub Actions.\n" > README.md
touch .nojekyll
git add README.md .nojekyll
git commit -m "Rama de datos para instantáneas y la página"
git push -u origin datos
git switch main
gh api -X POST repos/Mariocgaitan/fantasy-nfl/pages -f "source[branch]=datos" -f "source[path]=/"
```
Expected: la respuesta de `gh api` trae `"html_url": "https://mariocgaitan.github.io/fantasy-nfl/"`.
Ojo: `git switch --orphan` deja en el directorio de trabajo los archivos sin rastrear de `main` (por ejemplo `.venv`); `git add` solo agrega `README.md` y `.nojekyll`, que es lo correcto.

- [ ] **Step 4: Secretos (sin imprimirlos)**

```bash
python -c "import secrets; print('fantasy-' + secrets.token_hex(12))" | gh secret set NTFY_TOPIC
gh secret set NTFY_EMAIL   # pega el correo de Mario cuando lo pida; confírmalo con él antes
```
Expected: `✓ Set Actions secret NTFY_TOPIC` y `✓ Set Actions secret NTFY_EMAIL`.

- [ ] **Step 5: Commit, push y corrida manual**

```bash
git add .github/workflows/reporte.yml README.md
git commit -m "feat: reporte programado en Actions, publicado en Pages y avisado por ntfy"
git push
gh workflow run reporte -f tipo=martes -f forzar=true
gh run watch --exit-status
```
Expected: la corrida termina en verde; en la rama `datos` aparecen `index.html`, `reportes/2026-semNN-martes.html` e `instantaneas/2026/semNN/...`; la página responde en `https://mariocgaitan.github.io/fantasy-nfl/` y llega el correo (revisar spam la primera vez).

- [ ] **Step 6: Verificar CI**

Run: `gh run list --workflow ci --limit 1`
Expected: `completed success`.

---

## Después de la fase 0 (fuera de este plan)

- Verificar la zona horaria de `waiverProcessHour = 11` con los primeros reclamos reales y anotarlo en `PROYECTO.md` (decisión 14).
- Plan de la fase 1: intercambios + modelo como segunda opinión (fecha: martes 2026-10-06).
