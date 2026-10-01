import numpy as np
import pandas as pd

from fantasy.modelo import seleccion
from fantasy.modelo.variables import VARIABLES_V2


def _temporada(t, semilla):
    r = np.random.default_rng(semilla)
    filas = []
    for w in range(1, 18):
        for j in range(60):
            fila = {v: float(r.uniform(0, 1)) for v in VARIABLES_V2}
            fila.update({"jugador_id": j, "temporada": t, "semana": w,
                         "pos": ["QB", "RB", "WR", "TE"][j % 4],
                         "proy_espn": 5.0 + j % 15, "pts_equipo": float(r.uniform(15, 30)),
                         "semana_fuente_max": w - 1})
            fila["real"] = 0.9 * fila["proy_espn"] + 0.5 * (fila["pts_equipo"] - 22.5) + r.normal(0, 1)
            filas.append(fila)
    return pd.DataFrame(filas)


def test_walk_forward_usa_espn_calibrada_y_semanas():
    pred = seleccion.walk_forward_v2(_temporada(2023, 0), _temporada(2024, 1),
                                     {"tipo": "ridge", "alpha": 10})
    assert set(pred.semana) == set(range(3, 18))
    assert {"espn", "modelo", "real"} <= set(pred.columns)
    assert (pred.espn < pred.real.max()).all()


def test_comparar_ordena_por_mae():
    res = seleccion.comparar(_temporada(2023, 0), _temporada(2024, 1))
    assert len(res) == 7
    assert [x["mae_modelo"] for x in res] == sorted(x["mae_modelo"] for x in res)
    assert res[0]["delta"] < 0  # el contexto existe en los datos sintéticos
