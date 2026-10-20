import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte import armado
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

VIE = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-10-02"
AHORA = pd.Timestamp("2026-10-01 23:23", tz="UTC")


def _r():
    return armar(cargar(VIE), AHORA, "viernes", 5)


def test_viernes_semana4_washington_watson_es_empate():
    e = [x for x in _r().empates if x["titular"] == "Parker Washington"]
    assert e and e[0]["tipo"] == "empate" and e[0]["alternativa"] == "Christian Watson"
    assert e[0]["pts_titular"] is not None and e[0]["pts_alternativa"] is not None


def test_viernes_semana4_young_shough_es_casi():
    e = [x for x in _r().empates if x["titular"] == "Bryce Young"]
    assert e and e[0]["tipo"] == "casi" and e[0]["alternativa"] == "Tyler Shough"
    assert 1.0 < e[0]["diferencia"] <= 2.0


def test_empates_no_cambian_alineacion_ni_acciones(monkeypatch):
    con = _r()
    monkeypatch.setattr(armado.empates_mod, "buscar", lambda al, t, pts: [])
    sin = _r()
    assert sin.empates == [] and con.empates
    assert (con.alineacion, con.esperado, con.acciones) == (sin.alineacion, sin.esperado,
                                                            sin.acciones)


def test_sin_juegos_sale_sin_linea():
    crudos = cargar(VIE)
    crudos.pop("juegos")
    r = armar(crudos, AHORA, "viernes", 5)
    assert r.empates and all(x["pts_titular"] is None for x in r.empates)


def test_pagina_muestra_empates_y_nota():
    html = generar_html(_r())
    assert "Empate en" in html and "Casi empate en" in html and "sin línea" not in html
    assert "moneda" in html


def test_nota_explica_que_los_puntos_descuentan_la_probabilidad_de_jugar():
    html = generar_html(_r())
    assert "probabilidad de que juegue" in html
    assert "1 punto o menos" in html
