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
