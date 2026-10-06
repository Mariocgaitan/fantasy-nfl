import json
import pathlib

import pandas as pd
import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.modelo.estado import huella
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html
from fantasy.varianza import artefacto, en_vivo, validar
from tests.varianza_util import art_prueba

VIE = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-10-02"
AHORA = pd.Timestamp("2026-10-01 23:23", tz="UTC")


@pytest.fixture(scope="module")
def crudos():
    return cargar(VIE)


def _entorno(tmp_path, paso_1, paso_2, escribir=True):
    ruta = tmp_path / "varianza.joblib"
    artefacto.guardar(art_prueba(), ruta)
    if escribir:
        (tmp_path / validar.RESULTADO).write_text(json.dumps(
            {"paso_1": paso_1, "paso_2": paso_2, "sha256": huella(ruta)}), encoding="utf-8")
    return {"ruta_validacion": tmp_path, "ruta_varianza": ruta,
                "ruta_rol_previo": tmp_path / "no_existe.csv"}


def _r(crudos, tmp_path, tipo="viernes", **kw):
    return armar(crudos, AHORA, tipo, 5, **_entorno(tmp_path, **kw))


def test_sin_resultado_no_cambia_nada(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=False, paso_2=False, escribir=False)
    base = armar(crudos, AHORA, "viernes", 5, ruta_validacion=tmp_path)
    assert r.p_ganar is None and r.explicaciones_pg == []
    assert [x["jugador_id"] for x in r.alineacion] == [x["jugador_id"] for x in base.alineacion]
    assert not any("probabilidad de ganar" in a.lower() for a in r.avisos)


def test_solo_creible_muestra_porcentaje_sin_cambiar_la_alineacion(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=False, paso_2=True)
    base = armar(crudos, AHORA, "viernes", 5, ruta_validacion=tmp_path / "x")
    assert 0 <= r.p_ganar <= 100
    assert [x["jugador_id"] for x in r.alineacion] == [x["jugador_id"] for x in base.alineacion]
    assert "Probabilidad de ganar" in generar_html(r)


def test_pasa_las_dos_puede_alinear_y_no_se_aleja_10_puntos(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=True, paso_2=True)
    base = armar(crudos, AHORA, "viernes", 5, ruta_validacion=tmp_path / "x")
    assert r.p_ganar is not None
    assert r.esperado >= base.esperado - 10.0


def test_no_paso_avisa(crudos, tmp_path):
    r = _r(crudos, tmp_path, paso_1=True, paso_2=False)
    assert r.p_ganar is None
    assert "La probabilidad de ganar no pasó la validación." in r.avisos


def test_martes_es_preliminar(crudos, tmp_path):
    r = _r(crudos, tmp_path, tipo="martes", paso_1=False, paso_2=True)
    assert r.p_ganar_preliminar and "preliminar" in generar_html(r)


def test_artefacto_roto_no_tumba_el_reporte(crudos, tmp_path):
    kw = _entorno(tmp_path, True, True)
    kw["ruta_varianza"].write_bytes(b"roto")
    (tmp_path / validar.RESULTADO).write_text(json.dumps(
        {"paso_1": True, "paso_2": True, "sha256": huella(kw["ruta_varianza"])}),
        encoding="utf-8")
    r = armar(crudos, AHORA, "viernes", 5, **kw)
    assert r.p_ganar is None
    assert any("probabilidad de ganar" in a.lower() for a in r.avisos)


def test_sin_nflverse_igual_calcula(crudos, tmp_path):
    sin = {k: v for k, v in crudos.items() if k not in ("semanal", "snaps", "jugadores")}
    r = armar(sin, AHORA, "viernes", 5, **_entorno(tmp_path, False, True))
    assert r.p_ganar is not None


def test_rival_con_titular_fuera_usa_su_optima():
    t = pd.DataFrame({
        "jugador_id": [1, 2, 3, 4, 5, 6, 7, 8], "pos": ["QB", "RB", "RB", "WR", "WR", "TE",
                                                        "WR", "WR"],
        "esperado": [20, 15, 14, 13, 12, 10, 0, 11], "proy": [20, 15, 14, 13, 12, 10, 9, 11],
        "lesion": ["ACTIVE"] * 6 + ["OUT", "ACTIVE"], "inicio_utc": pd.Timestamp(
            "2026-10-05 17:00", tz="UTC"), "slot": ["QB", "RB", "RB", "WR", "WR", "TE",
                                                     "FLEX", "BANCA"], "bloqueado": False})
    al = en_vivo.alineacion_rival(t)
    assert 7 not in al.ids() and 8 in al.ids()
