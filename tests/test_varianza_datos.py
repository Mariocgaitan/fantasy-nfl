from pathlib import Path

import pytest

from fantasy.ingesta import historico
from fantasy.varianza import artefacto, datos, rol

RAIZ = Path(__file__).parents[1] / "historico"


@pytest.fixture(scope="module")
def t23():
    return datos.tabla(historico.cargar_historico(RAIZ, 2023), 2023)


def test_tabla_tiene_rol_sin_fuga_y_equipo(t23):
    assert set(rol.TODOS) <= set(t23.columns)
    assert (t23.fuente_max < t23.semana).all()
    assert t23.semana.min() == 1 and t23.semana.max() == 17
    c = datos.para_construir(t23)
    assert c.relevante.all() and c.semana.between(3, 17).all()
    assert c.equipo.notna().mean() > 0.9
    assert c[rol.TODOS].notna().all().all()


def test_artefacto_ida_y_vuelta(t23, tmp_path):
    c = datos.para_construir(t23)
    art = artefacto.construir(c, c, {"QB": 1, "RB": 2, "WR": 2, "TE": 1})
    ruta = tmp_path / "v.joblib"
    artefacto.guardar(art, ruta)
    otra = artefacto.cargar(ruta)
    assert otra.k == art.k and otra.temporadas == (2023,)
    assert len(otra.colecciones.muestra("WR", 1, 2)) >= 200
