import pandas as pd
import pytest

from fantasy.ingesta import nflverse

WASHINGTON = 4432620  # id ESPN de Parker Washington
CSV_COMPLETO = (b"player_id,season_type,week,targets,carries,pfr_player_id,offense_pct,"
                b"gsis_id,pfr_id,espn_id,position\n"
                b"g1,REG,1,3,0,p1,0.5,g1,p1,1,WR\n")


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
    assert u.snaps_pct.dropna().between(0, 1).all()  # vacío = sin dato de snaps


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
        return Resp(CSV_COMPLETO)

    crudos = nflverse.bajar_nflverse(2026, abrir=abrir, dormir=lambda s: None)
    assert set(crudos) == {"semanal", "snaps", "jugadores"}
    assert len(intentos) == 4  # 1 fallo + 3 archivos


def test_bajar_falla_si_cambian_las_columnas():
    # Revisión 1: un cambio de formato debe degradar (DatosInvalidos), no tronar después.
    import io

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    with pytest.raises(nflverse.DatosInvalidos, match="offense_pct"):
        nflverse.bajar_nflverse(2026, abrir=lambda u, timeout: Resp(
            CSV_COMPLETO.replace(b"offense_pct", b"pct_ofensiva")), dormir=lambda s: None)


def test_sin_fila_de_snaps_no_es_cero():
    # Revisión 1: faltar el dato no es jugar 0% de los snaps.
    semanal = pd.DataFrame({"player_id": ["g1", "g1"], "season_type": ["REG", "REG"],
                            "week": [1, 2], "targets": [3, 4], "carries": [0, 0]})
    snaps = pd.DataFrame({"week": [2], "pfr_player_id": ["p1"], "offense_pct": [0.7]})
    jug = pd.DataFrame({"gsis_id": ["g1"], "pfr_id": ["p1"], "espn_id": [1.0]})
    u = nflverse.uso_semanal(semanal, snaps, jug).set_index("semana")
    assert pd.isna(u.loc[1, "snaps_pct"])
    assert u.loc[1, "targets"] == 3
