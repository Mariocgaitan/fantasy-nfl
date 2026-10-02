import pandas as pd

from fantasy.decision import lugar_libre as ll

TEMPRANO = pd.Timestamp("2026-10-04 17:00", tz="UTC")
TARDE = pd.Timestamp("2026-10-05 00:20", tz="UTC")


def _caso(libres, rival_flojo_en="RB"):
    """Mario (5): QB 1, RB 2-3, WR 4-5, TE 6. Rival (3): flojo en `rival_flojo_en`.
    `libres`: [(id, pos, puntos por semana, inicio, disponibilidad)]."""
    mios = [(1, "QB", 20), (2, "RB", 18), (3, "RB", 15), (4, "WR", 16), (5, "WR", 14),
            (6, "TE", 10)]
    suyos = [(11, "QB", 20), (12, "RB", 3 if rival_flojo_en == "RB" else 15),
             (13, "RB", 14), (14, "WR", 15), (15, "WR", 3 if rival_flojo_en == "WR" else 14),
             (16, "TE", 9), (17, "TE", 8)]  # 17 ocupa el FLEX del rival
    filas = [{"jugador_id": j, "pos": p, "pts": x, "inicio": TEMPRANO, "equipo_fantasy_id": 5,
                  "disponibilidad": "EQUIPO"} for j, p, x in mios]
    filas[1]["inicio"] = TARDE  # el RB titular 2 juega tarde
    filas += [{"jugador_id": j, "pos": p, "pts": x, "inicio": TEMPRANO, "equipo_fantasy_id": 3,
                   "disponibilidad": "EQUIPO"} for j, p, x in suyos]
    filas += [{"jugador_id": j, "pos": p, "pts": x, "inicio": i, "equipo_fantasy_id": 0,
                   "disponibilidad": d} for j, p, x, i, d in libres]
    jug = pd.DataFrame([{"jugador_id": f["jugador_id"], "nombre": f"J{f['jugador_id']}",
                         "pos": f["pos"], "equipo_nfl_id": 1, "lesion": "ACTIVE",
                         "equipo_fantasy_id": f["equipo_fantasy_id"],
                         "disponibilidad": f["disponibilidad"], "dueno_pct": 1.0,
                         "dueno_cambio": 0.0} for f in filas])
    tablas = {}
    for w in (4, 5):
        t = jug.copy()
        t["proy"] = [f["pts"] for f in filas]
        t["p_jugar"] = 1.0
        t["esperado"] = t.proy
        t["inicio_utc"] = [f["inicio"] for f in filas]
        t["slot"] = "BANCA"
        t["bloqueado"] = False
        tablas[w] = t
    plantillas = jug[jug.equipo_fantasy_id > 0].rename(
        columns={"equipo_fantasy_id": "equipo_id"})[["equipo_id", "jugador_id"]]
    return jug, tablas, plantillas


def test_respaldo_primero_si_un_titular_no_tiene_quien_lo_cubra():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE"), (22, "WR", 12, TEMPRANO, "LIBRE")])
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1)
    assert (e.jugador_id, e.motivo, e.cubre) == (21, "respaldo", 2)


def test_respaldo_debe_jugar_a_la_misma_hora_o_despues():
    # El único RB libre juega antes que el titular: no lo cubre → moneda de cambio.
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE")])
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1)
    assert e.motivo == "moneda" and e.jugador_id == 21 and e.rival == 3


def test_sin_faltantes_elige_moneda_de_cambio_por_valor_para_rivales():
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE"), (22, "WR", 12, TEMPRANO, "LIBRE")],
                            rival_flojo_en="RB")
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [], 1)
    assert (e.jugador_id, e.motivo, e.rival) == (21, "moneda", 3)
    assert e.valor_rival > 0


def test_dos_lugares_no_repiten_jugador():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE"), (22, "RB", 8, TARDE, "LIBRE")])
    elegidos = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 2)
    assert len({e.jugador_id for e in elegidos}) == 2
    assert elegidos[0].motivo == "respaldo"


def test_nadie_sirve_no_devuelve_nada():
    # Review Focus 3: ningún libre ayuda a nadie → lista vacía, no "Pide a None".
    jug, tablas, pl = _caso([])
    assert ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1) == []


def test_solo_respaldo_no_cae_a_moneda():
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE")])
    assert ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1, solo_respaldo=True) == []


def test_waiver_que_llega_tarde_no_sirve_para_un_urgente():
    # Review Focus 5: el de waivers se procesa después del partido → se elige el LIBRE.
    jug, tablas, pl = _caso([(21, "RB", 12, TARDE, "WAIVERS"), (22, "RB", 7, TARDE, "LIBRE")])
    despues = TARDE + pd.Timedelta(hours=1)
    [e] = ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1, solo_respaldo=True, waiver=despues)
    assert e.jugador_id == 22


def test_titular_que_descansa_no_pide_respaldo():
    # Review Focus 2: titular sin partido esta semana (NaT) se ignora.
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE")])
    for t in tablas.values():
        t.loc[t.jugador_id == 2, "inicio_utc"] = pd.NaT
    assert ll.elegir(jug, tablas, pl, 5, 4, [("RB", 2)], 1, solo_respaldo=True) == []


AHORA = TEMPRANO - pd.Timedelta(days=2)


def test_planear_plantilla_llena_suelta_al_primero_soltable():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE")])
    pedidos, lugares = ll.planear(jug, tablas, pl, 5, 4, fuera=[("RB", 2)], sin_respaldo=[],
                                  lugares_libres=0, soltables=[6], ahora=AHORA, waiver=None)
    assert [(p.jugador_id, p.titular, p.soltar) for p in pedidos] == [(21, 2, 6)]
    assert lugares == []


def test_planear_dos_titulares_fuera_no_repite_y_cuenta_lugares():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE"), (22, "RB", 8, TARDE, "LIBRE")])
    pedidos, _ = ll.planear(jug, tablas, pl, 5, 4, fuera=[("RB", 2), ("RB", 3)],
                            sin_respaldo=[], lugares_libres=1, soltables=[6],
                            ahora=AHORA, waiver=None)
    assert len({p.jugador_id for p in pedidos}) == 2
    assert [p.soltar for p in pedidos] == [None, 6]


def test_planear_lleno_sin_soltables_no_pide():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE")])
    pedidos, _ = ll.planear(jug, tablas, pl, 5, 4, fuera=[("RB", 2)], sin_respaldo=[],
                            lugares_libres=0, soltables=[], ahora=AHORA, waiver=None)
    assert pedidos == []


def test_planear_titular_fuera_acepta_libre_que_juega_antes_que_el():
    # Si ya se sabe que no juega, cualquiera que aún no haya jugado es mejor que 0.
    jug, tablas, pl = _caso([(21, "RB", 9, TEMPRANO, "LIBRE")])
    pedidos, _ = ll.planear(jug, tablas, pl, 5, 4, fuera=[("RB", 2)], sin_respaldo=[],
                            lugares_libres=1, soltables=[], ahora=AHORA, waiver=None)
    assert [(p.jugador_id, p.limite) for p in pedidos] == [(21, TEMPRANO)]


def test_planear_lugares_no_repiten_al_pedido_ni_cubren_al_que_no_juega():
    jug, tablas, pl = _caso([(21, "RB", 9, TARDE, "LIBRE"), (22, "RB", 8, TARDE, "LIBRE")])
    pedidos, lugares = ll.planear(jug, tablas, pl, 5, 4, fuera=[("RB", 2)],
                                  sin_respaldo=[("RB", 2)], lugares_libres=2, soltables=[],
                                  ahora=AHORA, waiver=None)
    assert {p.jugador_id for p in pedidos}.isdisjoint({e.jugador_id for e in lugares})
    assert all(e.cubre != 2 for e in lugares)


def test_lugar_respaldo_en_waivers_debe_llegar_antes_del_partido():
    jug, tablas, pl = _caso([(21, "RB", 12, TARDE, "WAIVERS"), (22, "RB", 7, TARDE, "LIBRE")])
    _, lugares = ll.planear(jug, tablas, pl, 5, 4, fuera=[], sin_respaldo=[("RB", 2)],
                            lugares_libres=1, soltables=[], ahora=AHORA,
                            waiver=TARDE + pd.Timedelta(hours=1))
    assert lugares[0].jugador_id == 22 and lugares[0].motivo == "respaldo"


def test_soltables_excluye_ir_intocables_bloqueados_y_titulares():
    resto = {10: 5.0, 11: 1.0, 12: 0.0, 13: 2.0, 14: 3.0}
    assert ll.soltables({1, 10, 11, 12, 13, 14}, titulares={1}, en_ir={12}, intocables={13},
                        bloqueados={14}, resto=resto) == [11, 10]
