import numpy as np
import pandas as pd

from fantasy.cli import main
from fantasy.modelo import evaluar


def _temporada(temporada, semilla):
    r = np.random.default_rng(semilla)
    filas = []
    for w in range(1, 18):
        for j in range(80):
            proy = 5 + (j % 20)
            filas.append({"jugador_id": j, "temporada": temporada, "semana": w,
                          "pos": ["QB", "RB", "WR", "TE"][j % 4], "proy_espn": proy,
                          "pts_prev": proy, "snaps_prev": 0.7, "targets_prev": j % 7,
                          "acarreos_prev": 0.0, "n_prev": w - 1, "semana_fuente_max": w - 1,
                          "real": proy + 0.8 * (j % 7) - 2 + r.normal(0, 1)})
    return pd.DataFrame(filas)


def test_modelo_que_corrige_a_espn_gana():
    pred = evaluar.walk_forward(_temporada(2023, 0), _temporada(2024, 1))
    res = evaluar.resumen(pred)
    assert set(pred.semana) == set(range(3, 18))
    assert res["delta"] < 0 and res["ic95"][1] < 0
    assert set(res["por_pos"]) == {"QB", "RB", "WR", "TE"}


def test_relevantes_respeta_topes():
    f = _temporada(2024, 0).rename(columns={})
    r = evaluar.relevantes(f[f.semana == 5])
    assert r.groupby("pos").size().to_dict() == {"QB": 12, "RB": 20, "TE": 12, "WR": 20}


def test_evaluar_2025_rechazado():
    assert main(["evaluar", "--temporada", "2025"]) == 2
