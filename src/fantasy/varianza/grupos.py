"""Tipos de jugador por rol (k-means por posición). El número de grupos lo eligen los datos:
el que mejor predice la variación (CRPS) en una temporada que no se usó para formarlos."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from fantasy.varianza import errores
from fantasy.varianza.rol import RASGOS

EMPATE = 0.01  # 1% de CRPS: se prefiere el k más chico


@dataclass
class GruposPos:
    rasgos: list[str]
    media: np.ndarray
    desv: np.ndarray
    centros: np.ndarray

    def asignar(self, X: pd.DataFrame) -> np.ndarray:
        z = (X[self.rasgos].to_numpy(float) - self.media) / self.desv
        d = ((z[:, None, :] - self.centros[None, :, :]) ** 2).sum(axis=2)
        return d.argmin(axis=1)


def ajustar(filas: pd.DataFrame, pos: str, k: int, semilla: int = 0) -> GruposPos:
    rasgos = RASGOS[pos]
    X = filas.loc[filas.pos == pos, rasgos].to_numpy(float)
    media, desv = X.mean(axis=0), X.std(axis=0)
    desv[desv == 0] = 1.0
    if k == 1:
        centros = np.zeros((1, len(rasgos)))
    else:
        km = KMeans(n_clusters=k, n_init=10, random_state=semilla).fit((X - media) / desv)
        centros = km.cluster_centers_
    return GruposPos(rasgos, media, desv, centros)


def asignar(grupos: dict[str, GruposPos], filas: pd.DataFrame) -> pd.Series:
    salida = pd.Series(0, index=filas.index, dtype=int)
    for pos, g in grupos.items():
        m = filas.pos == pos
        if m.any():
            salida[m] = g.asignar(filas[m])
    return salida


def _crps_medio(g: GruposPos, c: pd.DataFrame, e: pd.DataFrame, pos: str) -> float:
    col = errores.construir(c.assign(grupo=g.asignar(c)))
    d = pd.DataFrame({"g": g.asignar(e), "t": [col.tramo(pos, x) for x in e.proy_espn],
                      "z": (e.real - e.proy_espn).to_numpy(float)})
    total = sum(errores.crps(col.muestra(pos, gi, ti), s.z.to_numpy()).sum()
                for (gi, ti), s in d.groupby(["g", "t"]))
    return float(total / len(d))


def elegir_k(construccion: pd.DataFrame, eleccion: pd.DataFrame, ks=range(1, 6),
             semilla: int = 0) -> tuple[dict[str, int], pd.DataFrame]:
    elegido, filas = {}, []
    for pos in errores.POS:
        c = construccion[(construccion.pos == pos) & construccion.real.notna()]
        e = eleccion[(eleccion.pos == pos) & eleccion.real.notna()]
        if c.empty or e.empty:
            continue
        res = {k: _crps_medio(ajustar(c, pos, k, semilla), c, e, pos) for k in ks}
        filas += [{"pos": pos, "k": k, "crps": v} for k, v in res.items()]
        mejor = min(res.values())
        elegido[pos] = min(k for k, v in res.items() if v <= mejor * (1 + EMPATE))
    return elegido, pd.DataFrame(filas)
