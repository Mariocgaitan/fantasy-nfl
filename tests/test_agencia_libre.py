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
