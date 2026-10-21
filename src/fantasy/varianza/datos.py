"""Tabla jugador-semana de una temporada para la varianza: proyección de ESPN, puntos reales,
equipo NFL (último conocido antes de la semana) y rol previo."""

import io

import pandas as pd

from fantasy.ingesta import nflverse
from fantasy.modelo import variables
from fantasy.modelo.evaluar import relevantes
from fantasy.varianza import rol

SEMANAS = range(3, 18)


def tabla(crudos: dict, temporada: int, previo: pd.DataFrame | None = None) -> pd.DataFrame:
    base = variables.desde_crudos(crudos, temporada, semanas=list(range(1, 18)))
    base = base[base.proy_espn > 0][["jugador_id", "temporada", "semana", "pos",
                                     "proy_espn", "real"]]
    marca = relevantes(base)[["jugador_id", "semana"]].assign(relevante=True)
    base = base.merge(marca, on=["jugador_id", "semana"], how="left")
    base["relevante"] = base.relevante.fillna(False).astype(bool)
    leer = {n: pd.read_csv(io.StringIO(crudos[n]), low_memory=False)
            for n in ("semanal", "jugadores")}
    uso = nflverse.uso_extendido(leer["semanal"], leer["jugadores"])
    eq = variables.equipo_previo(uso, sorted(base.semana.unique()))
    base = base.merge(eq, on=["jugador_id", "semana"], how="left")
    r = rol.previo_a(rol.leer(crudos), base[["jugador_id", "semana", "pos"]], previo)
    return base.merge(r.drop(columns="pos"), on=["jugador_id", "semana"], how="left")


def para_construir(t: pd.DataFrame) -> pd.DataFrame:
    return t[t.relevante & t.semana.isin(SEMANAS)]
