import numpy as np
import pandas as pd
import pytest

from fantasy.varianza import errores


def test_crps_de_un_punto_es_la_distancia():
    assert errores.crps(np.array([0.0]), np.array([1.0, -2.0])) == pytest.approx([1.0, 2.0])


def test_crps_normal_estandar_en_cero():
    m = np.sort(np.random.default_rng(0).standard_normal(200_000))
    assert errores.crps(m, np.array([0.0]))[0] == pytest.approx(0.2337, abs=0.005)


def _filas(n, rng, pos="WR", grupo=0, proy=10.0, sd=5.0):
    p = proy + rng.uniform(0, 1, n)  # continuas: los cortes no caen en empates
    return pd.DataFrame({"pos": pos, "grupo": grupo, "proy_espn": p,
                         "real": p + rng.normal(0, sd, n)})


def test_construir_tramos_y_respaldo():
    rng = np.random.default_rng(1)
    f = pd.concat([_filas(600, rng, proy=5.0), _filas(600, rng, proy=10.0),
                   _filas(600, rng, proy=20.0), _filas(50, rng, grupo=1, proy=20.0)])
    col = errores.construir(f)
    assert col.tramo("WR", 4.0) == 0 and col.tramo("WR", 25.0) == 2
    tramos = np.array([col.tramo("WR", x) for x in f.proy_espn])
    esperado = int(((f.grupo == 0).to_numpy() & (tramos == 2)).sum())
    assert esperado >= 500 and len(col.muestra("WR", 0, 2)) == esperado
    # grupo 1 tiene 50 errores: cae a (WR,) completo
    assert len(col.muestra("WR", 1, 2)) == len(col.muestras[("WR",)])
    assert np.all(np.diff(col.muestra("WR", 0, 0)) >= 0)
    assert col.piso["WR"] == pytest.approx(f.real.min())


def test_correlaciones_entre_companeros():
    rng = np.random.default_rng(2)
    n = 800
    z = rng.multivariate_normal([0, 0], [[1, 0.5], [0.5, 1]], n)
    qb = pd.DataFrame({"temporada": 2023, "semana": np.arange(n) % 17, "equipo":
                       [f"T{i // 17}" for i in range(n)], "jugador_id": np.arange(n),
                       "pos": "QB", "error": z[:, 0]})
    wr = qb.assign(jugador_id=qb.jugador_id + 10_000, pos="WR", error=z[:, 1])
    te = qb.head(100).assign(jugador_id=qb.head(100).jugador_id + 20_000, pos="TE")
    corr = errores.correlaciones(pd.concat([qb, wr, te]))
    assert corr[("QB", "WR")] == pytest.approx(0.5, abs=0.08)
    assert corr[("QB", "TE")] == 0.0  # solo 100 pares
    assert errores.rho(corr, "WR", "QB") == corr[("QB", "WR")]
