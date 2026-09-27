import pandas as pd
import pytest

from fantasy.ingesta import nflverse

WASHINGTON = 4432620  # id ESPN de Parker Washington


def test_uso_semanal_une_estadisticas_y_snaps(fixture_dir):
    u = nflverse.uso_semanal(
        pd.read_csv(fixture_dir / "semanal.csv"),
        pd.read_csv(fixture_dir / "snaps.csv"),
        pd.read_csv(fixture_dir / "jugadores.csv"),
    )
    pw = u[u.jugador_id == WASHINGTON].set_index("semana")
    assert pw.loc[2, "targets"] == 12
    assert pw.loc[2, "snaps_pct"] == pytest.approx(0.81)
    assert pw.loc[1, "snaps_pct"] == pytest.approx(0.61)
    assert u.jugador_id.dtype == "int64"
    assert u.snaps_pct.between(0, 1).all()


def test_tablas_desde_texto(fixture_dir):
    crudos = {n: (fixture_dir / f"{n}.csv").read_text(encoding="utf-8")
              for n in ("semanal", "snaps", "jugadores")}
    assert WASHINGTON in set(nflverse.tablas(crudos).jugador_id)


def test_bajar_reintenta_cortes_de_conexion():
    import io
    import urllib.error

    intentos = []

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def abrir(url, timeout):
        intentos.append(url)
        if len(intentos) == 1:
            raise urllib.error.URLError("conexión reiniciada")
        return Resp(b"position,espn_id,week\nWR,1,1\n")

    crudos = nflverse.bajar_nflverse(2026, abrir=abrir, dormir=lambda s: None)
    assert set(crudos) == {"semanal", "snaps", "jugadores"}
    assert len(intentos) == 4  # 1 fallo + 3 archivos
