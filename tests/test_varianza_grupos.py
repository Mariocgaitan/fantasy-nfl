import numpy as np
import pandas as pd

from fantasy.varianza import grupos
from fantasy.varianza.rol import RASGOS


def _wr(n, rng, estructura):
    X = rng.normal(0, 1, (n, 4))
    if estructura:  # dos tipos: los de rasgo 0 alto son explosivos
        explosivo = rng.random(n) < 0.5
        X[:, 0] = np.where(explosivo, 3.0, -3.0) + rng.normal(0, 0.3, n)
        sd = np.where(explosivo, 14.0, 3.0)
    else:
        sd = np.full(n, 8.0)
    f = pd.DataFrame(X, columns=RASGOS["WR"]).assign(pos="WR", proy_espn=10.0)
    return f.assign(real=10.0 + rng.normal(0, 1, n) * sd)


def test_sin_estructura_gana_k_1():
    rng = np.random.default_rng(0)
    k, tabla = grupos.elegir_k(_wr(4000, rng, False), _wr(4000, rng, False))
    assert k["WR"] == 1
    assert set(tabla.k) == {1, 2, 3, 4, 5}


def test_con_estructura_gana_mas_de_un_grupo():
    rng = np.random.default_rng(1)
    k, _ = grupos.elegir_k(_wr(4000, rng, True), _wr(4000, rng, True))
    assert k["WR"] >= 2


def test_asignar_respeta_posiciones_y_es_estable():
    rng = np.random.default_rng(2)
    f = _wr(1000, rng, True)
    g = {"WR": grupos.ajustar(f, "WR", 2)}
    mezcla = pd.concat([f.head(5), pd.DataFrame({"pos": ["QB"], "rush_share": [0.1],
                                                 "snap_pct": [1.0]})], ignore_index=True)
    a = grupos.asignar(g, mezcla)
    assert a.iloc[-1] == 0  # QB sin grupos
    assert (a.iloc[:5].to_numpy() == g["WR"].asignar(f.head(5))).all()
