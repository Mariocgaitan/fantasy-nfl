import io

import pandas as pd
import pytest

from fantasy.ingesta import nflverse

JUEGOS = (
    "game_id,season,game_type,week,gameday,gametime,away_team,home_team,spread_line,total_line\n"
    "a,2024,REG,1,2024-09-08,13:00,BUF,KC,3.0,47.0\n"
    "b,2024,POST,19,2025-01-12,13:00,BUF,KC,1.0,45.0\n"
    "c,2025,REG,1,2025-09-07,13:00,BUF,KC,2.0,48.0\n"
    "d,2026,REG,5,2026-10-11,13:00,LA,WAS,-2.5,44.5\n"
)


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _abrir(url, timeout):
    assert url == nflverse.URL_JUEGOS
    return Resp(JUEGOS.encode())


def test_bajar_juegos_filtra_temporada_y_tipo():
    # Review Focus 3: 2025 y la postemporada nunca pasan.
    df = pd.read_csv(io.StringIO(nflverse.bajar_juegos((2024, 2026), abrir=_abrir)))
    assert sorted(df.season.unique()) == [2024, 2026]
    assert (df.week <= 18).all()
    assert list(df.columns) == ["season", "week", "gameday", "gametime", "home_team",
                                "away_team", "spread_line", "total_line"]


def test_bajar_juegos_2025_sellada():
    with pytest.raises(ValueError, match="sellada"):
        nflverse.bajar_juegos((2025,), abrir=_abrir)
    df = pd.read_csv(io.StringIO(
        nflverse.bajar_juegos((2025,), abrir=_abrir, permitir_sellada=True)))
    assert list(df.season.unique()) == [2025]


def test_uso_extendido():
    semanal = pd.DataFrame({
        "player_id": ["g1", "g1", "g2"], "season_type": ["REG", "REG", "POST"],
        "week": [1, 2, 19], "team": ["KC", "LV", "KC"], "opponent_team": ["BUF", "DEN", "BUF"],
        "target_share": [0.25, None, 0.1], "air_yards_share": [0.3, 0.2, 0.1],
    })
    jug = pd.DataFrame({"gsis_id": ["g1", "g2"], "pfr_id": ["p1", "p2"], "espn_id": [11.0, 12.0]})
    u = nflverse.uso_extendido(semanal, jug).set_index("semana")
    assert list(u.jugador_id.unique()) == [11]
    assert u.loc[2, "equipo"] == "LV" and u.loc[2, "rival"] == "DEN"
    assert u.loc[2, "target_share"] == 0.0


def test_semanal_sin_columnas_nuevas_falla_en_la_descarga():
    viejo = "player_id,position,season_type,week,targets,carries\n" "g1,WR,REG,1,3,0\n"

    def abrir(url, timeout):
        return Resp(viejo.encode() if "stats_player" in url else
                    b"week,pfr_player_id,offense_pct,gsis_id,pfr_id,espn_id,position\n")

    with pytest.raises(nflverse.DatosInvalidos, match="target_share"):
        nflverse.bajar_nflverse(2026, abrir=abrir, dormir=lambda s: None)
