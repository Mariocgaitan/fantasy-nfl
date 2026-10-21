import numpy as np
import pandas as pd
import pytest

from fantasy.varianza import simular
from tests.varianza_util import art_prueba


def _jug(proys, pos="WR", equipo=None, real=np.nan, p_jugar=1.0):
    return pd.DataFrame({"pos": pos, "proy": proys, "p_jugar": p_jugar, "grupo": 0,
                         "equipo": equipo, "real_fijo": real})


def test_sin_dispersion_gana_el_que_proyecta_mas():
    pts = simular.simular(_jug([20.0, 10.0]), art_prueba(sd=0), n=1000)
    assert simular.p_ganar(pts, [0], [1]) == 1.0
    assert simular.p_ganar(pts, [1], [0]) == 0.0


def test_equipos_identicos_dan_mitad():
    pts = simular.simular(_jug([15.0] * 4), art_prueba(), n=20_000)
    assert simular.p_ganar(pts, [0, 1], [2, 3]) == pytest.approx(0.5, abs=0.02)


def test_jugados_usan_sus_puntos_reales():
    jug = _jug([15.0, 15.0]).assign(real_fijo=[30.0, np.nan])
    pts = simular.simular(jug, art_prueba(), n=500)
    assert (pts[:, 0] == 30.0).all()


def test_no_juega_hace_cero_y_proyeccion_cero_tambien():
    jug = _jug([15.0, 0.0]).assign(p_jugar=[0.0, 1.0])
    pts = simular.simular(jug, art_prueba(), n=500)
    assert (pts == 0.0).all()


def test_companeros_correlacionados():
    jug = _jug([15.0, 15.0, 15.0], pos=["QB", "WR", "WR"], equipo=["DET", "DET", "CHI"])
    pts = simular.simular(jug, art_prueba(corr={("QB", "WR"): 0.5}), n=20_000)
    assert np.corrcoef(pts[:, 0], pts[:, 1])[0, 1] == pytest.approx(0.5, abs=0.05)
    assert abs(np.corrcoef(pts[:, 0], pts[:, 2])[0, 1]) < 0.03


def test_piso_y_dispersion():
    pts = simular.simular(_jug([1.0]), art_prueba(sd=20.0), n=5000)
    assert pts.min() >= -10.0
    assert simular.dispersion(pts, 0) > 0
