import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte.armado import armar, hora_sidney
from fantasy.reporte.html import generar_html

VIE = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-10-02"
AHORA = pd.Timestamp("2026-10-01 23:23", tz="UTC")


def _r(tipo="viernes"):
    return armar(cargar(VIE), AHORA, tipo, 5)


def test_viernes_real_pide_respaldo_para_el_lugar_vacio():
    r = _r()
    assert (r.tope, r.lugares_libres) == (14, 1)
    lugar = [a for a in r.acciones if a.tipo == "lugar"]
    assert len(lugar) == 1 and lugar[0].urgencia == "recomendado"
    assert any(n in lugar[0].porque for n in ("Jahmyr Gibbs", "Ashton Jeanty",
                                              "Amon-Ra St. Brown"))


def test_viernes_real_daniels_no_es_recomendado():
    r = _r()
    rec = [a.texto for a in r.acciones if a.urgencia == "recomendado"]
    assert not any("Daniels" in t for t in rec)
    assert all(a["semanal"] < 1.0 for a in r.agencia if a["pedir"] == "Jayden Daniels")


def test_plantilla_completa_con_banca():
    r = _r()
    lugares = [f["lugar"] for f in r.plantilla]
    assert lugares[:7] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]
    assert lugares.count("Banca") == 6
    assert all(f["hora"] for f in r.plantilla)


def test_sin_respaldo_trae_motivo():
    r = _r()
    gibbs = next(x for x in r.reemplazos if x["titular"] == "Jahmyr Gibbs")
    assert gibbs["suplente"] is None and gibbs["motivo"] == "sin_posicion"


def test_rol_dice_de_quien_es():
    r = _r()
    assert all("dueno" in x for x in r.rol)


def test_martes_intercambios_con_ganancia_semanal():
    r = _r("martes")
    assert all("semanal" in x for x in r.intercambios)


def test_sin_nflverse_sale_igual():
    # Review Focus 4
    crudos = cargar(VIE)
    for k in ("semanal", "snaps", "jugadores"):
        crudos.pop(k, None)
    r = armar(crudos, AHORA, "viernes", 5)
    assert r.rol == [] and r.acciones is not None


def test_hora_sidney():
    assert hora_sidney(pd.Timestamp("2026-10-02 07:00", tz="UTC")) == "vie 17:00"
    assert hora_sidney(None) == "descansa"
    assert hora_sidney(pd.NaT) == "descansa"


def test_pagina_empieza_con_que_hacer():
    html = generar_html(_r())
    assert html.index("Qué hacer") < html.index("Tu plantilla")
    assert "Recomendado" in html and "sin soltar a nadie" in html
    assert "Lugares libres: 1 de 14" in html


def test_pagina_sin_modelo_ni_sello():
    html = generar_html(_r())
    assert "Modelo" not in html and "SIN VALIDAR" not in html
    assert "Decide la proyección de ESPN." in html


def test_pagina_explica_sin_respaldo_y_columnas_de_rol():
    html = generar_html(_r())
    assert "no tienes RB en la banca" in html
    assert "% de las jugadas de ataque" in html and "pases + carreras" in html


def test_pagina_ganancia_por_semana():
    html = generar_html(_r())
    assert "por semana" in html


def test_nada_que_hacer_hoy():
    r = _r()
    r.acciones = []
    assert "Nada que hacer hoy." in generar_html(r)
