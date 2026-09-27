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
