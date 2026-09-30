import pandas as pd
import pytest

from fantasy.modelo import variables as v


def _datos():
    proy = pd.DataFrame({"jugador_id": [1, 1, 1, 2, 2, 2], "semana": [1, 2, 3] * 2,
                         "puntos": [10.0, 11.0, 12.0, 5.0, 6.0, 7.0]})
    reales = pd.DataFrame({"jugador_id": [1, 1], "semana": [1, 2], "puntos": [20.0, 10.0]})
    uso = pd.DataFrame({"jugador_id": [1, 1], "semana": [1, 2], "snaps_pct": [0.8, 0.6],
                        "targets": [6, 4], "acarreos": [0, 2]})
    pos = pd.Series({1: "WR", 2: "RB"})
    return proy, reales, uso, pos


def test_solo_usa_semanas_anteriores():
    f = v.filas(*_datos(), 2026).set_index(["jugador_id", "semana"])
    s3 = f.loc[(1, 3)]
    assert s3.pts_prev == pytest.approx(15.0) and s3.n_prev == 2
    assert s3.snaps_prev == pytest.approx(0.7) and s3.targets_prev == pytest.approx(5.0)
    assert s3.semana_fuente_max == 2 and pd.isna(s3.real)
    assert f.loc[(1, 2)].pts_prev == pytest.approx(20.0) and f.loc[(1, 2)].real == 10.0
    v.verificar_sin_fuga(f.reset_index())


def test_sin_partidos_previos_no_deja_nan():
    # Review Focus 2 y 3: el jugador 2 nunca jugó y no tiene uso.
    f = v.filas(*_datos(), 2026).set_index(["jugador_id", "semana"])
    s = f.loc[(2, 3)]
    assert s.n_prev == 0 and s.pts_prev == pytest.approx(7.0)  # su proyección de ESPN
    assert s.snaps_prev == 0 and s.targets_prev == 0
    assert not f[v.VARIABLES].isna().any().any()


def test_fuga_detiene():
    f = v.filas(*_datos(), 2026)
    f.loc[0, "semana_fuente_max"] = f.loc[0, "semana"]
    with pytest.raises(v.FugaDeDatos):
        v.verificar_sin_fuga(f)


def test_desde_crudos_de_la_fixture():
    import pathlib

    from fantasy.almacen.instantaneas import cargar
    c = cargar(pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30")
    f = v.desde_crudos(c, 2026, semanas=[4])
    assert len(f) > 200 and (f.semana == 4).all()
    assert not f[v.VARIABLES].isna().any().any()
    assert (f.n_prev <= 3).all()
