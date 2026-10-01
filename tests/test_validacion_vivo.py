import gzip
import json
from pathlib import Path

import pandas as pd

from fantasy.modelo import validacion


def _calendario(primer_partido_ms):
    return {"settings": {"proTeams": [{"id": 1, "abbrev": "KC", "proGamesByScoringPeriod": {
        "5": [{"date": primer_partido_ms, "homeProTeamId": 1, "awayProTeamId": 2}]}}]}}


def _snap(raiz: Path, semana: int, nombre: str, primer_partido_ms: int):
    c = raiz / "instantaneas" / "2026" / f"sem{semana:02d}" / nombre
    c.mkdir(parents=True)
    for archivo in validacion.ARCHIVOS_NECESARIOS:
        contenido = json.dumps(_calendario(primer_partido_ms)) if archivo.startswith(
            "calendario") else "x"
        (c / archivo).write_bytes(gzip.compress(contenido.encode()))
    return c


def test_solo_instantaneas_anteriores_al_primer_partido(tmp_path):
    # Review Focus 5. Primer partido de la semana 5: jueves 2026-10-08 20:15 ET
    # = viernes 2026-10-09 11:15 en Sídney (AEDT).
    ms = int(pd.Timestamp("2026-10-09 00:15", tz="UTC").timestamp() * 1000)
    _snap(tmp_path, 5, "2026-10-06T19-07", ms)
    viernes = _snap(tmp_path, 5, "2026-10-09T08-07", ms)
    _snap(tmp_path, 5, "2026-10-11T20-07", ms)   # domingo: ya empezó el jueves
    _snap(tmp_path, 4, "2026-10-02T08-07", ms)   # semana < 5: fuera
    assert validacion.instantaneas_previas(tmp_path) == {5: viernes}


def test_validar_en_vivo_espera_8_semanas(tmp_path):
    class Falso:
        pass

    res = validacion.validar_en_vivo(Falso(), {}, {"proyecciones": {"players": []}},
                                     tmp_path / "vivo.json")
    assert res == {"semanas": 0, "listo": False} and not (tmp_path / "vivo.json").exists()
