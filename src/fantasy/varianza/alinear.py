"""Alineaciones cercanas a la óptima por puntos esperados y elección por P(ganar)."""

import itertools

import pandas as pd

from fantasy.decision.alineacion import CUPOS, FLEX_POS, TITULARES, Alineacion, optima

MARGEN = 10.0  # nunca más de 10 puntos esperados por debajo de la óptima
UMBRAL = 0.01  # cambiar solo por al menos 1 punto porcentual de P(ganar)
_ORDEN = {s: i for i, s in enumerate(TITULARES)}


def _alineacion(elegidos: list[tuple[str, int]], esp: dict[int, float]) -> Alineacion:
    slots = tuple(sorted(elegidos, key=lambda x: _ORDEN[x[0]]))
    return Alineacion(slots, float(sum(esp[j] for _, j in slots)))


def candidatas(t: pd.DataFrame, margen: float = MARGEN) -> list[Alineacion]:
    mejor = optima(t)
    esp = dict(zip(t.jugador_id.astype(int), t.esperado.astype(float), strict=True))
    fijos_df = t[t.bloqueado & t.slot.isin(TITULARES)]
    fijos = [(s, int(j)) for s, j in zip(fijos_df.slot, fijos_df.jugador_id, strict=True)]
    libres = t[~t.bloqueado]
    por_pos = {p: [int(j) for j in libres.loc[libres.pos == p, "jugador_id"]] for p in CUPOS}
    faltan = {p: max(n - sum(1 for s, _ in fijos if s == p), 0) for p, n in CUPOS.items()}
    falta_flex = not any(s == "FLEX" for s, _ in fijos)
    salida, vistos = [mejor], {frozenset(mejor.ids())}
    for eleccion in itertools.product(*(itertools.combinations(por_pos[p], faltan[p])
                                        for p in CUPOS)):
        base = fijos + [(p, j) for p, js in zip(CUPOS, eleccion, strict=True) for j in js]
        usados = {j for _, j in base}
        flex = ([j for p in FLEX_POS for j in por_pos[p] if j not in usados]
                if falta_flex else [None])
        for fx in flex:
            el = base + ([("FLEX", fx)] if fx is not None else [])
            clave = frozenset(j for _, j in el)
            if clave in vistos:
                continue
            al = _alineacion(el, esp)
            if al.esperado >= mejor.esperado - margen:
                vistos.add(clave)
                salida.append(al)
    return salida


def elegir(p: list[float], umbral: float = UMBRAL) -> int:
    i = max(range(len(p)), key=lambda k: p[k])
    return i if p[i] - p[0] >= umbral else 0
