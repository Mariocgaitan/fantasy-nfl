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
