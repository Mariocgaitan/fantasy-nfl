import numpy as np
import pandas as pd
import pytest

from fantasy.modelo import ridge
from fantasy.modelo.variables import VARIABLES, FugaDeDatos


def _sinteticas(n=400, semilla=0):
    r = np.random.default_rng(semilla)
    f = pd.DataFrame({
        "jugador_id": np.arange(n), "temporada": 2024, "semana": 5,
        "pos": np.where(np.arange(n) % 2, "WR", "RB"),
        "proy_espn": r.uniform(5, 20, n), "pts_prev": r.uniform(0, 25, n),
        "snaps_prev": r.uniform(0, 1, n), "targets_prev": r.uniform(0, 10, n),
        "acarreos_prev": r.uniform(0, 15, n), "n_prev": r.integers(0, 4, n),
        "semana_fuente_max": 4,
    })
    f["real"] = 1.0 * f.proy_espn + 0.5 * f.targets_prev + r.normal(0, 0.5, n)
    return f


def test_aprende_la_relacion():
    f = _sinteticas()
    m = ridge.entrenar(f, alpha=0.1)
    pred = ridge.predecir(m, f)
    assert np.abs(pred - f.real).mean() < 1.0
    assert set(m.por_pos) == {"RB", "WR"}


def test_guardar_y_cargar(tmp_path):
    f = _sinteticas()
    m = ridge.entrenar(f)
    ridge.guardar(m, tmp_path / "m.json")
    m2 = ridge.cargar(tmp_path / "m.json")
    assert np.allclose(ridge.predecir(m, f), ridge.predecir(m2, f))


def test_version_de_variables_distinta_falla(tmp_path):
    m = ridge.entrenar(_sinteticas())
    m.variables = ["otra"]
    ridge.guardar(m, tmp_path / "m.json")
    with pytest.raises(ValueError, match="variables"):
        ridge.cargar(tmp_path / "m.json")


def test_no_entrena_con_fuga():
    f = _sinteticas()
    f.loc[0, "semana_fuente_max"] = 5
    with pytest.raises(FugaDeDatos):
        ridge.entrenar(f)


def test_posicion_sin_modelo_da_nan():
    m = ridge.entrenar(_sinteticas())
    f = _sinteticas(4).assign(pos="QB")
    assert ridge.predecir(m, f).isna().all()
    assert VARIABLES == m.variables
