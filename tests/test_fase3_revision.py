"""Pruebas de los hallazgos de la revisión final de la fase 3."""

import gzip
import io
import json
import pathlib

import pandas as pd
import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.esquemas import DatosInvalidos
from fantasy.ingesta import nflverse
from fantasy.modelo import candidatos, validacion
from fantasy.modelo.estado import estado_validacion, huella
from fantasy.reporte.armado import armar
from tests.test_seleccion import _temporada

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"
MARTES = pd.Timestamp("2026-09-30 01:40", tz="UTC")


def _modelo(tmp_path):
    previas = pd.concat([_temporada(2023, 0), _temporada(2024, 1)], ignore_index=True)
    m = candidatos.entrenar_v2(previas, {"tipo": "ridge", "alpha": 10}, k=0.9)
    ruta = tmp_path / "m.joblib"
    candidatos.guardar_v2(m, ruta)
    return m, ruta, previas


def _validado(tmp_path, ruta_modelo, paso=True, sha=None):
    val = tmp_path / "val"
    val.mkdir()
    (val / "2025.json").write_text(json.dumps({"paso": paso, "k": 0.9,
                                               "sha256": sha or huella(ruta_modelo)}),
                                   encoding="utf-8")
    return val


# 1 y 4 — "VALIDADO" solo si el modelo validado de verdad decidió
def test_validado_solo_si_el_modelo_decidio(tmp_path):
    _, ruta, _ = _modelo(tmp_path)
    val = _validado(tmp_path, ruta)
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=ruta, ruta_validacion=val)
    # La fixture no trae juegos: el modelo no puede predecir, así que decide ESPN.
    assert r.validado is None
    assert any("validado" in a.lower() for a in r.avisos)


def test_modelo_distinto_al_validado_no_manda(tmp_path):
    _, ruta, _ = _modelo(tmp_path)
    val = _validado(tmp_path, ruta, sha="otro")
    assert estado_validacion(val, ruta)["manda"] is False
    (tmp_path / "ok").mkdir()
    assert estado_validacion(_validado(tmp_path / "ok", ruta), ruta)["manda"] is True


# 2 — games.csv con otro formato: DatosInvalidos, no KeyError
def test_juegos_con_otro_formato():
    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    malo = b"season,week,home,away\n2026,5,KC,BUF\n"
    with pytest.raises(DatosInvalidos, match="juegos"):
        nflverse.bajar_juegos((2026,), abrir=lambda u, timeout: Resp(malo),
                              dormir=lambda s: None)


# 3 — cuando manda, lo que no predice el modelo usa ESPN calibrada
def test_semanas_futuras_con_espn_calibrada(tmp_path, monkeypatch):
    _, ruta, _ = _modelo(tmp_path)
    val = _validado(tmp_path, ruta)

    def falsa(crudos, temporada, semana, r):
        from fantasy.ingesta import espn
        pr = espn.parsear_proyecciones(crudos["proyecciones"], temporada)
        pr = pr[(pr.semana == semana) & (pr.puntos > 0)]
        return {int(j): float(p) for j, p in zip(pr.jugador_id, pr.puntos, strict=True)}, None

    capturadas = {}
    original = __import__("fantasy.decision.agencia_libre",
                          fromlist=["recomendar"]).recomendar

    def espia(jugadores, tablas, *a, **k):
        capturadas.update(tablas)
        return original(jugadores, tablas, *a, **k)

    monkeypatch.setattr("fantasy.reporte.armado.prediccion_modelo", falsa)
    monkeypatch.setattr("fantasy.reporte.armado.agencia_libre.recomendar", espia)
    r = armar(cargar(SEM4), MARTES, "viernes", 5, ruta_modelo=ruta, ruta_validacion=val)
    assert r.validado == "2025 sellada"
    from fantasy.ingesta import espn
    pr = espn.parsear_proyecciones(cargar(SEM4)["proyecciones"], 2026)
    futura = capturadas[6].set_index("jugador_id").proy
    crudo = pr[pr.semana == 6].set_index("jugador_id").puntos
    comunes = futura.index.intersection(crudo[crudo > 0].index)[:20]
    assert (abs(futura[comunes] - 0.9 * crudo[comunes]) < 1e-6).all()


# 5 — candado de la corrida única
def test_sellado_exige_src_igual_al_registro_y_huella(tmp_path):
    m, ruta, previas = _modelo(tmp_path)
    registro = {"config": m.config, "k": m.k, "sha256": huella(ruta), "commit": "abc"}
    obtener = lambda: _temporada(2025, 2)
    with pytest.raises(RuntimeError, match="código"):
        validacion.validar_sellado(registro, m, previas, obtener, tmp_path / "a.json",
                                   git_limpio=lambda: True, src_igual=lambda c: False,
                                   ruta_modelo=ruta)
    with pytest.raises(RuntimeError, match="huella"):
        validacion.validar_sellado(dict(registro, sha256="otra"), m, previas, obtener,
                                   tmp_path / "b.json", git_limpio=lambda: True,
                                   src_igual=lambda c: True, ruta_modelo=ruta)
    res = validacion.validar_sellado(registro, m, previas, obtener, tmp_path / "c.json",
                                     git_limpio=lambda: True, src_igual=lambda c: True,
                                     ruta_modelo=ruta, head="def")
    assert res["sha256"] == huella(ruta) and res["head"] == "def"


# 6 y 7 — validación en vivo
TODOS = ("calendario", "proyecciones", "semanal", "snaps", "jugadores", "juegos")


def _snap(raiz, semana, nombre, primer_ms, ultimo_ms, archivos=TODOS):
    c = raiz / "instantaneas" / "2026" / f"sem{semana:02d}" / nombre
    c.mkdir(parents=True)
    juegos = [{"date": primer_ms, "homeProTeamId": 1, "awayProTeamId": 2},
              {"date": ultimo_ms, "homeProTeamId": 1, "awayProTeamId": 2}]
    cal = {"settings": {"proTeams": [{"id": 1, "abbrev": "KC", "proGamesByScoringPeriod": {
        "5": juegos, "6": juegos}}]}}
    for a in archivos:
        nombre = next(n for n in validacion.ARCHIVOS_NECESARIOS if n.startswith(a + "."))
        contenido = json.dumps(cal) if a == "calendario" else "x"
        (c / nombre).write_bytes(gzip.compress(contenido.encode()))
    return c


def _ms(s):
    return int(pd.Timestamp(s, tz="UTC").timestamp() * 1000)


def test_salta_instantaneas_incompletas(tmp_path):
    p, u = _ms("2026-10-09 00:15"), _ms("2026-10-13 00:15")
    buena = _snap(tmp_path, 5, "2026-10-06T19-07", p, u)
    _snap(tmp_path, 5, "2026-10-09T08-07", p, u, archivos=("calendario",))  # sin nflverse
    assert validacion.instantaneas_previas(tmp_path) == {5: buena}


def test_reales_de_la_primera_instantanea_despues_de_la_semana(tmp_path):
    p, u = _ms("2026-10-09 00:15"), _ms("2026-10-13 00:15")  # último partido: martes 11:15
    _snap(tmp_path, 5, "2026-10-06T19-07", p, u)
    _snap(tmp_path, 6, "2026-10-13T08-07", p, u)        # antes de que acabe el lunes
    despues = _snap(tmp_path, 6, "2026-10-13T19-07", p, u)
    assert validacion.instantanea_posterior(tmp_path, 5) == despues
    assert validacion.instantanea_posterior(tmp_path, 7) is None   # sin partidos conocidos


def test_resultado_en_vivo_se_congela(tmp_path):
    destino = tmp_path / "vivo.json"
    destino.write_text(json.dumps({"paso": False, "semanas": [5, 6]}), encoding="utf-8")
    res = validacion.validar_en_vivo(object(), {}, {}, destino)
    assert res["paso"] is False and res["listo"] is True and res["congelado"] is True
