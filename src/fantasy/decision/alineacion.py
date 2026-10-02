"""Alineación óptima, regla de jugadores en duda y reemplazos condicionales."""

from dataclasses import dataclass

import pandas as pd

CUPOS = {"QB": 1, "RB": 2, "WR": 2, "TE": 1}
FLEX_POS = ("RB", "WR", "TE")
TITULARES = ("QB", "RB", "WR", "TE", "FLEX")
EN_DUDA = ("QUESTIONABLE", "DOUBTFUL", "DAY_TO_DAY")
UMBRAL_DUDA = 2.0


@dataclass(frozen=True)
class Alineacion:
    slots: tuple[tuple[str, int], ...]
    esperado: float

    def ids(self) -> set[int]:
        return {j for _, j in self.slots}


@dataclass(frozen=True)
class Reemplazo:
    slot: str
    titular: int
    suplente: int | None
    motivo: str | None = None  # sin suplente: "sin_posicion" | "horario" | "ocupado"


def _armar(elegidos: list[tuple[str, int]], t: pd.DataFrame) -> Alineacion:
    orden = {s: i for i, s in enumerate(TITULARES)}
    elegidos = sorted(elegidos, key=lambda x: orden[x[0]])
    esperado = float(t.set_index("jugador_id").loc[[j for _, j in elegidos], "esperado"].sum())
    return Alineacion(tuple((s, int(j)) for s, j in elegidos), esperado)


def optima(t: pd.DataFrame) -> Alineacion:
    """Exacta: con cupos por posición y un solo FLEX, llenar cada posición con sus mejores
    y el FLEX con el mejor sobrante es óptimo. Los bloqueados quedan donde están."""
    fijos = t[t.bloqueado & t.slot.isin(TITULARES)]
    libres = t[~t.bloqueado].sort_values("esperado", ascending=False, kind="stable")
    elegidos = [(s, int(j)) for s, j in zip(fijos.slot, fijos.jugador_id, strict=True)]
    usados = {j for _, j in elegidos}
    for pos, n in CUPOS.items():
        faltan = n - sum(1 for s, _ in elegidos if s == pos)
        cand = libres[(libres.pos == pos) & ~libres.jugador_id.isin(usados)].head(max(faltan, 0))
        for j in cand.jugador_id:
            elegidos.append((pos, int(j)))
            usados.add(int(j))
    if not any(s == "FLEX" for s, _ in elegidos):
        cand = libres[libres.pos.isin(FLEX_POS) & ~libres.jugador_id.isin(usados)].head(1)
        for j in cand.jugador_id:
            elegidos.append(("FLEX", int(j)))
    return _armar(elegidos, t)


def _posiciones(slot: str) -> tuple[str, ...]:
    return FLEX_POS if slot == "FLEX" else (slot,)


def aplicar_regla_duda(al: Alineacion, t: pd.DataFrame, umbral: float = UMBRAL_DUDA) -> Alineacion:
    idx = t.set_index("jugador_id")
    slots = list(al.slots)
    usados = al.ids()
    for i, (slot, j) in enumerate(slots):
        f = idx.loc[j]
        if f.bloqueado or f.lesion not in EN_DUDA:
            continue
        alt = t[~t.bloqueado & t.pos.isin(_posiciones(slot)) & (t.lesion == "ACTIVE")
                & ~t.jugador_id.isin(usados)]
        if alt.empty:
            continue
        mejor = alt.sort_values("proy", ascending=False, kind="stable").iloc[0]
        if f.proy - mejor.proy < umbral:
            slots[i] = (slot, int(mejor.jugador_id))
            usados = (usados - {j}) | {int(mejor.jugador_id)}
    return _armar(slots, t)


def reemplazos(al: Alineacion, t: pd.DataFrame) -> list[Reemplazo]:
    """Para cada titular movible, el mejor suplente que juega a la misma hora o después.
    Un suplente cubre a un solo titular; primero eligen los que juegan más tarde, que son
    los que tienen menos opciones."""
    idx = t.set_index("jugador_id")
    banca = t[~t.jugador_id.isin(al.ids()) & ~t.bloqueado & (t.proy > 0) & (t.p_jugar > 0)
              & t.inicio_utc.notna()]
    movibles = [(i, slot, j) for i, (slot, j) in enumerate(al.slots) if not idx.loc[j].bloqueado]
    nunca = pd.Timestamp.min.tz_localize("UTC")

    def inicio(j: int) -> pd.Timestamp:
        v = idx.loc[j].inicio_utc
        return v if pd.notna(v) else nunca

    movibles.sort(key=lambda x: inicio(x[2]), reverse=True)  # estable en empates
    usados: set[int] = set()
    elegidos: dict[int, Reemplazo] = {}
    for i, slot, j in movibles:
        f = idx.loc[j]
        de_su_pos = banca[banca.pos.isin(_posiciones(slot))]
        cand = de_su_pos[~de_su_pos.jugador_id.isin(usados)]
        if pd.notna(f.inicio_utc):
            cand = cand[cand.inicio_utc >= f.inicio_utc]
        mejor = cand.sort_values("esperado", ascending=False, kind="stable").head(1)
        suplente = int(mejor.jugador_id.iloc[0]) if len(mejor) else None
        motivo = None
        if suplente is None:
            a_tiempo = de_su_pos if pd.isna(f.inicio_utc) else                 de_su_pos[de_su_pos.inicio_utc >= f.inicio_utc]
            motivo = ("sin_posicion" if de_su_pos.empty
                      else "horario" if a_tiempo.empty else "ocupado")
        else:
            usados.add(suplente)
        elegidos[i] = Reemplazo(slot, int(j), suplente, motivo)
    return [elegidos[i] for i in sorted(elegidos)]
