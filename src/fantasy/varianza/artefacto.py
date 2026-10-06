"""Todo lo que la simulación necesita, congelado en un archivo (con huella para el sellado)."""

from dataclasses import dataclass
from pathlib import Path

import joblib
import pandas as pd

from fantasy.varianza import errores
from fantasy.varianza.errores import Colecciones
from fantasy.varianza.grupos import GruposPos, ajustar, asignar

VERSION = 1


@dataclass
class Artefacto:
    version: int
    k: dict[str, int]
    grupos: dict[str, GruposPos]
    colecciones: Colecciones
    correlaciones: dict[tuple[str, str], float]
    temporadas: tuple[int, ...]


def construir(filas_grupos: pd.DataFrame, filas_colecciones: pd.DataFrame,
              k: dict[str, int], semilla: int = 0) -> Artefacto:
    """Grupos formados con `filas_grupos`; colecciones y correlaciones con
    `filas_colecciones` (ambas: filas relevantes de semanas 3–17)."""
    grupos = {pos: ajustar(filas_grupos, pos, n, semilla) for pos, n in k.items()}
    f = filas_colecciones.assign(grupo=asignar(grupos, filas_colecciones))
    col = errores.construir(f)
    corr = errores.correlaciones(f.assign(error=f.real - f.proy_espn))
    temporadas = tuple(sorted(int(t) for t in f.temporada.unique()))
    return Artefacto(VERSION, dict(k), grupos, col, corr, temporadas)


def guardar(art: Artefacto, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(art, ruta)


def cargar(ruta: Path) -> Artefacto:
    art = joblib.load(ruta)
    if getattr(art, "version", None) != VERSION:
        raise ValueError(f"el artefacto de varianza en {ruta} es de otra versión")
    return art
