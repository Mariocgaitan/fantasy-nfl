import numpy as np
import pandas as pd
import pytest

from fantasy.modelo import candidatos as c
from fantasy.modelo.variables import VARIABLES_V2, FugaDeDatos


def _datos(n=2000, semilla=0):
    r = np.random.default_rng(semilla)
    f = pd.DataFrame({v: r.uniform(0, 1, n) for v in VARIABLES_V2})
    f["proy_espn"] = r.uniform(5, 20, n)
    f["pts_equipo"] = r.uniform(15, 30, n)
    f["pos"] = np.tile(["QB", "RB", "WR", "TE"], n // 4)
    f["jugador_id"], f["temporada"], f["semana"], f["semana_fuente_max"] = np.arange(n), 2024, 5, 4
    # Lo que ESPN no ve: el contexto del partido mueve ±2 puntos.
    f["real"] = 0.95 * f.proy_espn + 0.4 * (f.pts_equipo - 22.5) + r.normal(0, 0.5, n)
    return f


def test_configs():
    assert len(c.CONFIGS) == 7
    assert [c.nombre_config(x) for x in c.CONFIGS][:2] == ["ridge(alpha=1)", "ridge(alpha=10)"]


@pytest.mark.parametrize("config", [c.CONFIGS[0], c.CONFIGS[4]])
def test_aprende_la_correccion(config):
    f = _datos()
    m = c.entrenar_v2(f, config, k=0.95)
    pred = c.predecir_v2(m, f)
    base = np.abs(0.95 * f.proy_espn - f.real).mean()
    assert np.abs(pred - f.real).mean() < 0.7 * base


def test_guardar_y_cargar(tmp_path):
    f = _datos()
    m = c.entrenar_v2(f, c.CONFIGS[3], k=0.95)
    c.guardar_v2(m, tmp_path / "m.joblib")
    m2 = c.cargar_v2(tmp_path / "m.joblib")
    assert np.allclose(c.predecir_v2(m, f), c.predecir_v2(m2, f))
    m.variables = ["otra"]
    c.guardar_v2(m, tmp_path / "malo.joblib")
    with pytest.raises(ValueError, match="variables"):
        c.cargar_v2(tmp_path / "malo.joblib")


def test_no_entrena_con_fuga():
    f = _datos()
    f.loc[0, "semana_fuente_max"] = 5
    with pytest.raises(FugaDeDatos):
        c.entrenar_v2(f, c.CONFIGS[0], k=1.0)
