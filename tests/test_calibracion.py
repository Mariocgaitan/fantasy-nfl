import numpy as np
import pandas as pd

from fantasy.modelo import calibracion


def test_recupera_el_sesgo():
    r = np.random.default_rng(0)
    n = 4000
    f = pd.DataFrame({"semana": np.repeat(np.arange(1, 11), n // 10),
                      "pos": np.tile(["QB", "RB", "WR", "TE"], n // 4),
                      "proy_espn": r.uniform(5, 25, n)})
    f["real"] = 0.9 * f.proy_espn + r.laplace(0, 1.0, n)  # mediana = 0.9 · proyección
    k = calibracion.factor(f)
    assert abs(k - 0.9) <= 0.015
    assert k in calibracion.RANGO
