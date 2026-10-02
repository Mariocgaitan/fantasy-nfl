"""Agencia libre: a quién pedir, a quién soltar y quién viene ganando rol."""

import pandas as pd

from fantasy.config import SEMANA_FINAL
from fantasy.decision.alineacion import CUPOS, FLEX_POS, TITULARES
from fantasy.proyeccion.espn import tabla_semana

SEGURO = 0.15          # fracción de sus puntos que vale un respaldo (sin validar)
SEMANAS_SEGURO = 3
SEGURO_POS = ("QB", "TE")  # RB y WR ya se cubren entre sí por el FLEX
ADP_INTOCABLE = 60.0  # nombre alto: sirve para intercambios
COLUMNAS_ROL = ["jugador_id", "nombre", "pos", "disponibilidad", "equipo_fantasy_id",
                "snaps_antes", "snaps_ahora", "oport_antes", "oport_ahora", "dueno_pct",
                "dueno_cambio"]


def tablas_por_semana(jugadores, proyecciones, partidos, plantilla_mia, semana, ahora):
    tablas = {}
    for w in range(semana, SEMANA_FINAL + 1):
        t = tabla_semana(jugadores, proyecciones, partidos, w, con_lesion=(w == semana))
        if w == semana:
            t = t.merge(plantilla_mia[["jugador_id", "slot", "bloqueado"]],
                        on="jugador_id", how="left")
            empezo = t["inicio_utc"].notna() & (t["inicio_utc"] <= ahora)
            # Solo cuenta un bloqueo si el partido de esta semana ya empezó: el martes ESPN
            # todavía marca bloqueada la semana que terminó.
            espn_dice = t["bloqueado"].fillna(True).astype(bool)
            t["bloqueado"] = espn_dice & empezo
            t["slot"] = t["slot"].fillna("BANCA")
        else:
            t["slot"] = "BANCA"
            t["bloqueado"] = False
        tablas[w] = t
    return tablas


class Valuador:
    """Lo mismo que sumar `optima(...).esperado` por semana, en Python puro: la búsqueda de
    agencia libre evalúa miles de plantillas y con pandas tardaba minutos."""

    def __init__(self, tablas: dict[int, pd.DataFrame]):
        self._semanas = [
            {int(r.jugador_id): (r.pos, float(r.esperado), bool(r.bloqueado), r.slot)
             for r in t[["jugador_id", "pos", "esperado", "bloqueado", "slot"]].itertuples()}
            for t in tablas.values()
        ]

    def valor(self, ids: set[int]) -> float:
        return sum(self._semana(filas, ids) for filas in self._semanas)

    @staticmethod
    def _semana(filas: dict, ids: set[int]) -> float:
        total = 0.0
        ocupados = dict.fromkeys(TITULARES, 0)
        libres = []
        for j in ids:
            f = filas.get(j)
            if f is None:
                continue
            pos, esperado, bloqueado, slot = f
            if bloqueado:
                if slot in ocupados:
                    ocupados[slot] += 1
                    total += esperado
            else:
                libres.append((esperado, pos))
        libres.sort(key=lambda x: -x[0])
        usados = [False] * len(libres)
        for pos, n in CUPOS.items():
            faltan = n - ocupados[pos]
            for i, (esperado, p) in enumerate(libres):
                if faltan <= 0:
                    break
                if p == pos and not usados[i]:
                    usados[i] = True
                    total += esperado
                    faltan -= 1
        if ocupados["FLEX"] == 0:
            for i, (esperado, p) in enumerate(libres):
                if p in FLEX_POS and not usados[i]:
                    total += esperado
                    break
        return total


def valor_plantilla(ids: set[int], tablas: dict[int, pd.DataFrame]) -> float:
    return Valuador(tablas).valor(ids)


def _seguro(cand: pd.Series, ids: set[int], jugadores: pd.DataFrame,
            tablas: dict[int, pd.DataFrame], semana: int) -> float:
    pos = cand.pos
    if pos not in SEGURO_POS:
        return 0.0
    sanos = jugadores[jugadores.jugador_id.isin(ids) & (jugadores.pos == pos)
                      & (jugadores.lesion == "ACTIVE")]
    if len(sanos) > CUPOS.get(pos, 0):
        return 0.0
    semanas = [w for w in range(semana, semana + SEMANAS_SEGURO) if w in tablas]
    puntos = sum(float(tablas[w].loc[tablas[w].jugador_id == cand.jugador_id, "proy"].sum())
                 for w in semanas)
    return SEGURO * puntos


def recomendar(jugadores, tablas, mis_ids, semana, *, max_candidatos=30, max_sugerencias=5,
               intocables=frozenset()):
    futuro = pd.concat(tablas.values())
    total = futuro.groupby("jugador_id")["proy"].sum()
    libres = jugadores[jugadores.disponibilidad.isin(["LIBRE", "WAIVERS"])
                       & ~jugadores.jugador_id.isin(mis_ids)]
    libres = libres.assign(total=libres.jugador_id.map(total).fillna(0.0))
    candidatos = libres.sort_values("total", ascending=False).head(max_candidatos)
    t0 = tablas[semana]
    bloqueados = set(t0.loc[t0.bloqueado & t0.jugador_id.isin(mis_ids), "jugador_id"])
    soltables = [j for j in mis_ids if j not in bloqueados and j not in intocables]
    valuador = Valuador(tablas)
    base = valuador.valor(mis_ids)
    filas = []
    for _, cand in candidatos.iterrows():
        for s in soltables:
            nuevos = (mis_ids - {s}) | {int(cand.jugador_id)}
            ganancia = valuador.valor(nuevos) - base
            ganancia += _seguro(cand, mis_ids - {s}, jugadores, tablas, semana)
            ganancia = round(ganancia, 6)  # que el ruido de coma flotante no rompa empates
            filas.append({"pedir": int(cand.jugador_id), "soltar": int(s),
                          "pos": cand.pos, "ganancia": ganancia,
                          "valor_soltado": float(total.get(s, 0.0))})
    r = pd.DataFrame(filas, columns=["pedir", "soltar", "pos", "ganancia", "valor_soltado"])
    # Empates (la banca no suma): se suelta al de menor proyección de aquí al final.
    r = r[r.ganancia > 1e-9].sort_values(["ganancia", "valor_soltado"], ascending=[False, True],
                                         kind="stable")
    r = r.drop_duplicates("pedir")[["pedir", "soltar", "pos", "ganancia"]]
    return r.head(max_sugerencias).reset_index(drop=True)


def ganando_rol(uso, jugadores, *, plantillas=None, equipo_id=None, umbral_snaps=0.15,
                umbral_oport=3.0, max_cambio_dueno=1.0):
    """Libres a los que les sube el uso. Con `plantillas` y `equipo_id`, también los que están
    en la banca de un rival: su dueño aún no los valora y salen baratos en un intercambio."""
    semanas = sorted(uso.semana.unique())
    if len(semanas) < 2:
        return pd.DataFrame(columns=COLUMNAS_ROL)
    recientes = semanas[-2:] if len(semanas) >= 3 else semanas[-1:]
    u = uso.assign(oport=uso.targets + uso.acarreos, reciente=uso.semana.isin(recientes))
    g = u.groupby(["jugador_id", "reciente"])[["snaps_pct", "oport"]].mean().unstack("reciente")
    g = g.dropna()
    if g.empty:
        return pd.DataFrame(columns=COLUMNAS_ROL)
    d = pd.DataFrame({
        "snaps_antes": g[("snaps_pct", False)], "snaps_ahora": g[("snaps_pct", True)],
        "oport_antes": g[("oport", False)], "oport_ahora": g[("oport", True)],
    }).reset_index()
    sube = ((d.snaps_ahora - d.snaps_antes >= umbral_snaps)
            | (d.oport_ahora - d.oport_antes >= umbral_oport))
    d = d[sube].merge(jugadores, on="jugador_id")
    elegible = d.disponibilidad != "EQUIPO"
    if plantillas is not None and equipo_id is not None:
        banca_rival = set(plantillas.loc[(plantillas.slot == "BANCA")
                                         & (plantillas.equipo_id != equipo_id), "jugador_id"])
        elegible |= d.jugador_id.isin(banca_rival)
    d = d[elegible & (d.dueno_cambio <= max_cambio_dueno)]
    d = d.assign(delta=d.snaps_ahora - d.snaps_antes).sort_values("delta", ascending=False)
    return d[COLUMNAS_ROL].reset_index(drop=True)
