import json

import pandas as pd
import pytest

from fantasy.modelo import candidatos, validacion
from tests.test_seleccion import _temporada


def _res(delta, hi, por_pos):
    return {"delta": delta, "ic95": (delta - 0.1, hi), "por_pos": por_pos,
            "mae_modelo": 5.0, "mae_espn": 5.0 - delta}


def test_criterio():
    assert validacion.criterio(_res(-0.2, -0.05, {"QB": (5.0, 5.1), "RB": (6.0, 6.2)}))
    assert not validacion.criterio(_res(-0.2, 0.01, {"QB": (5.0, 5.1)}))       # IC toca 0
    assert not validacion.criterio(_res(-0.2, -0.05, {"QB": (5.2, 5.1)}))      # pierde en QB


def _registro_y_modelo():
    previas = pd.concat([_temporada(2023, 0), _temporada(2024, 1)], ignore_index=True)
    config = {"tipo": "ridge", "alpha": 10}
    m = candidatos.entrenar_v2(previas, config, k=0.9)
    return {"config": config, "k": 0.9, "commit": "abc"}, m, previas


def _guardado(tmp_path, m):
    from fantasy.modelo.estado import huella
    ruta = tmp_path / "m.joblib"
    candidatos.guardar_v2(m, ruta)
    return ruta, huella(ruta)


def test_validar_sellado_corre_una_sola_vez(tmp_path):
    registro, m, previas = _registro_y_modelo()
    ruta, sha = _guardado(tmp_path, m)
    registro["sha256"] = sha
    destino = tmp_path / "2025.json"
    otros = {"git_limpio": lambda: True, "src_igual": lambda c: True, "ruta_modelo": ruta}
    res = validacion.validar_sellado(registro, m, previas, lambda: _temporada(2025, 2),
                                     destino, **otros)
    assert destino.exists() and "paso" in json.loads(destino.read_text(encoding="utf-8"))
    assert isinstance(res["paso"], bool)
    with pytest.raises(RuntimeError, match="ya se corrió"):
        validacion.validar_sellado(registro, m, previas, lambda: _temporada(2025, 2),
                                   destino, **otros)


def test_validar_sellado_exige_repo_limpio_y_modelo_registrado(tmp_path):
    registro, m, previas = _registro_y_modelo()
    ruta, registro["sha256"] = _guardado(tmp_path, m)
    llamado = []

    def obtener():
        llamado.append(1)
        return _temporada(2025, 2)

    with pytest.raises(RuntimeError, match="cambios"):
        validacion.validar_sellado(registro, m, previas, obtener, tmp_path / "a.json",
                                   git_limpio=lambda: False, src_igual=lambda c: True,
                                   ruta_modelo=ruta)
    otro = dict(registro, k=0.95)  # Review Focus 4
    with pytest.raises(RuntimeError, match="registro"):
        validacion.validar_sellado(otro, m, previas, obtener, tmp_path / "b.json",
                                   git_limpio=lambda: True, src_igual=lambda c: True,
                                   ruta_modelo=ruta)
    assert llamado == []  # 2025 nunca se tocó


def test_cli_sin_bandera_no_corre():
    from fantasy.cli import main
    assert main(["validar"]) == 2
