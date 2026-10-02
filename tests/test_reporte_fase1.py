import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte import correo
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def test_martes_trae_intercambios():
    r = armar(cargar(SEM4), MARTES, "martes", 5)
    assert 1 <= len(r.intercambios) <= 5
    assert "Norway Ass" not in {x["rival"] for x in r.intercambios}
    x = r.intercambios[0]
    assert x["das"] and x["recibes"] and x["ganancia"] > 0
    html = generar_html(r)
    assert "Intercambios" in html and "propón una a la vez" in html
    assert x["recibes"][0] in html
    assert "Reporte del martes (semana 4)" in correo.resumen(r)


def test_viernes_no_trae_intercambios():
    r = armar(cargar(SEM4), MARTES, "viernes", 5)
    assert r.intercambios == []
    assert "propón una a la vez" not in generar_html(r)


def test_agencia_no_suelta_a_nabers():
    r = armar(cargar(SEM4), MARTES, "martes", 5)
    assert "Malik Nabers" not in {a["soltar"] for a in r.agencia}


def test_si_falla_la_busqueda_el_reporte_sale_igual(monkeypatch):
    def rota(*a, **k):
        raise KeyError("sin plantilla")

    monkeypatch.setattr("fantasy.reporte.armado.intercambios_mod.buscar", rota)
    r = armar(cargar(SEM4), MARTES, "martes", 5)
    assert r.intercambios == [] and r.alineacion
    assert any("intercambios" in a.lower() for a in r.avisos)


def test_ningun_libre_sale_en_agencia_y_en_intercambios():
    r = armar(cargar(SEM4), MARTES, "martes", 5)
    pedidos = {a["pedir"] for a in r.agencia}
    assert pedidos
    for x in r.intercambios:
        assert not pedidos & set(x["relleno"])
