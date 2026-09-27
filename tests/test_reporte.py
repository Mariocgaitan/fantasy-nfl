import urllib.parse

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.reporte import correo
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

AHORA = pd.Timestamp("2026-09-25 02:26", tz="UTC")


def test_armar_semana3(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    assert r.semana == 3
    assert [f["slot"] for f in r.alineacion] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]
    assert r.cambios == []  # la alineación de Mario ya era la óptima
    shough = next(x for x in r.reemplazos if x["titular"] == "Tyler Shough")
    assert shough["suplente"] is None
    assert len(r.agencia) >= 1
    assert all(a["ganancia"] > 0 for a in r.agencia)


def test_armar_martes_es_de_la_semana_siguiente(fixture_dir):
    r = armar(cargar(fixture_dir), pd.Timestamp("2026-09-29 09:00", tz="UTC"), "martes", 5)
    assert r.semana == 4
    assert not any(f["bloqueado"] for f in r.alineacion)


def test_html_marca_sin_validar(fixture_dir):
    html = generar_html(armar(cargar(fixture_dir), AHORA, "viernes", 5))
    assert "SIN VALIDAR" in html
    assert "Tyler Shough" in html
    assert "sin respaldo útil" in html
    assert '<meta name="viewport"' in html


def test_resumen_y_envio(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    texto = correo.resumen(r)
    assert texto.startswith("Semana 3 · reporte del viernes · SIN VALIDAR")
    vistos = []

    class Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def abrir(req, timeout):
        vistos.append(req)
        return Resp()

    correo.enviar("tema-secreto", "yo@example.com", "Fantasy · semana 3", texto,
                  "https://x/reportes/a.html", abrir=abrir)
    req = vistos[0]
    q = urllib.parse.parse_qs(urllib.parse.urlparse(req.full_url).query)
    assert req.full_url.startswith("https://ntfy.sh/tema-secreto?")
    assert q["email"] == ["yo@example.com"] and q["click"] == ["https://x/reportes/a.html"]
    assert req.data.decode("utf-8") == texto and req.get_method() == "POST"


def test_horas_en_espanol(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    shough = next(x for x in r.reemplazos if x["titular"] == "Tyler Shough")
    assert shough["hora"] == "lun 06:25"


def test_agencia_libre_muestra_la_lesion(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    assert all("lesion" in a for a in r.agencia)
    html = generar_html(r)
    fuera = [a for a in r.agencia if a["lesion"] != "ACTIVE"]
    assert all(a["estado"] in html for a in fuera)


def test_suplente_muestra_su_lesion(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    cook = next(x for x in r.reemplazos if x["titular"] == "James Cook III")
    assert cook["lesion_suplente"] == "QUESTIONABLE"
    assert "en duda" in generar_html(r)


def test_temporada_terminada_no_arma_reporte(fixture_dir):
    import pytest

    from fantasy.reporte.armado import TemporadaTerminada
    with pytest.raises(TemporadaTerminada):
        crudos = cargar(fixture_dir)
        crudos["liga"] = dict(crudos["liga"], scoringPeriodId=17)
        armar(crudos, pd.Timestamp("2027-01-12 09:00", tz="UTC"), "martes", 5)


def test_correo_dice_si_el_sugerido_esta_lesionado(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    r.agencia[0]["lesion"] = "OUT"
    assert "(fuera" in correo.resumen(r)


def test_estados_en_espanol_y_descanso_visible(fixture_dir):
    r = armar(cargar(fixture_dir), AHORA, "viernes", 5)
    html = generar_html(r)
    assert "QUESTIONABLE" not in html and "ACTIVE" not in html
    assert "en duda" in html  # Coker, suplente de Cook
    # Un titular sin partido esa semana se marca como "descansa".
    r.alineacion[0]["estado"] = "descansa"
    assert "descansa" in generar_html(r)
    assert all("estado" in f for f in armar(cargar(fixture_dir), AHORA, "viernes", 5).alineacion)
