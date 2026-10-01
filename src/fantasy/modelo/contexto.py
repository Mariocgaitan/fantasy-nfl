"""Contexto del partido: líneas de apuestas y lo que permite cada defensa."""

import pandas as pd

ESPN_A_NFLVERSE = {"LAR": "LA", "WSH": "WAS"}
POSICIONES = ("QB", "RB", "WR", "TE")


def a_nflverse(abrev: str) -> str:
    return ESPN_A_NFLVERSE.get(abrev, abrev)


def lineas(juegos: pd.DataFrame) -> pd.DataFrame:
    total, spread = juegos["total_line"], juegos["spread_line"]
    local = pd.DataFrame({"equipo": juegos["home_team"], "semana": juegos["week"],
                          "rival": juegos["away_team"], "local": 1,
                          "pts_equipo": (total + spread) / 2, "spread_equipo": spread})
    visita = pd.DataFrame({"equipo": juegos["away_team"], "semana": juegos["week"],
                           "rival": juegos["home_team"], "local": 0,
                           "pts_equipo": (total - spread) / 2, "spread_equipo": -spread})
    return pd.concat([local, visita], ignore_index=True)


def permitido(semanal: pd.DataFrame) -> pd.DataFrame:
    if "opponent_team" not in semanal.columns:  # instantáneas viejas: sin dato del rival
        return pd.DataFrame(columns=["rival", "semana", "pos", "pts"])
    s = semanal[(semanal["season_type"] == "REG") & semanal["position"].isin(POSICIONES)]
    g = s.groupby(["opponent_team", "week", "position"], as_index=False)["fantasy_points_ppr"].sum()
    return g.rename(columns={"opponent_team": "rival", "week": "semana", "position": "pos",
                             "fantasy_points_ppr": "pts"})


def permitido_previo(perm: pd.DataFrame, semanas) -> pd.DataFrame:
    partes = []
    for w in semanas:
        g = perm[perm.semana < w].groupby(["rival", "pos"]).agg(
            permitido_prev=("pts", "mean"), fuente=("semana", "max")).reset_index()
        g["semana"] = w
        partes.append(g)
    if not partes:
        return pd.DataFrame(columns=["rival", "semana", "pos", "permitido_prev", "fuente"])
    return pd.concat(partes, ignore_index=True)[
        ["rival", "semana", "pos", "permitido_prev", "fuente"]]
