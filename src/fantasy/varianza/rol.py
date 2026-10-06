"""Rol de cada jugador (cómo lo usa su equipo), solo con partidos anteriores a la semana.

El rol se estabiliza rápido; la varianza de un jugador en 3–4 partidos es ruido. Por eso lo
que dice 2026 de cada jugador entra por aquí y no por sus puntos."""

import io

import numpy as np
import pandas as pd

from fantasy.modelo.variables import FugaDeDatos

RASGOS = {
    "QB": ["rush_share", "snap_pct"],
    "RB": ["target_share", "rush_share", "snap_pct", "eficiencia"],
    "WR": ["target_share", "rel_depth", "snap_pct", "eficiencia"],
    "TE": ["target_share", "rel_depth", "snap_pct", "eficiencia"],
}
TODOS = ["target_share", "rel_depth", "rush_share", "eficiencia", "snap_pct"]
PESO_PREVIO = 3  # el año anterior pesa como 3 partidos
SEMANA_MAX = 18  # temporada regular


def _division(a, b) -> np.ndarray:
    a, b = np.asarray(a, float), np.asarray(b, float)
    return np.divide(a, b, out=np.zeros_like(a), where=b > 0)


def por_partido(semanal: pd.DataFrame, snaps: pd.DataFrame,
                jugadores: pd.DataFrame) -> pd.DataFrame:
    ids = jugadores.dropna(subset=["espn_id"])
    s = semanal[semanal["season_type"] == "REG"].copy()
    s["acarreos_eq"] = s.groupby(["team", "week"])["carries"].transform("sum")
    s = s.merge(ids[["gsis_id", "espn_id"]], left_on="player_id", right_on="gsis_id")
    ts = s["target_share"].fillna(0.0).to_numpy(float)
    oport = (s["targets"] + s["carries"]).to_numpy(float)
    out = pd.DataFrame({
        "jugador_id": s["espn_id"].astype("int64").to_numpy(),
        "semana": s["week"].astype("int64").to_numpy(),
        "target_share": ts,
        "rel_depth": _division(s["air_yards_share"].fillna(0.0), ts),
        "rush_share": _division(s["carries"], s["acarreos_eq"]),
        "eficiencia": _division(s["fantasy_points_ppr"] - s["receptions"], oport),
    })
    out = out.groupby(["jugador_id", "semana"], as_index=False).mean()
    n = snaps.merge(ids[["pfr_id", "espn_id"]], left_on="pfr_player_id", right_on="pfr_id")
    n = (n.groupby(["espn_id", "week"], as_index=False)["offense_pct"].max()
         .rename(columns={"espn_id": "jugador_id", "week": "semana", "offense_pct": "snap_pct"}))
    n[["jugador_id", "semana"]] = n[["jugador_id", "semana"]].astype("int64")
    n = n[n.semana <= SEMANA_MAX]
    # Sin fila de snaps no es 0% de snaps: queda vacío y lo cubre la mezcla.
    return out.merge(n, on=["jugador_id", "semana"], how="left")


def _vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype=float) for c in ["jugador_id", "semana", *TODOS]})


def leer(crudos: dict) -> pd.DataFrame:
    if not all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        return _vacio()
    t = {k: pd.read_csv(io.StringIO(crudos[k]), low_memory=False)
         for k in ("semanal", "snaps", "jugadores")}
    return por_partido(t["semanal"], t["snaps"], t["jugadores"])


def promedio_temporada(pp: pd.DataFrame) -> pd.DataFrame:
    return pp.groupby("jugador_id", as_index=False)[TODOS].mean()


def previo_a(pp: pd.DataFrame, base: pd.DataFrame,
             previo: pd.DataFrame | None = None) -> pd.DataFrame:
    """Para cada fila de `base` (jugador_id, semana, pos): promedio de sus partidos de semanas
    anteriores mezclado con el año previo, `x = (n·x_temporada + 3·x_previo) / (n + 3)`.
    Sin año previo: mediana de la posición en el previo; si tampoco hay, la de la temporada."""
    ref = previo.set_index("jugador_id") if previo is not None and len(previo) else None
    partes = []
    for w, b in base.groupby("semana"):
        antes = pp[pp.semana < w]
        g = antes.groupby("jugador_id")
        media, cuenta = g[TODOS].mean(), g[TODOS].count()
        f = b[["jugador_id", "semana", "pos"]].reset_index(drop=True)
        f["fuente_max"] = f.jugador_id.map(g["semana"].max()).fillna(0).astype(int)
        for c in TODOS:
            xt = f.jugador_id.map(media[c]) if c in media else pd.Series(np.nan, index=f.index)
            n = f.jugador_id.map(cuenta[c]).fillna(0) if c in cuenta else 0.0
            xp = f.jugador_id.map(ref[c]) if ref is not None else pd.Series(np.nan, index=f.index)
            xp = xp.fillna(xp.groupby(f.pos).transform("median"))
            xp = xp.fillna(xt.groupby(f.pos).transform("median")).fillna(0.0)
            f[c] = (n * xt.fillna(0.0) + PESO_PREVIO * xp) / (n + PESO_PREVIO)
        partes.append(f)
    if not partes:
        return pd.DataFrame(columns=["jugador_id", "semana", "pos", *TODOS, "fuente_max"])
    out = pd.concat(partes, ignore_index=True)
    if (out.fuente_max >= out.semana).any():
        raise FugaDeDatos("el rol usa datos de su propia semana o posteriores")
    return out
