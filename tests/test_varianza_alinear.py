import pandas as pd

from fantasy.decision.alineacion import optima
from fantasy.varianza import alinear


def _t():
    filas = [(1, "QB", 20), (2, "QB", 12), (3, "RB", 18), (4, "RB", 15), (5, "RB", 9),
             (6, "WR", 17), (7, "WR", 14), (8, "WR", 13), (9, "WR", 4), (10, "TE", 10),
             (11, "TE", 7)]
    return pd.DataFrame(filas, columns=["jugador_id", "pos", "esperado"]).assign(
        bloqueado=False, slot="BANCA")


def test_la_primera_es_la_optima_y_ninguna_se_aleja_mas_del_margen():
    t = _t()
    c = alinear.candidatas(t)
    assert c[0].ids() == optima(t).ids()
    assert all(x.esperado >= c[0].esperado - alinear.MARGEN for x in c)
    assert len({frozenset(x.ids()) for x in c}) == len(c)
    assert len(c) > 5
    assert all(len(x.slots) == 7 for x in c)


def test_bloqueados_quedan_fijos():
    t = _t()
    t.loc[t.jugador_id == 2, ["bloqueado", "slot"]] = [True, "QB"]  # QB malo ya jugando
    t.loc[t.jugador_id == 8, ["bloqueado", "slot"]] = [True, "BANCA"]  # en banca y ya jugó
    for x in alinear.candidatas(t):
        assert 2 in x.ids() and 1 not in x.ids() and 8 not in x.ids()


def test_elegir_exige_un_punto_porcentual():
    assert alinear.elegir([0.60, 0.605, 0.58]) == 0
    assert alinear.elegir([0.60, 0.62, 0.61]) == 1
