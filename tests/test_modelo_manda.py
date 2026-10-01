import json
import pathlib

import pandas as pd

from fantasy.almacen.instantaneas import cargar
from fantasy.modelo.estado import estado_validacion
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def test_estado(tmp_path):
    assert estado_validacion(tmp_path) == {"manda": False, "fuente": None}
    (tmp_path / "2025.json").write_text(json.dumps({"paso": False}), encoding="utf-8")
    assert estado_validacion(tmp_path)["manda"] is False
    (tmp_path / "2026_vivo.json").write_text(json.dumps({"paso": True}), encoding="utf-8")
    assert estado_validacion(tmp_path) == {"manda": True, "fuente": "2026 en vivo"}


def test_sin_validar_sigue_decidiendo_espn(tmp_path):
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_validacion=tmp_path)
    assert r.validado is None
    assert all(f["proy"] == f["espn"] for f in r.alineacion)
    assert "SIN VALIDAR" in generar_html(r)


def test_cuando_manda_decide_el_modelo(tmp_path, monkeypatch):
    (tmp_path / "2025.json").write_text(json.dumps({"paso": True}), encoding="utf-8")

    def prediccion_falsa(crudos, temporada, semana, ruta):
        from fantasy.ingesta import espn
        pr = espn.parsear_proyecciones(crudos["proyecciones"], temporada)
        pr = pr[pr.semana == semana]
        return {int(j): (40.0 if j == pr.jugador_id.iloc[0] else p * 0.5)
                for j, p in zip(pr.jugador_id, pr.puntos, strict=True)}, None

    monkeypatch.setattr("fantasy.reporte.armado.prediccion_modelo", prediccion_falsa)
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_validacion=tmp_path)
    assert r.validado == "2025 sellada"
    assert any(f["proy"] != f["espn"] for f in r.alineacion)
    html = generar_html(r)
    assert "VALIDADO" in html and "SIN VALIDAR" not in html
