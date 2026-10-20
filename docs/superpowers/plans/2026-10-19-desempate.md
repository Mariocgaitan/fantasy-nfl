# Marca de empates en el reporte — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El reporte marca como empate (≤ 1.0) o casi empate (1.0–2.0) cada decisión de
alineación pareja y muestra el total esperado del equipo de cada jugador, sin cambiar nada.

**Architecture:** Un módulo puro nuevo (`decision/empates.py`) recibe la alineación final, la
tabla de la semana y un mapa equipo NFL → puntos esperados, y devuelve los empates. `armado.armar`
lo llama después de `aplicar_regla_duda` y pasa el resultado al `Reporte`; la plantilla HTML lo
pinta bajo "Tu plantilla".

**Tech Stack:** Python 3.12, pandas, Jinja2, pytest; `uv run --no-env-file` (hay un
`UV_ENV_FILE=.env` global y no existe `.env`).

**Spec:** `docs/superpowers/specs/2026-10-19-desempate-design.md` (versión reducida, sección 4).

## Global Constraints

- No cambia la alineación, la proyección de nadie ni `Reporte.esperado`.
- No aparece en "Qué hacer" ni cambia urgencias (`acciones.construir` no se toca).
- No editar nada en `src/fantasy/modelo/` (huella del modelo v2 congelado). Se *usan*
  `contexto.lineas` y `contexto.a_nflverse` sin modificarlos.
- Umbrales: empate `|d| ≤ 1.0`, casi empate `1.0 < |d| ≤ 2.0`, con `esperado`.
- Sin dependencias nuevas. Suite completa en verde (`uv run --no-env-file pytest -q`).
- Rama `desempate`; PR al final; Mario fusiona.

## Review Focus

- Sin `juegos` en los crudos (instantáneas viejas, nflverse caído) → los empates salen igual,
  con "sin línea"; el reporte nunca truena por esto.
- Jugador cuyo equipo no tiene partido en `juegos` esa semana, o con `equipo_nfl_id == 0` →
  su total es `None` ("sin línea"), el del otro sí aparece.
- Titular bloqueado (su partido ya empezó) → no genera empate; alternativa bloqueada o con
  `esperado == 0` (descansa, fuera) → no cuenta como alternativa.
- Tras la regla de duda el titular puede tener *menos* `esperado` que la alternativa → se usa
  `|d|`.
- Bordes exactos: `d == 1.0` es empate y `d == 2.0` es casi empate; `d > 2.0` no aparece.

---

### Task 1: Módulo `empates`

**Files:**
- Create: `src/fantasy/decision/empates.py`
- Test: `tests/test_empates.py`

**Interfaces:**
- Consumes: `fantasy.decision.alineacion.Alineacion`, `FLEX_POS`; `fantasy.modelo.contexto.lineas`,
  `contexto.a_nflverse`.
- Produces:
  - `UMBRAL_EMPATE = 1.0`, `UMBRAL_CASI = 2.0`
  - `@dataclass(frozen=True) class Empate: slot: str; titular: int; alternativa: int;
    diferencia: float; tipo: str  # "empate" | "casi"; pts_titular: float | None;
    pts_alternativa: float | None`
  - `pts_por_equipo(juegos_csv: str | None, calendario: dict, temporada: int, semana: int)
    -> dict[int, float]` — `equipo_nfl_id` (proTeamId de ESPN) → `pts_equipo` de esa semana.
    `{}` si `juegos_csv` es `None`.
  - `buscar(al: Alineacion, t: pd.DataFrame, pts: dict[int, float]) -> list[Empate]` —
    `t` tiene al menos `jugador_id, pos, esperado, bloqueado, equipo_nfl_id`. Un `Empate` por
    lugar titular, en el orden de `al.slots`.

- [ ] **Step 1: Write the failing tests** en `tests/test_empates.py`, con una tabla sintética
  construida en el propio archivo (helper `_t(filas)` → DataFrame con las columnas de arriba;
  `Alineacion(slots=..., esperado=0.0)` armada a mano):

```python
def test_empate_y_casi_empate():
    # WR titular 15.3 vs banca 14.4 → empate (0.9); QB 20.2 vs 18.6 → casi (1.6)
    e = {x.slot: x for x in buscar(al, t, {9: 26.0, 30: 21.5, 29: 24.0, 18: 22.5})}
    assert e["WR"].tipo == "empate" and e["WR"].diferencia == pytest.approx(0.9)
    assert e["QB"].tipo == "casi"
    assert (e["WR"].pts_titular, e["WR"].pts_alternativa) == (21.5, 26.0)

def test_bordes_exactos():          # d=1.0 → "empate"; d=2.0 → "casi"; d=2.01 → no aparece
def test_flex_compara_rb_wr_te():   # FLEX titular RB vs WR de la banca a 0.5 → empate
def test_ignora_bloqueados_y_sin_puntos():
    # titular bloqueado → sin empate; mejor alternativa bloqueada o esperado 0 → se usa la siguiente
def test_diferencia_absoluta_tras_regla_de_duda():
    # titular 13.0 y alternativa 14.5 → |d| = 1.5 → tipo "casi", diferencia == 1.5
def test_sin_linea_da_none():       # pts sin la clave del equipo o equipo_nfl_id 0 → None
def test_misma_alternativa_en_dos_lugares():
    # Watson es la mejor alternativa del WR2 y del FLEX → aparece en los dos empates
def test_pts_por_equipo_desde_juegos():
    # CSV mínimo: season,week,home_team,away_team,total_line,spread_line
    # 2026,4,JAX,SF,45.0,-3.0 ; calendario {"settings":{"proTeams":[{"id":30,"abbrev":"JAX"},
    # {"id":25,"abbrev":"SF"}]}} → {30: 21.0, 25: 24.0}; otra semana o temporada no entra
def test_pts_por_equipo_sin_juegos():  # pts_por_equipo(None, cal, 2026, 4) == {}
```

  `spread_line` en nflverse es a favor del local: `contexto.lineas` da local
  `(total + spread)/2` = (45 − 3)/2 = 21.0 y visita 24.0. Usa `contexto.lineas`; no la
  reimplementes.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-env-file pytest tests/test_empates.py -q`
Expected: FAIL (`ModuleNotFoundError: fantasy.decision.empates`)

- [ ] **Step 3: Implement `empates.py`**

  `buscar`: por cada `(slot, j)` de `al.slots` con titular no bloqueado, la alternativa es la
  fila de `t` fuera de `al.ids()`, con `pos` en `FLEX_POS` si `slot == "FLEX"` o `== slot`, no
  bloqueada y `esperado > 0`, de mayor `esperado` (orden estable). `d = |esperado_j −
  esperado_alt|`, redondeado a 2 decimales antes de comparar con los umbrales (evita que
  15.3 − 14.3 = 1.0000000002 caiga en "casi"). `pts_*` = `pts.get(equipo_nfl_id)`.
  `pts_por_equipo`: lee el CSV, filtra `season == temporada`, aplica `contexto.lineas`, filtra
  `semana`, y cruza con `calendario["settings"]["proTeams"]` vía `a_nflverse(abrev)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run --no-env-file pytest tests/test_empates.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fantasy/decision/empates.py tests/test_empates.py
git commit -m "feat(decision): empates y casi empates de la alineación con el total del equipo"
```

---

### Task 2: Empates en el reporte (armado + HTML + docs)

**Files:**
- Modify: `src/fantasy/reporte/armado.py` (campo nuevo en `Reporte`; cálculo tras
  `al = aplicar_regla_duda(...)`)
- Modify: `src/fantasy/reporte/plantillas/reporte.html.j2` (bajo la tabla de "Tu plantilla",
  antes de "Si alguien queda fuera")
- Modify: `docs/ESTADO.md`, `README.md`
- Test: `tests/test_reporte_empates.py`

**Interfaces:**
- Consumes: `empates.buscar`, `empates.pts_por_equipo`, `Empate` (Task 1).
- Produces: `Reporte.empates: list[dict] = field(default_factory=list)`; cada dict:
  `{"tipo": "empate"|"casi", "slot": str, "titular": str, "proy_titular": float,
  "alternativa": str, "proy_alternativa": float, "diferencia": float,
  "pts_titular": float|None, "pts_alternativa": float|None}` (`proy_*` = `esperado`
  redondeado a 1 decimal; `pts_*` a 1 decimal o `None`).

- [ ] **Step 1: Write the failing tests** en `tests/test_reporte_empates.py`, con el fixture
  real `tests/fixtures/sem04_2026-10-02` y `AHORA = pd.Timestamp("2026-10-01 23:23", tz="UTC")`
  (mismo patrón que `tests/test_reporte_claro.py`):

```python
def test_viernes_semana4_washington_watson_es_empate():
    r = armar(cargar(VIE), AHORA, "viernes", 5)
    e = [x for x in r.empates if x["titular"] == "Parker Washington"]
    assert e and e[0]["tipo"] == "empate" and e[0]["alternativa"] == "Christian Watson"
    assert e[0]["pts_titular"] is not None and e[0]["pts_alternativa"] is not None

def test_viernes_semana4_young_shough_es_casi():
    # Bryce Young titular vs Tyler Shough, diferencia ~1.6 → "casi"

def test_empates_no_cambian_alineacion_ni_acciones():
    # misma r.alineacion, r.esperado y r.acciones que armar con empates.buscar parcheado a []
    # (monkeypatch de fantasy.reporte.armado.empates_mod.buscar)

def test_sin_juegos_sale_sin_linea():
    crudos = cargar(VIE); crudos.pop("juegos")
    r = armar(crudos, AHORA, "viernes", 5)
    assert r.empates and all(x["pts_titular"] is None for x in r.empates)

def test_pagina_muestra_empates_y_nota():
    html = generar_html(armar(cargar(VIE), AHORA, "viernes", 5))
    assert "Empate" in html and "Casi empate" in html and "sin línea" not in html
    assert "moneda" in html   # la nota fija
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run --no-env-file pytest tests/test_reporte_empates.py -q`
Expected: FAIL (`AttributeError: 'Reporte' object has no attribute 'empates'`)

- [ ] **Step 3: Implement in `armado.py`**

  Importa `from fantasy.decision import empates as empates_mod`. Tras calcular `al`:
  `pts = empates_mod.pts_por_equipo(crudos.get("juegos"), crudos["calendario"], TEMPORADA,
  semana)`, `lista_empates = empates_mod.buscar(al, tm, pts)` y conviértelos al dict de
  Interfaces con `idx` para los nombres. Si `pts_por_equipo` lanza, `pts = {}` y se agrega el
  aviso `"Sin líneas de apuestas: los empates salen sin el total del equipo."` (el reporte
  nunca se cae por esto). Pásalo a `Reporte(empates=...)`.

- [ ] **Step 4: Implement in `reporte.html.j2`**

  Si hay empates, un `<h3>Decisiones parejas</h3>` y una lista; cada línea, con el texto
  exacto:
  - `Empate en {slot}: {titular} {proy_titular} (su equipo espera {pts_titular}) · {alternativa} {proy_alternativa} (su equipo espera {pts_alternativa})`
  - igual con `Casi empate en {slot}: …`
  - si un `pts_*` es `None`, ese paréntesis dice `(sin línea)`.

  Debajo, la nota fija en `<p class="suave">`:
  `Empate: menos de 1 punto de diferencia; la proyección acierta ~51 %, como una moneda. Casi empate: de 1 a 2 puntos. "Su equipo espera": puntos que las apuestas esperan del equipo del jugador; es un dato, no una recomendación. Decides tú.`

- [ ] **Step 5: Run tests to verify they pass, then the full suite**

Run: `uv run --no-env-file pytest tests/test_reporte_empates.py -q` → PASS
Run: `uv run --no-env-file pytest -q` → todas en verde (~150 + las nuevas)

- [ ] **Step 6: Docs**

  - `docs/ESTADO.md`: en "Dónde estamos", una fila "Empates en el reporte — En producción al
    fusionar"; un apartado corto con la exploración (sección 1 del spec: 53.9 % / en conflicto
    52.9 % en 2023–2024, 48.1 % en 2026 sem 1–6) y que la prueba de 2025 del desempate queda
    **registrada sin correr** (spec sección 3).
  - `README.md`: una línea en la descripción del reporte: "Marca las decisiones parejas
    (empate y casi empate) con los puntos que las apuestas esperan de cada equipo."

- [ ] **Step 7: Commit**

```bash
git add src/fantasy/reporte/armado.py src/fantasy/reporte/plantillas/reporte.html.j2 tests/test_reporte_empates.py docs/ESTADO.md README.md
git commit -m "feat(reporte): decisiones parejas con el total esperado del equipo"
```

---

### Al terminar

Revisión final de la rama, comprobar a mano con
`uv run --no-env-file fantasy reporte --tipo martes --salida <tmp> --sin-correo --forzar`
que la sección "Decisiones parejas" aparece y que "Qué hacer" no cambió, y abrir el PR a `main`.
