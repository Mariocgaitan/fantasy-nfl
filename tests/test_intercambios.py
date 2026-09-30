import pathlib
import time

import pandas as pd
import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.decision import intercambios as it
from fantasy.decision.agencia_libre import tablas_por_semana
from fantasy.ingesta import espn

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"


def test_nombre():
    assert it.nombre(0) == pytest.approx(100.0)
    assert it.nombre(45) == pytest.approx(100 / 2.718281828, rel=1e-6)
    assert it.nombre(None) == it.nombre(200)


def _jug(filas):
    base = {"equipo_nfl_id": 1, "lesion": "ACTIVE", "dueno_pct": 50.0, "dueno_cambio": 0.0}
    return pd.DataFrame([{**base, **f} for f in filas])


def _tabla(jug, puntos):
    t = jug.copy()
    t["proy"] = t.jugador_id.map(puntos).fillna(0.0)
    t["p_jugar"] = 1.0
    t["esperado"] = t.proy
    t["inicio_utc"] = pd.Timestamp("2026-10-04 17:00", tz="UTC")
    t["slot"] = "BANCA"
    t["bloqueado"] = False
    return t


def _liga_chica():
    # Mario (5): 3 RB buenos + WR flojos. Rival (4): WR estrella, RB flojos.
    mio = [(1, "QB"), (2, "RB"), (3, "RB"), (4, "RB"), (5, "WR"), (6, "WR"), (7, "TE")]
    suyo = [(11, "QB"), (12, "RB"), (13, "RB"), (14, "WR"), (15, "WR"), (16, "TE")]
    filas = [{"jugador_id": j, "nombre": f"J{j}", "pos": p, "equipo_fantasy_id": 5,
              "disponibilidad": "EQUIPO"} for j, p in mio]
    filas += [{"jugador_id": j, "nombre": f"J{j}", "pos": p, "equipo_fantasy_id": 4,
               "disponibilidad": "EQUIPO"} for j, p in suyo]
    filas += [{"jugador_id": 21, "nombre": "LIBRE", "pos": "RB", "equipo_fantasy_id": 0,
               "disponibilidad": "LIBRE"}]
    jug = _jug(filas)
    puntos = {1: 20, 2: 18, 3: 16, 4: 15, 5: 9, 6: 8, 7: 10,
              11: 20, 12: 8, 13: 7, 14: 22, 15: 12, 16: 10, 21: 6}
    tablas = {w: _tabla(jug, puntos) for w in (4, 5)}
    plantillas = jug[jug.equipo_fantasy_id > 0].rename(columns={"equipo_fantasy_id": "equipo_id"})
    adp = {2: 10.0, 3: 30.0, 4: 50.0, 14: 20.0}
    return plantillas, jug, tablas, adp


def test_propone_rb_de_sobra_por_su_wr_estrella():
    plantillas, jug, tablas, adp = _liga_chica()
    props = it.buscar(plantillas, jug, tablas, 5, adp, None, tope=7)
    mejor = props[0]
    assert mejor.rival == 4 and 14 in mejor.recibes
    assert set(mejor.das) <= {2, 3, 4, 5, 6}
    assert mejor.ganancia > 0
    assert mejor.delta_rival >= -15 and mejor.delta_nombre >= -3
    assert mejor.riesgo_veto in {"bajo", "medio", "alto"}


def test_nunca_propone_al_rival_de_la_semana():
    plantillas, jug, tablas, adp = _liga_chica()
    assert it.buscar(plantillas, jug, tablas, 5, adp, rival_excluido=4, tope=7) == []


def test_riesgo_de_veto():
    assert it.riesgo_veto(0.30) == "alto"
    assert it.riesgo_veto(0.15) == "medio"
    assert it.riesgo_veto(-0.50) == "bajo"


def test_semana4_real_rapido_y_sin_norway():
    # Review Focus 1 y 5
    c = cargar(SEM4)
    liga = c["liga"]
    j = espn.parsear_jugadores(c["proyecciones"], liga, c["agentes_libres"])
    p = espn.parsear_plantillas(liga)
    tablas = tablas_por_semana(
        j, espn.parsear_proyecciones(c["proyecciones"], 2026),
        espn.parsear_calendario(c["calendario"]), p[p.equipo_id == 5].assign(bloqueado=False),
        4, pd.Timestamp("2026-09-30 01:40", tz="UTC"))
    inicio = time.perf_counter()
    props = it.buscar(p, j, tablas, 5, espn.parsear_adp(liga), espn.rival_de(liga, 5, 4))
    assert time.perf_counter() - inicio < 90
    assert 1 <= len(props) <= 5
    assert 7 not in {x.rival for x in props}
    assert len({x.rival for x in props}) == len(props)  # una por rival
    assert all(x.ganancia > 0 for x in props)
    assert [x.ganancia for x in props] == sorted((x.ganancia for x in props), reverse=True)


def test_recibir_mas_de_lo_que_das_dice_a_quien_soltar():
    # Revisión 1: 1 por 2 con la plantilla llena no puede dejarte en 15.
    plantillas, jug, tablas, adp = _liga_chica()
    props = it.buscar(plantillas, jug, tablas, 5, adp, None, tope=7, max_das=1)
    for x in props:
        extra = len(x.recibes) - len(x.das)
        assert len(x.sueltas) == max(extra, 0)
        assert not set(x.sueltas) & set(x.recibes)


def test_rival_con_pocos_jugadores_no_truena():
    # Review Focus 1
    plantillas, jug, tablas, adp = _liga_chica()
    chica = plantillas[~plantillas.jugador_id.isin([12, 13, 15, 16])]
    props = it.buscar(chica, jug, tablas, 5, adp, None, tope=7)
    assert all(x.rival == 4 for x in props)
