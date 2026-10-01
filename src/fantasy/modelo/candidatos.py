"""Candidatos de la fase 3: ridge o gradient boosting sobre la corrección a ESPN calibrada."""

from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from fantasy.modelo.variables import VARIABLES_V2, verificar_sin_fuga

CONFIGS = ([{"tipo": "ridge", "alpha": a} for a in (1, 10, 100)]
           + [{"tipo": "hgb", "max_depth": d, "max_iter": n} for d in (2, 3) for n in (100, 300)])


def nombre_config(config: dict) -> str:
    if config["tipo"] == "ridge":
        return f"ridge(alpha={config['alpha']})"
    return f"hgb(depth={config['max_depth']},iter={config['max_iter']})"


def _estimador(config: dict):
    if config["tipo"] == "ridge":
        return make_pipeline(StandardScaler(), Ridge(alpha=config["alpha"]))
    return HistGradientBoostingRegressor(loss="absolute_error", learning_rate=0.05,
                                         max_depth=config["max_depth"],
                                         max_iter=config["max_iter"], random_state=0)


@dataclass
class ModeloV2:
    config: dict
    k: float
    variables: list[str] = field(default_factory=lambda: list(VARIABLES_V2))
    por_pos: dict[str, object] = field(default_factory=dict)
    version: int = 2


def entrenar_v2(f: pd.DataFrame, config: dict, k: float) -> ModeloV2:
    verificar_sin_fuga(f)
    datos = f[f["real"].notna() & (f["proy_espn"] > 0)]
    m = ModeloV2(config=config, k=k)
    for pos, g in datos.groupby("pos"):
        x = g[VARIABLES_V2].to_numpy(float)
        y = g["real"].to_numpy(float) - k * g["proy_espn"].to_numpy(float)
        m.por_pos[pos] = _estimador(config).fit(x, y)
    return m


def predecir_v2(m: ModeloV2, f: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=f.index, dtype=float)
    for pos, est in m.por_pos.items():
        mask = f["pos"] == pos
        if mask.any():
            g = f.loc[mask]
            pred[mask] = m.k * g["proy_espn"].to_numpy(float) + est.predict(
                g[VARIABLES_V2].to_numpy(float))
    # Sin proyección de ESPN (descansa o no juega) no hay nada que corregir: 0 puntos.
    pred[f["proy_espn"] <= 0] = 0.0
    return pred


def guardar_v2(m: ModeloV2, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(m, ruta)


def cargar_v2(ruta: Path) -> ModeloV2:
    m = joblib.load(ruta)
    if getattr(m, "version", None) != 2 or m.variables != VARIABLES_V2:
        raise ValueError(f"el modelo en {ruta} usa otras variables o versión")
    return m
