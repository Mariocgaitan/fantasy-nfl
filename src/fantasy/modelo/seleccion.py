"""Elección del modelo con el walk-forward de 2024 (regla fijada: menor MAE)."""

import pandas as pd

from fantasy.modelo import calibracion, candidatos
from fantasy.modelo.evaluar import relevantes, resumen


def walk_forward_v2(previas, actual, config, k=None, semanas=range(3, 18)):
    k = calibracion.factor(previas) if k is None else k
    salida = []
    for w in semanas:
        entreno = pd.concat([previas, actual[actual.semana < w]], ignore_index=True)
        m = candidatos.entrenar_v2(entreno, config, k)
        prueba = relevantes(actual[(actual.semana == w) & actual.real.notna()])
        if prueba.empty:
            continue
        salida.append(pd.DataFrame({
            "semana": w, "pos": prueba.pos.values, "jugador_id": prueba.jugador_id.values,
            "real": prueba.real.values, "espn": k * prueba.proy_espn.values,
            "modelo": candidatos.predecir_v2(m, prueba).values}))
    return pd.concat(salida, ignore_index=True)


def comparar(previas, actual):
    k = calibracion.factor(previas)
    res = []
    for config in candidatos.CONFIGS:
        r = resumen(walk_forward_v2(previas, actual, config, k=k), n=200)
        res.append({"config": config, "nombre": candidatos.nombre_config(config),
                    "mae_modelo": r["mae_modelo"], "mae_espn": r["mae_espn"],
                    "delta": r["delta"]})
    return sorted(res, key=lambda x: x["mae_modelo"])
