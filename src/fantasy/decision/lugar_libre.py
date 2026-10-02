"""Qué pedir con un lugar vacío (o con un titular fuera): respaldo si a un titular nadie lo
cubre; si no, moneda de cambio (el libre que más mejora las alineaciones de los rivales)."""

from dataclasses import dataclass

import pandas as pd

from fantasy.decision.agencia_libre import Valuador
from fantasy.decision.alineacion import FLEX_POS

TOP_CANDIDATOS = 40


@dataclass(frozen=True)
class Eleccion:
    jugador_id: int
    motivo: str               # "respaldo" | "moneda"
    cubre: int | None         # titular al que respalda (solo "respaldo")
    rival: int | None         # equipo al que más le sirve
    valor_rival: float        # mejora de la alineación de ese rival, de aquí al final


def _posiciones(slot: str) -> tuple[str, ...]:
    return FLEX_POS if slot == "FLEX" else (slot,)


def _valor_para_rivales(cands, plantillas, equipo_id, valuador):
    """jugador → (suma de mejoras positivas, rival con la mayor, esa mejora)."""
    equipos = {int(e): set(g.jugador_id) for e, g in plantillas.groupby("equipo_id")
               if int(e) != equipo_id}
    base = {e: valuador.valor(s) for e, s in equipos.items()}
    out = {}
    for j in cands:
        mejoras = {e: valuador.valor(s | {j}) - base[e] for e, s in equipos.items()}
        rival = max(mejoras, key=mejoras.get) if mejoras else None
        out[j] = (sum(max(v, 0.0) for v in mejoras.values()), rival,
                  max(mejoras.values(), default=0.0))
    return out


def elegir(jugadores, tablas, plantillas, equipo_id, semana, sin_respaldo, n_lugares, *,
           solo_respaldo=False, waiver=None, top=TOP_CANDIDATOS) -> list[Eleccion]:
    if n_lugares <= 0:
        return []
    resto = pd.concat(tablas.values()).groupby("jugador_id")["proy"].sum()
    t0 = tablas[semana].set_index("jugador_id")
    sanos = jugadores[jugadores.disponibilidad.isin(["LIBRE", "WAIVERS"])
                      & (jugadores.lesion == "ACTIVE")]
    sanos = (sanos.assign(r=sanos.jugador_id.map(resto).fillna(0.0))
             .sort_values("r", ascending=False, kind="stable").head(top))
    valores = _valor_para_rivales([int(j) for j in sanos.jugador_id], plantillas, equipo_id,
                                  Valuador(tablas))
    pendientes = list(sin_respaldo)
    usados: set[int] = set()
    elegidos: list[Eleccion] = []
    for _ in range(n_lugares):
        e = _respaldo(sanos, t0, valores, pendientes, usados, waiver)
        if e is None and not solo_respaldo:
            e = _moneda(sanos, valores, usados)
        if e is None:
            break
        elegidos.append(e)
        usados.add(e.jugador_id)
        pendientes = [(s, t) for s, t in pendientes if t != e.cubre]
    return elegidos


def _respaldo(sanos, t0, valores, pendientes, usados, waiver):
    opciones = []
    for slot, titular in pendientes:
        inicio = t0.inicio_utc.get(titular)
        if inicio is None or pd.isna(inicio):
            continue  # descansa esta semana: no hay a quién cubrir
        for f in sanos.itertuples():
            j = int(f.jugador_id)
            if j in usados or f.pos not in _posiciones(slot):
                continue
            ini = t0.inicio_utc.get(j)
            if ini is None or pd.isna(ini) or ini < inicio or t0.proy.get(j, 0.0) <= 0:
                continue
            if waiver is not None and f.disponibilidad == "WAIVERS" and not waiver < inicio:
                continue
            suma, rival, mejora = valores[j]
            opciones.append(((f.r, suma), Eleccion(j, "respaldo", int(titular), rival, mejora)))
    if not opciones:
        return None
    return max(opciones, key=lambda x: x[0])[1]


def _moneda(sanos, valores, usados):
    cands = [(valores[int(j)][0], int(j)) for j in sanos.jugador_id
             if int(j) not in usados and valores[int(j)][0] > 0]
    if not cands:
        return None
    _, j = max(cands)
    _, rival, mejora = valores[j]
    return Eleccion(j, "moneda", None, rival, mejora)
