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
