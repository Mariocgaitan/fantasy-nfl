"""Ridge por posición sobre variables estandarizadas; se guarda como JSON legible."""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from fantasy.modelo.variables import VARIABLES, verificar_sin_fuga


@dataclass
class Modelo:
    por_pos: dict[str, dict]
    variables: list[str] = field(default_factory=lambda: list(VARIABLES))
    entrenado_con: list[int] = field(default_factory=list)
    version: int = 1


def entrenar(f: pd.DataFrame, alpha: float = 10.0) -> Modelo:
    verificar_sin_fuga(f)
    datos = f[f["real"].notna() & (f["proy_espn"] > 0)]
    por_pos = {}
    for pos, g in datos.groupby("pos"):
        x = g[VARIABLES].to_numpy(dtype=float)
        media, escala = x.mean(axis=0), x.std(axis=0)
        escala[escala == 0] = 1.0
        r = Ridge(alpha=alpha).fit((x - media) / escala, g["real"].to_numpy(dtype=float))
        por_pos[pos] = {"coef": r.coef_.tolist(), "intercepto": float(r.intercept_),
                        "media": media.tolist(), "escala": escala.tolist(), "n": len(g)}
    return Modelo(por_pos=por_pos, entrenado_con=sorted(int(t) for t in datos.temporada.unique()))


def predecir(m: Modelo, f: pd.DataFrame) -> pd.Series:
    pred = pd.Series(np.nan, index=f.index, dtype=float)
    for pos, p in m.por_pos.items():
        mask = f["pos"] == pos
        if not mask.any():
            continue
        x = (f.loc[mask, VARIABLES].to_numpy(dtype=float) - np.array(p["media"])) / np.array(
            p["escala"])
        pred[mask] = x @ np.array(p["coef"]) + p["intercepto"]
    return pred


def guardar(m: Modelo, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(asdict(m), indent=1), encoding="utf-8")


def cargar(ruta: Path) -> Modelo:
    m = Modelo(**json.loads(ruta.read_text(encoding="utf-8")))
    if m.variables != VARIABLES:
        raise ValueError(f"el modelo usa variables {m.variables}, se esperaban {VARIABLES}")
    return m
