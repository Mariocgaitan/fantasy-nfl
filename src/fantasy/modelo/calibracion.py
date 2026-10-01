"""ESPN calibrada: el factor que mejor corrige el sesgo de ESPN en temporadas anteriores."""

import numpy as np
import pandas as pd

from fantasy.modelo.evaluar import relevantes

RANGO = np.round(np.arange(0.80, 1.1001, 0.005), 3)


def factor(f: pd.DataFrame) -> float:
    r = relevantes(f[f["real"].notna()])
    proy, real = r["proy_espn"].to_numpy(float), r["real"].to_numpy(float)
    errores = [(float(np.abs(k * proy - real).mean()), abs(k - 1.0), float(k)) for k in RANGO]
    return min(errores)[2]
