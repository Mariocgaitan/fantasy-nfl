import json

import numpy as np
import pandas as pd
import pytest

from fantasy.modelo.estado import huella
from fantasy.varianza import validar


def _res(delta_por_semana, p=0.7, real=0.7, n=300, semilla=0):
    rng = np.random.default_rng(semilla)
    filas = []
    for w, d in delta_por_semana.items():
        gana = (rng.random(n) < real).astype(float)
        esp = gana.copy()
        k = int(abs(d) * n)
        esp[:k] = gana[:k] - np.sign(d)  # en k casos la otra forma pierde (o gana)
        filas.append(pd.DataFrame({"semana": w, "p": p, "gana_pg": gana,
                                   "gana_esp": esp.clip(0, 1), "cambia": True}))
    return pd.concat(filas, ignore_index=True)


def test_pasa_las_dos():
    r = validar.criterio(_res({w: 0.05 for w in range(3, 18)}), n_boot=2000)
    assert r["paso_1"] and r["paso_2"] and r["ic95"][0] > 0


def test_falla_1_si_no_gana_mas():
    r = validar.criterio(_res({w: 0.0 for w in range(3, 18)}), n_boot=2000)
    assert not r["paso_1"] and r["paso_2"]


def test_falla_2_si_los_porcentajes_no_son_creibles():
    r = validar.criterio(_res({w: 0.05 for w in range(3, 18)}, p=0.9, real=0.6), n_boot=2000)
    assert not r["paso_2"]


def _art(tmp_path):
    ruta = tmp_path / "varianza.joblib"
    ruta.write_bytes(b"artefacto")
    return ruta


def test_estado_segun_archivo_y_huella(tmp_path):
    ruta = _art(tmp_path)
    assert validar.estado(tmp_path, ruta) == {"existe": False, "paso_1": False, "paso_2": False}
    (tmp_path / validar.RESULTADO).write_text(json.dumps(
        {"paso_1": True, "paso_2": True, "sha256": huella(ruta)}), encoding="utf-8")
    assert validar.estado(tmp_path, ruta) == {"existe": True, "paso_1": True, "paso_2": True}
    ruta.write_bytes(b"otro artefacto")  # alguien lo regeneró
    assert validar.estado(tmp_path, ruta) == {"existe": True, "paso_1": False, "paso_2": False}


def test_sellado_se_niega(tmp_path):
    ruta = _art(tmp_path)
    reg = {"commit": "abc", "sha256": huella(ruta), "ligas": 1, "n_sim": 10, "semilla": 0}
    destino = tmp_path / validar.RESULTADO
    nunca = lambda: pytest.fail("no debe tocar 2025")
    casos = [
        {"git_limpio": lambda: False, "src_igual": lambda c: True},
        {"git_limpio": lambda: True, "src_igual": lambda c: False},
    ]
    for kw in casos:
        with pytest.raises(RuntimeError):
            validar.validar_sellado(reg, ruta, nunca, destino, **kw)
    with pytest.raises(RuntimeError, match="src/ cambió"):
        validar.validar_sellado(reg, ruta, nunca, destino, **casos[1])
    with pytest.raises(RuntimeError, match="huella"):
        validar.validar_sellado({**reg, "sha256": "x"}, ruta, nunca, destino,
                                git_limpio=lambda: True, src_igual=lambda c: True)
    destino.write_text("{}", encoding="utf-8")
    with pytest.raises(RuntimeError, match="ya se corrió"):
        validar.validar_sellado(reg, ruta, nunca, destino,
                                git_limpio=lambda: True, src_igual=lambda c: True)


def test_cli_validar_sin_bandera_no_corre():
    from fantasy.cli import main
    assert main(["varianza-validar"]) == 2


def test_el_sello_congela_todo_src():
    # El resultado de 2025 también depende de alineacion, evaluar, variables, espn y la cli.
    vistos = []

    class R:
        returncode = 0

    def git(*args):
        vistos.append(args)
        return R()

    assert validar.codigo_igual("abc", git)
    assert vistos == [("diff", "--quiet", "abc", "HEAD", "--", "src")]
