"""Monte Carlo de una semana: a cada jugador se le suma un error real de ESPN de su tipo
(grupo y tramo); los compañeros comparten suerte mediante una cópula gaussiana."""

import numpy as np
import pandas as pd
from scipy.special import ndtr

from fantasy.varianza import errores
from fantasy.varianza.artefacto import Artefacto

N_SIM = 10_000


def _matriz(pos: list[str], equipos: list, corr: dict) -> np.ndarray:
    m = len(pos)
    R = np.eye(m)
    for i in range(m):
        for j in range(i + 1, m):
            if equipos[i] is not None and equipos[i] == equipos[j]:
                R[i, j] = R[j, i] = errores.rho(corr, pos[i], pos[j])
    w, v = np.linalg.eigh(R)
    if w.min() < 1e-6:  # la más cercana definida positiva
        R = (v * np.clip(w, 1e-6, None)) @ v.T
        d = np.sqrt(np.diag(R))
        R = R / np.outer(d, d)
    return R


def simular(jug: pd.DataFrame, art: Artefacto, n: int = N_SIM, semilla: int = 0) -> np.ndarray:
    rng = np.random.default_rng(semilla)
    m = len(jug)
    equipos = [None if pd.isna(e) else e for e in jug.equipo]
    L = np.linalg.cholesky(_matriz(list(jug.pos), equipos, art.correlaciones))
    u = ndtr(rng.standard_normal((n, m)) @ L.T)
    juega = rng.random((n, m)) < jug.p_jugar.to_numpy(float)
    col = art.colecciones
    salida = np.zeros((n, m))
    for i, f in enumerate(jug.itertuples(index=False)):
        if not pd.isna(f.real_fijo):
            salida[:, i] = f.real_fijo
            continue
        if f.proy <= 0:
            continue  # descansa o no lo proyectan: 0, no "0 + error"
        mu = col.muestra(f.pos, int(f.grupo), col.tramo(f.pos, f.proy))
        idx = np.minimum((u[:, i] * len(mu)).astype(int), len(mu) - 1)
        pts = np.maximum(f.proy + mu[idx], col.piso[f.pos])
        salida[:, i] = np.where(juega[:, i], pts, 0.0)
    return salida


def p_ganar(puntos: np.ndarray, cols_a: list[int], cols_b: list[int]) -> float:
    a = puntos[:, cols_a].sum(axis=1)
    b = puntos[:, cols_b].sum(axis=1)
    return float(((a > b) + 0.5 * (a == b)).mean())


def dispersion(puntos: np.ndarray, col: int) -> float:
    q10, q90 = np.quantile(puntos[:, col], [0.1, 0.9])
    return float(q90 - q10)
