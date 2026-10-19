import pandas as pd
import pytest

from fantasy.decision.alineacion import Alineacion
from fantasy.decision.empates import UMBRAL_CASI, UMBRAL_EMPATE, buscar, pts_por_equipo

COLS = ["jugador_id", "pos", "esperado", "bloqueado", "equipo_nfl_id"]


def _t(filas):
    return pd.DataFrame(filas, columns=COLS)


def _al(*slots):
    return Alineacion(slots=tuple(slots), esperado=0.0)


def test_umbrales():
    assert (UMBRAL_EMPATE, UMBRAL_CASI) == (1.0, 2.0)


def test_empate_y_casi_empate():
    t = _t([(1, "QB", 20.2, False, 29), (2, "QB", 18.6, False, 18),
            (3, "WR", 15.3, False, 30), (4, "WR", 14.4, False, 9)])
    al = _al(("QB", 1), ("WR", 3))
    e = {x.slot: x for x in buscar(al, t, {9: 26.0, 30: 21.5, 29: 24.0, 18: 22.5})}
    assert e["WR"].tipo == "empate" and e["WR"].diferencia == pytest.approx(0.9)
    assert (e["WR"].titular, e["WR"].alternativa) == (3, 4)
    assert e["QB"].tipo == "casi" and e["QB"].diferencia == pytest.approx(1.6)
    assert (e["WR"].pts_titular, e["WR"].pts_alternativa) == (21.5, 26.0)


def test_bordes_exactos():
    t = _t([(1, "WR", 15.3, False, 1), (2, "WR", 14.3, False, 2),
            (3, "TE", 12.0, False, 3), (4, "TE", 10.0, False, 4),
            (5, "QB", 20.0, False, 5), (6, "QB", 17.99, False, 6)])
    e = {x.slot: x.tipo for x in buscar(_al(("WR", 1), ("TE", 3), ("QB", 5)), t, {})}
    assert e == {"WR": "empate", "TE": "casi"}


def test_flex_compara_rb_wr_te():
    t = _t([(1, "RB", 12.0, False, 1), (2, "WR", 11.5, False, 2), (3, "QB", 11.9, False, 3)])
    e = buscar(_al(("FLEX", 1)), t, {})
    assert len(e) == 1 and e[0].alternativa == 2 and e[0].tipo == "empate"


def test_ignora_bloqueados_y_sin_puntos():
    t = _t([(1, "RB", 15.0, True, 1), (2, "RB", 14.8, False, 2),
            (3, "WR", 15.0, False, 3), (4, "WR", 14.9, True, 4), (5, "WR", 0.0, False, 5),
            (6, "WR", 13.5, False, 6)])
    e = buscar(_al(("RB", 1), ("WR", 3)), t, {})
    assert [(x.slot, x.alternativa, x.tipo) for x in e] == [("WR", 6, "casi")]


def test_diferencia_absoluta_tras_regla_de_duda():
    t = _t([(1, "WR", 13.0, False, 1), (2, "WR", 14.5, False, 2)])
    e = buscar(_al(("WR", 1)), t, {})
    assert e[0].tipo == "casi" and e[0].diferencia == pytest.approx(1.5)


def test_sin_linea_da_none():
    t = _t([(1, "WR", 15.0, False, 0), (2, "WR", 14.5, False, 2)])
    e = buscar(_al(("WR", 1)), t, {2: 23.0})
    assert (e[0].pts_titular, e[0].pts_alternativa) == (None, 23.0)


def test_misma_alternativa_en_dos_lugares():
    t = _t([(1, "WR", 15.0, False, 1), (2, "RB", 14.8, False, 2), (3, "WR", 14.5, False, 3)])
    e = buscar(_al(("WR", 1), ("FLEX", 2)), t, {})
    assert [(x.slot, x.alternativa) for x in e] == [("WR", 3), ("FLEX", 3)]


CAL = {"settings": {"proTeams": [{"id": 30, "abbrev": "JAX"}, {"id": 25, "abbrev": "SF"}]}}
JUEGOS = ("season,week,home_team,away_team,total_line,spread_line\n"
          "2026,4,JAX,SF,45.0,-3.0\n2026,5,JAX,SF,50.0,0.0\n2025,4,JAX,SF,40.0,0.0\n")


def test_pts_por_equipo_desde_juegos():
    assert pts_por_equipo(JUEGOS, CAL, 2026, 4) == {30: 21.0, 25: 24.0}


def test_pts_por_equipo_sin_juegos():
    assert pts_por_equipo(None, CAL, 2026, 4) == {}
