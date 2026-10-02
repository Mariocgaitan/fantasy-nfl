import pandas as pd

from fantasy.decision import acciones as ac

T1 = pd.Timestamp("2026-10-04 17:00", tz="UTC")
T2 = pd.Timestamp("2026-10-05 00:20", tz="UTC")


def _vacio(**kw):
    base = {"cambios": [], "limite_cambios": None, "alineacion": [], "reemplazos": [], "pedidos": [],
                "lugares": [], "agencia": [], "intercambios": [], "rol": []}
    return ac.construir(**{**base, **kw})


def test_nada_que_hacer():
    assert _vacio() == []
    assert ac.contar([]) == {"urgente": 0, "recomendado": 0, "radar": 0}


def test_alineacion_no_optima_es_urgente_con_el_primer_partido():
    [a] = _vacio(cambios=["Entra X", "Sale Y"], limite_cambios=T1)
    assert (a.urgencia, a.tipo, a.limite) == ("urgente", "alineacion", T1)
    assert "Entra X" in a.texto and "Sale Y" in a.texto


def test_titular_en_duda_con_suplente_es_urgente():
    al = [{"slot": "WR", "nombre": "A", "pos": "WR", "lesion": "QUESTIONABLE",
           "estado": "en duda", "bloqueado": False, "inicio_utc": T2}]
    rem = [{"titular": "A", "suplente": "B", "motivo": None, "inicio_utc": T2}]
    [a] = _vacio(alineacion=al, reemplazos=rem)
    assert a.urgencia == "urgente" and a.limite == T2
    assert a.texto == "Si A queda fuera, mete a B"


def test_pedido_urgente_dice_a_quien_soltar():
    # Review Focus 1: plantilla llena → el texto incluye a quién soltar.
    ped = [{"titular": "A", "nombre": "N", "pos": "RB", "disponibilidad": "WAIVERS",
            "limite": T1, "soltar": "Z"}]
    [a] = _vacio(pedidos=ped)
    assert a.urgencia == "urgente" and a.limite == T1
    assert "Pide a N (RB)" in a.texto and "suelta a Z" in a.texto
    assert "waivers" in a.texto and "A no juega" in a.porque


def test_lugar_vacio_respaldo_y_moneda_son_recomendados():
    lug = [{"nombre": "D", "pos": "RB", "disponibilidad": "LIBRE", "motivo": "respaldo",
            "cubre": "Gibbs", "rival": "PUTI", "valor_rival": 27.0, "limite": None},
           {"nombre": "E", "pos": "WR", "disponibilidad": "WAIVERS", "motivo": "moneda",
            "cubre": None, "rival": "Norway", "valor_rival": 17.0, "limite": T1}]
    a, b = _vacio(lugares=lug)
    assert a.urgencia == b.urgencia == "recomendado"
    assert "sin soltar a nadie" in a.texto and "entra al instante" in a.texto
    assert "Gibbs no tiene quien lo cubra" in a.porque
    assert "Norway" in b.porque and "+17" in b.porque and b.limite == T1


def test_agencia_por_semana_separa_recomendado_y_radar():
    ag = [{"pedir": "Daniels", "pos": "QB", "soltar": "Young", "semanal": 0.6},
          {"pedir": "Love", "pos": "QB", "soltar": "Young", "semanal": 0.4},
          {"pedir": "Goedert", "pos": "TE", "soltar": "Johnson", "semanal": 1.2}]
    acc = _vacio(agencia=ag)
    rec = [a for a in acc if a.urgencia == "recomendado"]
    radar = [a for a in acc if a.urgencia == "radar"]
    assert [a.texto for a in rec] == ["Pide a Goedert (TE), suelta a Johnson"]
    assert len(radar) == 1 and "Daniels" in radar[0].texto and "+0.6" in radar[0].texto


def test_intercambios_recomendados_y_rol_en_radar():
    x = [{"rival": "Smashers", "das": ["A", "B"], "recibes": ["C"], "semanal": 2.1,
          "riesgo": "medio"}]
    rol = [{"nombre": "W", "pos": "RB", "dueno": "Smashers"}, {"nombre": "L", "pos": "WR",
                                                              "dueno": ""}]
    acc = _vacio(intercambios=x, rol=rol)
    assert acc[0].urgencia == "recomendado" and "Propón a Smashers" in acc[0].texto
    assert "veto medio" in acc[0].porque
    radar = [a.texto for a in acc if a.urgencia == "radar"]
    assert any("banca de Smashers" in t for t in radar)
    assert any("está libre" in t for t in radar)


def test_orden_urgentes_por_hora():
    al = [{"slot": "WR", "nombre": "A", "pos": "WR", "lesion": "DOUBTFUL", "estado": "dudoso",
           "bloqueado": False, "inicio_utc": T2}]
    rem = [{"titular": "A", "suplente": "B", "motivo": None, "inicio_utc": T2}]
    acc = _vacio(cambios=["Entra X"], limite_cambios=T1, alineacion=al, reemplazos=rem)
    assert [a.limite for a in acc] == [T1, T2]
    assert ac.contar(acc) == {"urgente": 2, "recomendado": 0, "radar": 0}


def test_pedido_urgente_dice_que_lo_metas_de_titular():
    ped = [{"titular": "A", "nombre": "N", "pos": "RB", "disponibilidad": "LIBRE",
            "limite": T1, "soltar": None}]
    [a] = _vacio(pedidos=ped)
    assert "mételo de titular por A" in a.texto
