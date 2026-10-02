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
           solo_respaldo=False, waiver=None, desde=None, usados=frozenset(),
           top=TOP_CANDIDATOS) -> list[Eleccion]:
    """`desde`: para un titular que ya se sabe que no juega, sirve cualquiera cuyo partido
    empiece después de `desde` (no hace falta que juegue después del titular).
    `usados`: jugadores ya elegidos en otra acción, que no se repiten."""
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
    usados = set(usados)
    elegidos: list[Eleccion] = []
    for _ in range(n_lugares):
        e = _respaldo(sanos, t0, valores, pendientes, usados, waiver, desde)
        if e is None and not solo_respaldo:
            e = _moneda(sanos, valores, usados)
        if e is None:
            break
        elegidos.append(e)
        usados.add(e.jugador_id)
        pendientes = [(s, t) for s, t in pendientes if t != e.cubre]
    return elegidos


def _respaldo(sanos, t0, valores, pendientes, usados, waiver, desde):
    opciones = []
    for slot, titular in pendientes:
        inicio = t0.inicio_utc.get(titular)
        if desde is None and (inicio is None or pd.isna(inicio)):
            continue  # descansa esta semana: no hay a quién cubrir
        for f in sanos.itertuples():
            j = int(f.jugador_id)
            if j in usados or f.pos not in _posiciones(slot):
                continue
            ini = t0.inicio_utc.get(j)
            if ini is None or pd.isna(ini) or t0.proy.get(j, 0.0) <= 0:
                continue
            # Cubrir por si acaso: juega a la misma hora o después que el titular.
            # Reemplazar a uno que ya no juega: basta con que su partido no haya empezado.
            llega = ini > desde if desde is not None else ini >= inicio
            if not llega:
                continue
            # Un pedido en waivers solo sirve si se procesa antes de que haga falta.
            hace_falta = ini if desde is not None else inicio
            if waiver is not None and f.disponibilidad == "WAIVERS" and not waiver < hace_falta:
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


@dataclass(frozen=True)
class Pedido:
    jugador_id: int
    titular: int              # el titular que no juega
    soltar: int | None        # a quién soltar si la plantilla está llena
    limite: pd.Timestamp      # UTC: waivers o inicio del partido del que entra


def soltables(mis_ids, *, titulares, en_ir, intocables, bloqueados, resto) -> list[int]:
    """A quién se puede soltar, del que menos aporta de aquí al final al que más. Soltar a
    uno del IR no libera lugar, así que no cuenta."""
    banca = [j for j in mis_ids
             if j not in titulares | en_ir | intocables | bloqueados]
    return sorted(banca, key=lambda j: (resto.get(j, 0.0), j))


def planear(jugadores, tablas, plantillas, equipo_id, semana, *, fuera, sin_respaldo,
            lugares_libres, soltables, ahora, waiver) -> tuple[list[Pedido], list[Eleccion]]:
    """Primero, un reemplazo por cada titular que no juega (urgente); con los lugares que
    sobren, respaldo o moneda de cambio. Nadie se repite y cada pedido tiene su lugar."""
    t0 = tablas[semana].set_index("jugador_id")
    usados: set[int] = set()
    pedidos: list[Pedido] = []
    libres = lugares_libres
    por_soltar = list(soltables)
    for slot, titular in fuera:
        if libres == 0 and not por_soltar:
            break  # no hay lugar ni a quién soltar: el pedido sería imposible
        es = elegir(jugadores, tablas, plantillas, equipo_id, semana, [(slot, titular)], 1,
                    solo_respaldo=True, waiver=waiver, desde=ahora, usados=usados)
        if not es:
            continue
        j = es[0].jugador_id
        soltar = None
        if libres > 0:
            libres -= 1
        else:
            soltar = por_soltar.pop(0)
        disp = jugadores.loc[jugadores.jugador_id == j, "disponibilidad"].iloc[0]
        limite = waiver if disp == "WAIVERS" and waiver is not None else t0.inicio_utc[j]
        pedidos.append(Pedido(j, int(titular), soltar, limite))
        usados.add(j)
    no_juegan = {t for _, t in fuera}
    pendientes = [(s, t) for s, t in sin_respaldo if t not in no_juegan]
    lugares = elegir(jugadores, tablas, plantillas, equipo_id, semana, pendientes, libres,
                     waiver=waiver, usados=usados)
    return pedidos, lugares
