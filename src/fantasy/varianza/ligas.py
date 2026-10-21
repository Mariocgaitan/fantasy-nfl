"""Ligas simuladas para comparar dos formas de alinear con los puntos reales de una temporada:
por puntos esperados (`optima`) o por probabilidad de ganar."""

import numpy as np
import pandas as pd

from fantasy.decision.alineacion import optima
from fantasy.varianza import alinear, simular
from fantasy.varianza.grupos import asignar

EQUIPOS = 8
RONDAS = 14
RUIDO = 0.15
POOL = 200
TOPE = {"QB": 3, "RB": 6, "WR": 6, "TE": 3}
MINIMOS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}


def draft(valores: pd.DataFrame, rng: np.random.Generator) -> list[list[int]]:
    v = valores.assign(valor=valores.valor * (1 + rng.normal(0, RUIDO, len(valores))))
    v = v.sort_values("valor", ascending=False)
    disponibles = list(zip(v.jugador_id.astype(int), v.pos, strict=True))
    equipos = [[] for _ in range(EQUIPOS)]
    conteo = [dict.fromkeys(TOPE, 0) for _ in range(EQUIPOS)]
    for r in range(RONDAS):
        orden = range(EQUIPOS) if r % 2 == 0 else range(EQUIPOS - 1, -1, -1)
        for e in orden:
            faltan = {p: max(MINIMOS[p] - conteo[e][p], 0) for p in TOPE}
            obligado = sum(faltan.values()) >= RONDAS - r
            for i, (j, p) in enumerate(disponibles):
                if conteo[e][p] >= TOPE[p] or (obligado and faltan[p] == 0):
                    continue
                equipos[e].append(j)
                conteo[e][p] += 1
                disponibles.pop(i)
                break
    return equipos


def _tabla_equipo(jug: pd.DataFrame, ids: list[int]) -> pd.DataFrame:
    return jug[jug.jugador_id.isin(ids)].assign(bloqueado=False, slot="BANCA")


def _resultado(real, col, al, pts_rival) -> float:
    x = real[[col[j] for j in al.ids()]].sum()
    return 1.0 if x > pts_rival else 0.5 if x == pts_rival else 0.0


def temporada(t: pd.DataFrame, art, *, n_ligas: int = 200, semanas=range(3, 18),
              n_sim: int = simular.N_SIM, semilla: int = 0,
              margen: float = alinear.MARGEN) -> pd.DataFrame:
    rng = np.random.default_rng(semilla)
    t = t.assign(grupo=asignar(art.grupos, t))
    valores = (t[t.semana == 1].nlargest(POOL, "proy_espn")[["jugador_id", "pos", "proy_espn"]]
               .rename(columns={"proy_espn": "valor"}))
    pos = valores.set_index("jugador_id").pos
    por_semana = {w: t[t.semana == w].drop_duplicates("jugador_id").set_index("jugador_id")
                  for w in semanas}
    filas = []
    for liga in range(n_ligas):
        equipos = draft(valores, rng)
        todos = [j for e in equipos for j in e]
        for w in semanas:
            s = por_semana[w].reindex(todos)
            jug = pd.DataFrame({
                "jugador_id": todos, "pos": pos.loc[todos].to_numpy(),
                "proy": s.proy_espn.fillna(0.0).to_numpy(), "p_jugar": 1.0,
                "grupo": s.grupo.fillna(0).astype(int).to_numpy(),
                "equipo": s.equipo.to_numpy(), "real_fijo": np.nan,
                "real": s.real.fillna(0.0).to_numpy()})
            jug["esperado"] = jug.proy
            pts = simular.simular(jug, art, n_sim, semilla=int(rng.integers(2**31)))
            col = {j: i for i, j in enumerate(todos)}
            real = jug.real.to_numpy()
            optimas = [optima(_tabla_equipo(jug, e)) for e in equipos]
            orden = rng.permutation(EQUIPOS)
            for a, b in zip(orden[::2], orden[1::2], strict=True):
                for yo, rival in ((a, b), (b, a)):
                    cols_r = [col[j] for j in optimas[rival].ids()]
                    pts_rival = real[cols_r].sum()
                    cands = alinear.candidatas(_tabla_equipo(jug, equipos[yo]), margen)
                    p = [simular.p_ganar(pts, [col[j] for j in c.ids()], cols_r) for c in cands]
                    i = alinear.elegir(p)
                    filas.append({"liga": liga, "semana": w, "equipo": int(yo), "p": p[i],
                                  "p_optima": p[0],
                                  "gana_pg": _resultado(real, col, cands[i], pts_rival),
                                  "gana_esp": _resultado(real, col, cands[0], pts_rival),
                                  "cambia": i != 0})
    return pd.DataFrame(filas)
