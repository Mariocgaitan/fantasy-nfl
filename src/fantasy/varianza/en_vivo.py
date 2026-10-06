"""La probabilidad de ganar en el reporte: rival real, partidos ya jugados, rol de 2026."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from fantasy.decision.agencia_libre import FUERA
from fantasy.decision.alineacion import TITULARES, Alineacion, optima
from fantasy.varianza import alinear, simular
from fantasy.varianza.grupos import asignar


def tabla_rival(t: pd.DataFrame, plantillas: pd.DataFrame, rival_id: int,
                ahora: pd.Timestamp) -> pd.DataFrame:
    pr = plantillas.loc[plantillas.equipo_id == rival_id, ["jugador_id", "slot", "bloqueado"]]
    tr = t.drop(columns=["slot", "bloqueado"], errors="ignore").merge(pr, on="jugador_id")
    empezo = tr.inicio_utc.notna() & (tr.inicio_utc <= ahora)
    tr["bloqueado"] = tr.bloqueado.astype(bool) & empezo
    return tr


def alineacion_rival(tr: pd.DataFrame) -> Alineacion:
    """Su alineación actual; si tiene un titular fuera, en descanso o un lugar vacío, la
    mejor por puntos esperados (lo razonable es que la arregle)."""
    tit = tr[tr.slot.isin(TITULARES)]
    incompleta = (len(tit) < len(TITULARES) + 2  # QB, RB×2, WR×2, TE, FLEX = 7
                  or tit.lesion.isin(FUERA).any()
                  or (tit.inicio_utc.isna() & ~tit.bloqueado.astype(bool)).any())
    if incompleta:
        return optima(tr)
    return Alineacion(tuple((s, int(j)) for s, j in zip(tit.slot, tit.jugador_id, strict=True)),
                      float(tit.esperado.sum()))


@dataclass
class Simulacion:
    puntos: np.ndarray
    col: dict[int, int]
    cols_rival: list[int]

    def p(self, al: Alineacion) -> float:
        return simular.p_ganar(self.puntos, [self.col[j] for j in al.ids()], self.cols_rival)

    def dispersion(self, j: int) -> float:
        return simular.dispersion(self.puntos, self.col[j])


def preparar(tm: pd.DataFrame, tr: pd.DataFrame, al_rival: Alineacion, reales: pd.DataFrame,
             rol_semana: pd.DataFrame, art, n: int = simular.N_SIM,
             semilla: int = 0) -> Simulacion:
    mios = [int(j) for j in tm.jugador_id]
    ids = mios + [j for j in al_rival.ids() if j not in set(mios)]
    f = pd.concat([tm, tr]).drop_duplicates("jugador_id").set_index("jugador_id").loc[ids]
    real = dict(zip(reales.jugador_id.astype(int), reales.puntos, strict=True))
    bloq = f.bloqueado.fillna(False).astype(bool).to_numpy()
    jug = pd.DataFrame({
        "jugador_id": ids, "pos": f.pos.to_numpy(), "proy": f.proy.to_numpy(float),
        "p_jugar": f.p_jugar.to_numpy(float), "equipo": f.equipo_nfl_id.to_numpy(),
        "real_fijo": [real.get(j, np.nan) if b else np.nan for j, b in zip(ids, bloq,
                                                                            strict=True)]})
    jug.loc[jug.real_fijo.notna(), "p_jugar"] = 1.0
    rasgos = rol_semana.drop(columns="pos").set_index("jugador_id").reindex(ids).fillna(0.0)
    jug["grupo"] = asignar(art.grupos, rasgos.reset_index(drop=True).assign(
        pos=jug.pos.to_numpy())).to_numpy()
    puntos = simular.simular(jug, art, n, semilla)
    col = {j: i for i, j in enumerate(ids)}
    return Simulacion(puntos, col, [col[j] for j in al_rival.ids()])


def elegir(sim: Simulacion, tm: pd.DataFrame) -> tuple[Alineacion, float]:
    cands = alinear.candidatas(tm)
    p = [sim.p(c) for c in cands]
    return cands[alinear.elegir(p)], p[0]


def explicar(elegida: Alineacion, opt: Alineacion, p_optima: float, sim: Simulacion,
             nombres: dict[int, str]) -> list[str]:
    entran = sorted(elegida.ids() - opt.ids())
    salen = sorted(opt.ids() - elegida.ids())
    lado = "arriba" if p_optima >= 0.5 else "abajo"
    lineas = []
    for e, s in zip(entran, salen, strict=False):
        busca = "estabilidad" if sim.dispersion(e) < sim.dispersion(s) else "techo"
        lineas.append(f"Entra {nombres[e]} por {nombres[s]}: vas {lado} y conviene {busca}.")
    return lineas
