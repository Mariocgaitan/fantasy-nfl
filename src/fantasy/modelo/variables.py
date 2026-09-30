"""Filas para el modelo: para la semana w, solo información de semanas anteriores."""

import pandas as pd

from fantasy.ingesta import espn, nflverse

VARIABLES = ["proy_espn", "pts_prev", "snaps_prev", "targets_prev", "acarreos_prev", "n_prev"]


class FugaDeDatos(Exception):
    """Una variable usa información de la semana que se predice o posterior."""


def filas(proy, reales, uso, pos, temporada, semanas=None):
    semanas = sorted(semanas or proy.semana.unique())
    salida = []
    for w in semanas:
        base = proy.loc[proy.semana == w, ["jugador_id", "puntos"]].rename(
            columns={"puntos": "proy_espn"})
        antes = reales[reales.semana < w]
        g = antes.groupby("jugador_id").agg(pts_prev=("puntos", "mean"),
                                           n_prev=("puntos", "size"),
                                           fuente_r=("semana", "max"))
        u = uso[uso.semana < w].groupby("jugador_id").agg(
            snaps_prev=("snaps_pct", "mean"), targets_prev=("targets", "mean"),
            acarreos_prev=("acarreos", "mean"), fuente_u=("semana", "max"))
        f = base.merge(g, on="jugador_id", how="left").merge(u, on="jugador_id", how="left")
        f["n_prev"] = f["n_prev"].fillna(0).astype(int)
        f["pts_prev"] = f["pts_prev"].fillna(f["proy_espn"])
        f[["snaps_prev", "targets_prev", "acarreos_prev"]] = (
            f[["snaps_prev", "targets_prev", "acarreos_prev"]].fillna(0.0))
        f["semana_fuente_max"] = f[["fuente_r", "fuente_u"]].max(axis=1).fillna(0).astype(int)
        real = reales.loc[reales.semana == w, ["jugador_id", "puntos"]].rename(
            columns={"puntos": "real"})
        f = f.merge(real, on="jugador_id", how="left")
        f["temporada"], f["semana"] = temporada, w
        f["pos"] = f["jugador_id"].map(pos)
        salida.append(f)
    out = pd.concat(salida, ignore_index=True) if salida else pd.DataFrame()
    out = out[out["pos"].notna()]
    cols = ["jugador_id", "temporada", "semana", "pos", *VARIABLES, "semana_fuente_max", "real"]
    out = out[cols].reset_index(drop=True)
    verificar_sin_fuga(out)
    return out


def verificar_sin_fuga(f: pd.DataFrame) -> None:
    malas = f[f["semana_fuente_max"] >= f["semana"]]
    if len(malas):
        raise FugaDeDatos(f"{len(malas)} filas usan datos de su propia semana o posteriores")


def desde_crudos(crudos: dict, temporada: int, semanas=None) -> pd.DataFrame:
    proy = espn.parsear_proyecciones(crudos["proyecciones"], temporada)
    reales = espn.parsear_reales(crudos["proyecciones"], temporada)
    pos = pd.Series({pe["id"]: espn.POSICIONES.get(pe["player"].get("defaultPositionId"))
                     for pe in crudos["proyecciones"]["players"]}).dropna()
    if all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        uso = nflverse.tablas(crudos)
    else:
        uso = pd.DataFrame(columns=["jugador_id", "semana", "snaps_pct", "targets", "acarreos"])
    return filas(proy, reales, uso, pos, temporada, semanas)
