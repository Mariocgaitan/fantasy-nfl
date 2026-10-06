"""Errores reales de ESPN (puntos reales − proyección) por tipo de jugador, su CRPS y la
correlación entre compañeros del mismo equipo NFL."""

import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

MINIMO_CELDA = 200
MINIMO_PAR = 300
POS = ("QB", "RB", "WR", "TE")


@dataclass
class Colecciones:
    cortes: dict[str, tuple[float, float]]
    muestras: dict[tuple, np.ndarray]
    piso: dict[str, float]

    def tramo(self, pos: str, proy: float) -> int:
        bajo, alto = self.cortes[pos]
        return int(proy > bajo) + int(proy > alto)

    def muestra(self, pos: str, grupo: int, tramo: int) -> np.ndarray:
        for clave in ((pos, int(grupo), int(tramo)), (pos, int(grupo))):
            m = self.muestras.get(clave)
            if m is not None and len(m) >= MINIMO_CELDA:
                return m
        return self.muestras[(pos,)]


def _clave(k) -> tuple:
    k = k if isinstance(k, tuple) else (k,)
    return tuple(x if isinstance(x, str) else int(x) for x in k)


def construir(filas: pd.DataFrame) -> Colecciones:
    f = filas.dropna(subset=["real"]).copy()
    f["error"] = f["real"] - f["proy_espn"]
    cortes = {p: tuple(float(x) for x in np.quantile(g.proy_espn, [1 / 3, 2 / 3]))
              for p, g in f.groupby("pos")}
    col = Colecciones(cortes, {}, {p: float(g.real.min()) for p, g in f.groupby("pos")})
    f["tramo"] = [col.tramo(p, x) for p, x in zip(f.pos, f.proy_espn, strict=True)]
    for claves in (["pos"], ["pos", "grupo"], ["pos", "grupo", "tramo"]):
        for k, g in f.groupby(claves):
            col.muestras[_clave(k)] = np.sort(g.error.to_numpy(float))
    return col


def crps(muestra: np.ndarray, z: np.ndarray) -> np.ndarray:
    """CRPS de la distribución empírica `muestra` (ordenada) en cada valor de `z`:
    E|X − z| − ½·E|X − X'|."""
    x, n = muestra, len(muestra)
    z = np.asarray(z, float)
    c = np.concatenate([[0.0], np.cumsum(x)])
    k = np.searchsorted(x, z, side="right")
    e1 = (k * z - c[k] + (c[n] - c[k]) - (n - k) * z) / n
    i = np.arange(1, n + 1)
    e2 = 2.0 * np.sum((2 * i - n - 1) * x) / n**2
    return e1 - 0.5 * e2


def correlaciones(filas: pd.DataFrame, minimo: int = MINIMO_PAR) -> dict[tuple[str, str], float]:
    """Spearman de los errores de compañeros (mismo equipo, misma semana) por par de
    posiciones, pasada a la correlación de una cópula gaussiana: 2·sen(π·ρs/6)."""
    f = filas.dropna(subset=["equipo", "error"])
    f = f.assign(clave=f.temporada.astype(str) + "-" + f.semana.astype(str) + "-"
                 + f.equipo.astype(str))
    p = f.merge(f, on="clave", suffixes=("_a", "_b"))
    p = p[p.jugador_id_a < p.jugador_id_b]
    salida = {}
    for par in itertools.combinations_with_replacement(POS, 2):
        directo = (p.pos_a == par[0]) & (p.pos_b == par[1])
        cruzado = (p.pos_a == par[1]) & (p.pos_b == par[0]) & (par[0] != par[1])
        x = pd.concat([p.loc[directo, "error_a"], p.loc[cruzado, "error_b"]])
        y = pd.concat([p.loc[directo, "error_b"], p.loc[cruzado, "error_a"]])
        if len(x) < minimo:
            salida[par] = 0.0
            continue
        rs = float(np.corrcoef(x.rank(), y.rank())[0, 1])
        salida[par] = float(2 * np.sin(np.pi * rs / 6))
    return salida


def rho(corr: dict[tuple[str, str], float], pos_a: str, pos_b: str) -> float:
    return corr.get(tuple(sorted((pos_a, pos_b), key=POS.index)), 0.0)
