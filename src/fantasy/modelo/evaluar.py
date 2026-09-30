"""Evaluación preliminar semana por semana contra ESPN (no es la validación oficial)."""

import numpy as np
import pandas as pd

from fantasy.modelo import ridge

TOPES = {"QB": 12, "RB": 30, "WR": 30, "TE": 12}


def relevantes(f: pd.DataFrame) -> pd.DataFrame:
    partes = [g.nlargest(TOPES.get(pos, 0), "proy_espn")
              for (_, pos), g in f.groupby(["semana", "pos"])]
    return pd.concat(partes) if partes else f.iloc[0:0]


def walk_forward(previas, actual, semanas=range(3, 18), alpha=10.0):
    salida = []
    for w in semanas:
        entreno = pd.concat([previas, actual[actual.semana < w]], ignore_index=True)
        m = ridge.entrenar(entreno, alpha=alpha)
        prueba = relevantes(actual[(actual.semana == w) & actual.real.notna()])
        if prueba.empty:
            continue
        salida.append(pd.DataFrame({
            "semana": w, "pos": prueba.pos.values, "jugador_id": prueba.jugador_id.values,
            "real": prueba.real.values, "espn": prueba.proy_espn.values,
            "modelo": ridge.predecir(m, prueba).values}))
    return pd.concat(salida, ignore_index=True)


def resumen(pred, semilla=0, n=2000):
    pred = pred.dropna(subset=["modelo"])
    e = pred.assign(em=(pred.modelo - pred.real).abs(), ee=(pred.espn - pred.real).abs())
    por_semana = e.groupby("semana")[["em", "ee"]].sum()
    conteo = e.groupby("semana").size()
    rng = np.random.default_rng(semilla)
    semanas = por_semana.index.to_numpy()
    deltas = []
    for _ in range(n):
        s = rng.choice(semanas, size=len(semanas), replace=True)
        deltas.append((por_semana.loc[s, "em"].sum() - por_semana.loc[s, "ee"].sum())
                      / conteo.loc[s].sum())
    return {
        "mae_modelo": float(e.em.mean()), "mae_espn": float(e.ee.mean()),
        "delta": float(e.em.mean() - e.ee.mean()),
        "ic95": (float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))),
        "por_pos": {p: (float(g.em.mean()), float(g.ee.mean())) for p, g in e.groupby("pos")},
    }
