"""Filas para el modelo: para la semana w, solo información de semanas anteriores."""

import io

import pandas as pd

from fantasy.ingesta import espn, nflverse
from fantasy.modelo import contexto

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


VARIABLES_V2 = VARIABLES + ["target_share_prev", "air_share_prev", "pts_equipo",
                            "spread_equipo", "local", "permitido_prev"]
NEUTROS = {"pts_equipo": 22.0, "spread_equipo": 0.0, "local": 0.5}


def filas_v2(base, uso_ext, equipos, lineas, perm_prev):
    partes = []
    for w, b in base.groupby("semana"):
        u = uso_ext[uso_ext.semana < w].groupby("jugador_id").agg(
            target_share_prev=("target_share", "mean"),
            air_share_prev=("air_yards_share", "mean"), fuente_s=("semana", "max"))
        f = b.merge(u, on="jugador_id", how="left")
        eq = equipos[equipos.semana == w][["jugador_id", "equipo"]].drop_duplicates("jugador_id")
        f = f.merge(eq, on="jugador_id", how="left")
        li = lineas[lineas.semana == w][["equipo", "rival", "local", "pts_equipo",
                                         "spread_equipo"]]
        f = f.merge(li, on="equipo", how="left")
        pp = perm_prev[perm_prev.semana == w][["rival", "pos", "permitido_prev", "fuente"]]
        f = f.merge(pp.rename(columns={"fuente": "fuente_p"}), on=["rival", "pos"], how="left")
        partes.append(f)
    f = pd.concat(partes, ignore_index=True)
    f[["target_share_prev", "air_share_prev"]] = (
        f[["target_share_prev", "air_share_prev"]].fillna(0.0))
    for col, neutro in NEUTROS.items():
        f[col] = f[col].fillna(neutro)
    # Relleno con el promedio de la misma semana y posición (nunca de semanas futuras).
    medias = f.groupby(["semana", "pos"])["permitido_prev"].transform("mean")
    f["permitido_prev"] = f["permitido_prev"].fillna(medias).fillna(0.0)
    f["semana_fuente_max"] = (f[["semana_fuente_max", "fuente_s", "fuente_p"]]
                              .max(axis=1).fillna(0).astype(int))
    cols = ["jugador_id", "temporada", "semana", "pos", *VARIABLES_V2, "semana_fuente_max",
            "real"]
    out = f[cols].reset_index(drop=True)
    verificar_sin_fuga(out)
    return out


def equipo_previo(uso_ext: pd.DataFrame, semanas) -> pd.DataFrame:
    """Último equipo conocido antes de cada semana (nunca el de la semana que se predice)."""
    partes = []
    for w in semanas:
        u = uso_ext[uso_ext.semana < w].sort_values("semana").groupby("jugador_id").tail(1)
        partes.append(u[["jugador_id", "equipo"]].assign(semana=w))
    if not partes:
        return pd.DataFrame(columns=["jugador_id", "semana", "equipo"])
    return pd.concat(partes, ignore_index=True)[["jugador_id", "semana", "equipo"]]


def desde_crudos_v2(crudos, temporada, semanas=None, *, equipo_desde_espn=False):
    base = desde_crudos(crudos, temporada, semanas)
    leer = {n: pd.read_csv(io.StringIO(crudos[n]), low_memory=False)
            for n in ("semanal", "jugadores", "juegos")}
    uso_ext = nflverse.uso_extendido(leer["semanal"], leer["jugadores"])
    lineas = contexto.lineas(leer["juegos"][leer["juegos"].season == temporada])
    perm_prev = contexto.permitido_previo(contexto.permitido(leer["semanal"]),
                                          sorted(base.semana.unique()))
    if equipo_desde_espn:
        abrev = {t["id"]: contexto.a_nflverse(t["abbrev"])
                 for t in crudos["calendario"]["settings"]["proTeams"]}
        eq = pd.DataFrame([{"jugador_id": pe["id"],
                            "equipo": abrev.get(pe["player"].get("proTeamId"))}
                           for pe in crudos["proyecciones"]["players"]])
        equipos = pd.concat([eq.assign(semana=w) for w in base.semana.unique()],
                            ignore_index=True)
    else:
        equipos = equipo_previo(uso_ext, sorted(base.semana.unique()))
    return filas_v2(base, uso_ext, equipos, lineas, perm_prev)
