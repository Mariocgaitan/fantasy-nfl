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
