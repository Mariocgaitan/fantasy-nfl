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


def _wr3(n, rng):
    """Tres tipos según el rasgo 0, con dispersión distinta (3, 8 y 15 puntos)."""
    X = rng.normal(0, 1, (n, 4))
    tipo = rng.integers(0, 3, n)
    X[:, 0] = np.array([-4.0, 0.0, 4.0])[tipo] + rng.normal(0, 0.3, n)
    sd = np.array([3.0, 8.0, 15.0])[tipo]
    f = pd.DataFrame(X, columns=RASGOS["WR"]).assign(pos="WR", proy_espn=10.0)
    return f.assign(real=10.0 + rng.normal(0, 1, n) * sd)


def test_minimo_100_al_elegir_k_si_prueba_tres_grupos():
    # 450 filas en 3 grupos: ~150 por celda. Con el mínimo de 200 k=3 cae a la posición y su
    # CRPS es idéntico al de k=1; con 100 (solo para elegir k) se prueba de verdad.
    rng = np.random.default_rng(3)
    c, e = _wr3(450, rng), _wr3(450, rng)
    _, t200 = grupos.elegir_k(c, e)
    _, t100 = grupos.elegir_k(c, e, minimo_celda=100)
    crps = lambda t, k: float(t.loc[t.k == k, "crps"].iloc[0])
    assert crps(t200, 3) == crps(t200, 1)
    assert crps(t100, 3) < crps(t100, 1)
