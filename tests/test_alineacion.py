import itertools
import json

import pandas as pd
import pytest

from fantasy.decision.alineacion import (
    CUPOS,
    FLEX_POS,
    aplicar_regla_duda,
    optima,
    reemplazos,
)
from fantasy.ingesta import espn
from fantasy.proyeccion.espn import tabla_semana


@pytest.fixture
def semana3(fixture_dir):
    c = {n: json.loads((fixture_dir / f"{n}.json").read_text(encoding="utf-8"))
         for n in ("liga", "calendario", "agentes_libres", "proyecciones")}
    j = espn.parsear_jugadores(c["proyecciones"], c["liga"], c["agentes_libres"])
    t = tabla_semana(j, espn.parsear_proyecciones(c["proyecciones"], 2026),
                     espn.parsear_calendario(c["calendario"]), 3, con_lesion=True)
    p = espn.parsear_plantillas(c["liga"])
    mia = p[p.equipo_id == 5][["jugador_id", "slot", "bloqueado"]]
    return t.merge(mia, on="jugador_id")


def nombres(t, ids):
    return set(t.set_index("jugador_id").loc[list(ids), "nombre"])


def test_optima_semana3_coincide_con_la_alineacion_de_mario(semana3):
    al = optima(semana3)
    actuales = semana3[semana3.slot.isin(["QB", "RB", "WR", "TE", "FLEX"])].jugador_id
    assert al.ids() == set(actuales)
    assert nombres(semana3, al.ids()) == {
        "Tyler Shough", "Jahmyr Gibbs", "Ashton Jeanty", "Parker Washington",
        "Christian Watson", "Trey McBride", "James Cook III"}
    assert [s for s, _ in al.slots] == ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"]


def test_bloqueado_en_la_banca_no_entra(semana3):
    # Review Focus 3: Golden jugó el jueves desde la banca y ya no se puede mover.
    t = semana3.copy()
    t.loc[t.nombre == "Matthew Golden", "proy"] = 40.0
    t.loc[t.nombre == "Matthew Golden", "esperado"] = 40.0
    assert "Matthew Golden" not in nombres(t, optima(t).ids())


def test_bloqueado_en_flex_se_queda_en_flex():
    t = pd.DataFrame({
        "jugador_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "nombre": list("ABCDEFGH"),
        "pos": ["QB", "RB", "RB", "WR", "WR", "TE", "WR", "RB"],
        "esperado": [20, 15, 14, 13, 12, 10, 5, 30.0],
        "slot": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "BANCA"],
        "bloqueado": [False] * 6 + [True, False],
    })
    al = optima(t)
    assert ("FLEX", 7) in al.slots
    assert 8 in al.ids()  # el RB de 30 desplaza al RB de 14
    assert 3 not in al.ids()


def test_optima_es_exacta_contra_enumeracion(semana3):
    t = semana3[~semana3.bloqueado].reset_index(drop=True)
    mejor = 0.0
    por_pos = {p: t[t.pos == p] for p in CUPOS}
    for qb in itertools.combinations(por_pos["QB"].jugador_id, 1):
        for rb in itertools.combinations(por_pos["RB"].jugador_id, 2):
            for wr in itertools.combinations(por_pos["WR"].jugador_id, 2):
                for te in itertools.combinations(por_pos["TE"].jugador_id, 1):
                    usados = set(qb + rb + wr + te)
                    resto = t[t.pos.isin(FLEX_POS) & ~t.jugador_id.isin(usados)]
                    flex = resto.esperado.max() if len(resto) else 0.0
                    total = t[t.jugador_id.isin(usados)].esperado.sum() + flex
                    mejor = max(mejor, total)
    assert optima(t).esperado == pytest.approx(mejor)


def test_regla_duda_prefiere_al_sano_si_la_diferencia_es_chica():
    # El RB de 12 se queda con el FLEX; la pelea es entre el WR en duda (5) y el WR sano (8).
    t = pd.DataFrame({
        "jugador_id": [1, 2, 3, 4, 5, 6, 7, 8],
        "nombre": list("ABCDEFGH"),
        "pos": ["QB", "RB", "RB", "WR", "WR", "TE", "RB", "WR"],
        "proy": [20, 15, 14, 13, 5.0, 10, 12, 3.5],
        "lesion": ["ACTIVE"] * 4 + ["QUESTIONABLE", "ACTIVE", "ACTIVE", "ACTIVE"],
        "slot": ["BANCA"] * 8, "bloqueado": [False] * 8,
    })
    t["p_jugar"] = t.lesion.map({"ACTIVE": 1.0, "QUESTIONABLE": 0.75})
    t["esperado"] = t.proy * t.p_jugar
    al = optima(t)
    assert 5 in al.ids()  # 3.75 esperado le gana a 3.5
    al2 = aplicar_regla_duda(al, t)
    assert 5 not in al2.ids() and 8 in al2.ids()  # 5.0 - 3.5 < 2.0


def test_reemplazos_respetan_horarios(semana3):
    al = optima(semana3)
    idx = semana3.set_index("jugador_id")
    r = {idx.loc[x.titular, "nombre"]: (idx.loc[x.suplente, "nombre"] if x.suplente else None)
         for x in reemplazos(al, semana3)}
    assert r["Tyler Shough"] is None        # ningún QB útil juega a la par o después
    assert r["Trey McBride"] is None        # no hay TE en la banca
    assert r["Jahmyr Gibbs"] == "Breece Hall"
    assert r["Ashton Jeanty"] == "D'Andre Swift"  # Hall juega antes que Jeanty
    assert r["Parker Washington"] == "Malik Nabers"
    assert r["James Cook III"] == "Jalen Coker"  # Hall ya cubre a Gibbs: nadie se repite
    assert "Christian Watson" not in r      # ya está bloqueado
    suplentes = [s for s in r.values() if s]
    assert len(suplentes) == len(set(suplentes))


def test_reemplazos_dicen_por_que_no_hay_suplente():
    import pandas as pd

    from fantasy.decision.alineacion import optima, reemplazos
    temprano = pd.Timestamp("2026-10-04 17:00", tz="UTC")
    tarde = pd.Timestamp("2026-10-05 00:20", tz="UTC")
    filas = [  # jugador_id, pos, esperado, inicio
        (1, "QB", 20, temprano), (2, "RB", 18, tarde), (3, "RB", 15, temprano),
        (4, "WR", 16, tarde), (5, "WR", 14, temprano), (6, "TE", 10, temprano),
        (7, "WR", 13, temprano), (8, "WR", 9, temprano),
    ]
    t = pd.DataFrame([{"jugador_id": j, "nombre": f"J{j}", "pos": p, "proy": e, "esperado": e,
                       "p_jugar": 1.0, "inicio_utc": i, "slot": "BANCA", "bloqueado": False,
                       "lesion": "ACTIVE"} for j, p, e, i in filas])
    al = optima(t)
    motivo = {r.titular: r.motivo for r in reemplazos(al, t)}
    assert motivo[2] == "sin_posicion"   # no hay RB en la banca
    assert motivo[4] == "horario"        # los WR de la banca juegan antes
    assert motivo[1] == "sin_posicion"   # no hay QB en la banca
