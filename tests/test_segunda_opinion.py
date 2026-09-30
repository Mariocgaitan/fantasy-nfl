import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.modelo import ridge
from fantasy.modelo.variables import VARIABLES
from fantasy.proyeccion.modelo import segunda_opinion
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def _modelo_copia_espn(ruta):
    # Coeficiente 1 sobre proy_espn estandarizada con escala 1: predice exactamente ESPN + 5.
    p = {"coef": [1.0] + [0.0] * (len(VARIABLES) - 1), "intercepto": 5.0,
         "media": [0.0] * len(VARIABLES), "escala": [1.0] * len(VARIABLES), "n": 1}
    ridge.guardar(ridge.Modelo(por_pos={x: p for x in ("QB", "RB", "WR", "TE")}), ruta)


def test_segunda_opinion_con_modelo(tmp_path):
    _modelo_copia_espn(tmp_path / "m.json")
    pred, aviso = segunda_opinion(cargar(SEM4), 2026, 4, tmp_path / "m.json")
    assert aviso is None and len(pred) > 200


def test_sin_modelo_avisa_y_no_truena(tmp_path):
    # Review Focus 4
    pred, aviso = segunda_opinion(cargar(SEM4), 2026, 4, tmp_path / "no_existe.json")
    assert pred == {} and "modelo" in aviso
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=tmp_path / "no_existe.json")
    assert all(f["modelo"] is None for f in r.alineacion)
    assert any("modelo" in a.lower() for a in r.avisos)
    assert "Modelo" not in generar_html(r)


def test_columna_y_bandera(tmp_path):
    _modelo_copia_espn(tmp_path / "m.json")
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=tmp_path / "m.json")
    assert all(abs(f["modelo"] - f["proy"] - 5.0) < 0.11 for f in r.alineacion)
    assert all(f["discrepa"] for f in r.alineacion)  # +5 > 3
    html = generar_html(r)
    assert "Modelo" in html and "⚑" in html


def test_modelo_danado_no_tumba_el_reporte(tmp_path):
    # Revisión final: el modelo nunca decide, así que tampoco puede bloquear el reporte.
    ruta = tmp_path / "m.json"
    ridge.guardar(ridge.Modelo(por_pos={"QB": {"intercepto": 1.0}}), ruta)  # sin coef
    pred, aviso = segunda_opinion(cargar(SEM4), 2026, 4, ruta)
    assert pred == {} and "modelo" in aviso.lower()
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=ruta)
    assert r.alineacion and all(f["modelo"] is None for f in r.alineacion)


def test_sin_proyeccion_de_espn_no_hay_numero_del_modelo(tmp_path):
    _modelo_copia_espn(tmp_path / "m.json")
    c = cargar(SEM4)
    pred, _ = segunda_opinion(c, 2026, 4, tmp_path / "m.json")
    from fantasy.ingesta import espn
    pr = espn.parsear_proyecciones(c["proyecciones"], 2026)
    ceros = set(pr[(pr.semana == 4) & (pr.puntos <= 0)].jugador_id)
    assert ceros and not ceros & set(pred)


def test_tabla_alineada_si_un_titular_no_tiene_modelo(tmp_path):
    _modelo_copia_espn(tmp_path / "m.json")
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=tmp_path / "m.json")
    r.alineacion[0]["modelo"] = None
    html = generar_html(r)
    import re
    filas = re.findall(r"<tr><td>(?:QB|RB|WR|TE|FLEX)</td>.*?</tr>", html, flags=re.DOTALL)
    assert len({f.count("<td") for f in filas}) == 1
