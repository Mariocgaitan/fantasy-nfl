"""Intercambios: qué dar y qué pedir a cada rival para ganar según ESPN, y que acepten."""

import itertools
import math
from dataclasses import dataclass

import pandas as pd

from fantasy.decision.agencia_libre import Valuador

MIN_DELTA_RIVAL = -15.0
MIN_DELTA_NOMBRE = -3.0


@dataclass(frozen=True)
class Propuesta:
    rival: int
    das: tuple[int, ...]
    recibes: tuple[int, ...]
    relleno: tuple[int, ...]   # agentes libres que pedirías con los lugares que quedan
    sueltas: tuple[int, ...]   # a quién soltar si recibes más de lo que das
    ganancia: float
    delta_rival: float
    delta_nombre: float
    desbalance: float
    riesgo_veto: str


def nombre(adp: float | None) -> float:
    return 100.0 * math.exp(-(adp if adp is not None else 200.0) / 45.0)


def riesgo_veto(desbalance: float) -> str:
    # Cortes sin validar: el único dato real (Hall + Swift + Collins por Amon-Ra, 0.11) no se vetó.
    if desbalance > 0.40:
        return "alto"
    if desbalance > 0.15:
        return "medio"
    return "bajo"


def sobre_libre(ids, resto, pos, reemplazo) -> float:
    """Puntos de aquí al final por encima del mejor libre sano de su posición: lo que rinde
    igual que un libre no vale nada en un intercambio, cualquiera lo pide gratis."""
    return float(sum(max(resto.get(i, 0.0) - reemplazo.get(pos.get(i), 0.0), 0.0) for i in ids))


def desbalance(dar: float, recibir: float) -> float:
    """Cuánto más recibes que das, como fracción del lado mayor (entre -1 y 1)."""
    return (recibir - dar) / max(dar, recibir, 1.0)


def buscar(plantillas, jugadores, tablas, equipo_id, adp, rival_excluido, *, top_rival=5,
           max_das=3, max_recibes=2, n_libres=6, max_propuestas=5, tope=14,
           excluir=frozenset()):
    """`excluir`: agentes libres reservados para agencia libre; no cuentan ni en tu plantilla
    de referencia ni de relleno, para que la ganancia no repita la de agencia libre."""
    valuador = Valuador(tablas)
    resto = pd.concat(tablas.values()).groupby("jugador_id")["proy"].sum()
    memo: dict[frozenset, float] = {}

    def val(ids) -> float:
        clave = frozenset(ids)
        if clave not in memo:
            memo[clave] = valuador.valor(clave)
        return memo[clave]

    def fama(ids) -> float:
        return sum(nombre(adp.get(i)) for i in ids)

    sanos = jugadores[(jugadores.disponibilidad != "EQUIPO") & (jugadores.lesion == "ACTIVE")]
    pos = dict(zip(jugadores.jugador_id, jugadores.pos, strict=True))
    reemplazo = sanos.assign(r=sanos.jugador_id.map(resto).fillna(0.0)).groupby("pos").r.max()
    reemplazo = reemplazo.to_dict()

    def valor_mercado(ids) -> float:
        return sobre_libre(ids, resto, pos, reemplazo)

    libres = sanos[~sanos.jugador_id.isin(excluir)]
    libres = (libres.assign(r=libres.jugador_id.map(resto).fillna(0.0))
              .sort_values("r", ascending=False).jugador_id.head(n_libres).tolist())

    def ajustar_mio(ids: set[int], recibidos: set[int]):
        """Deja la plantilla en `tope`: pide agentes libres o suelta al que menos aporta."""
        ids, relleno, sueltas = set(ids), [], []
        while len(ids) < tope:
            opciones = [f for f in libres if f not in ids]
            if not opciones:
                break
            mejor = max(opciones, key=lambda f: val(ids | {f}))
            ids.add(mejor)
            relleno.append(mejor)
        while len(ids) > tope:
            peor = max(ids - recibidos, key=lambda x: (val(ids - {x}), -resto.get(x, 0.0)))
            ids.remove(peor)
            sueltas.append(peor)
        return ids, tuple(relleno), tuple(sueltas)

    def recortar_suyo(ids: set[int], limite: int) -> set[int]:
        ids = set(ids)
        while len(ids) > limite:
            ids.remove(min(ids, key=lambda x: resto.get(x, 0.0)))
        return ids

    por_equipo = {e: set(g.jugador_id) for e, g in plantillas.groupby("equipo_id")}
    mia = por_equipo[equipo_id]
    base_mia = val(ajustar_mio(mia, set())[0])
    mejores: list[Propuesta] = []
    for rival, suya in por_equipo.items():
        if rival in (equipo_id, rival_excluido):
            continue
        base_suya = val(suya)
        limite_suyo = max(tope, len(suya))  # no castigar a quien ya tenía más de 14
        top = sorted(suya, key=lambda x: -resto.get(x, 0.0))[:top_rival]
        mejor: Propuesta | None = None
        for k2 in range(1, max_recibes + 1):
            for recibes in itertools.combinations(top, k2):
                for k1 in range(1, max_das + 1):
                    for das in itertools.combinations(sorted(mia), k1):
                        d_nombre = fama(das) - fama(recibes)
                        if d_nombre < MIN_DELTA_NOMBRE:
                            continue
                        sin_ajuste = (mia - set(das)) | set(recibes)
                        # Cota superior exacta: el valor solo sube al agregar jugadores.
                        cota = val(sin_ajuste | set(libres)) - base_mia
                        if cota <= max(0.0, mejor.ganancia if mejor else 0.0):
                            continue
                        d_rival = val(recortar_suyo((suya - set(recibes)) | set(das),
                                                    limite_suyo)) - base_suya
                        if d_rival < MIN_DELTA_RIVAL:
                            continue
                        nueva, relleno, sueltas = ajustar_mio(sin_ajuste, set(recibes))
                        ganancia = round(val(nueva) - base_mia, 6)
                        if ganancia <= 0 or (mejor and ganancia <= mejor.ganancia):
                            continue
                        desb = desbalance(valor_mercado(das), valor_mercado(recibes))
                        mejor = Propuesta(rival, das, recibes, relleno, sueltas, ganancia,
                                          round(d_rival, 1), round(d_nombre, 1),
                                          round(desb, 3), riesgo_veto(desb))
        if mejor:
            mejores.append(mejor)
    mejores.sort(key=lambda x: -x.ganancia)
    return mejores[:max_propuestas]
