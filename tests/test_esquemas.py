import pandas as pd
import pytest

from fantasy.esquemas import PROYECCIONES, DatosInvalidos, validar


def test_validar_devuelve_columnas_en_orden():
    df = pd.DataFrame({"puntos": [1.0], "semana": [3], "jugador_id": [7], "extra": [0]})
    out = validar(df, PROYECCIONES, "proyecciones")
    assert list(out.columns) == ["jugador_id", "semana", "puntos"]


def test_validar_falla_si_falta_columna():
    with pytest.raises(DatosInvalidos, match="proyecciones: faltan columnas"):
        validar(pd.DataFrame({"semana": [3]}), PROYECCIONES, "proyecciones")
