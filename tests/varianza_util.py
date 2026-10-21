import numpy as np

from fantasy.varianza.artefacto import VERSION, Artefacto
from fantasy.varianza.errores import POS, Colecciones


def art_prueba(sd=8.0, corr=None, n=5000, semilla=0) -> Artefacto:
    rng = np.random.default_rng(semilla)
    muestras = {(p,): np.sort(rng.normal(0, sd, n)) if sd else np.zeros(n) for p in POS}
    col = Colecciones({p: (5.0, 12.0) for p in POS}, muestras, {p: -10.0 for p in POS})
    return Artefacto(VERSION, {p: 1 for p in POS}, {}, col, corr or {}, (2023,))
