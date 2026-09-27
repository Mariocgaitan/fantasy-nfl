"""De respuestas crudas a un Reporte listo para pintar. Sin red ni disco."""

from dataclasses import dataclass, field

import pandas as pd

from fantasy.config import TEMPORADA
from fantasy.decision import agencia_libre
from fantasy.decision.alineacion import TITULARES, aplicar_regla_duda, optima, reemplazos
from fantasy.horario import ZONA, semana_objetivo
from fantasy.ingesta import espn, nflverse

DIAS = {"martes": "del martes", "viernes": "del viernes", "domingo": "del domingo"}
DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


@dataclass
class Reporte:
    tipo: str
    semana: int
    generado: str
    esperado: float
    alineacion: list[dict]
    cambios: list[str]
    reemplazos: list[dict]
    agencia: list[dict]
    rol: list[dict]
    avisos: list[str] = field(default_factory=list)


def armar(crudos: dict, ahora: pd.Timestamp, tipo: str, equipo_id: int,
          avisos: list[str] | None = None) -> Reporte:
    avisos = list(avisos or [])
    liga = crudos["liga"]
    plantillas = espn.parsear_plantillas(liga)
    jugadores = espn.parsear_jugadores(crudos["proyecciones"], liga, crudos["agentes_libres"])
    proyecciones = espn.parsear_proyecciones(crudos["proyecciones"], TEMPORADA)
    partidos = espn.parsear_calendario(crudos["calendario"])
    semana = semana_objetivo(espn.semana_actual(liga), partidos, ahora)

    mia = plantillas[plantillas.equipo_id == equipo_id]
    if semana != espn.semana_actual(liga):  # semana nueva: nada bloqueado todavía
        mia = mia.assign(bloqueado=False)
    tablas = agencia_libre.tablas_por_semana(jugadores, proyecciones, partidos, mia, semana, ahora)
    t = tablas[semana]
    mis_ids = set(mia.jugador_id)
    tm = t[t.jugador_id.isin(mis_ids)]
    al = aplicar_regla_duda(optima(tm), tm)
    idx = tm.set_index("jugador_id")

    alineacion = [{
        "slot": s, "nombre": idx.loc[j, "nombre"], "pos": idx.loc[j, "pos"],
        "proy": round(float(idx.loc[j, "proy"]), 1), "lesion": idx.loc[j, "lesion"],
        "bloqueado": bool(idx.loc[j, "bloqueado"]),
    } for s, j in al.slots]
    actuales = set(tm.loc[tm.slot.isin(TITULARES), "jugador_id"])
    entran = [idx.loc[j, "nombre"] for j in al.ids() - actuales]
    salen = [idx.loc[j, "nombre"] for j in actuales - al.ids()]
    cambios = [f"Entra {e}" for e in sorted(entran)] + [f"Sale {s}" for s in sorted(salen)]

    def hora(j):
        v = idx.loc[j, "inicio_utc"]
        if pd.isna(v):
            return "descansa"
        local = v.tz_convert(ZONA)
        return f"{DIAS_CORTOS[local.weekday()]} {local:%H:%M}"

    remp = [{
        "slot": r.slot, "titular": idx.loc[r.titular, "nombre"], "hora": hora(r.titular),
        "suplente": idx.loc[r.suplente, "nombre"] if r.suplente else None,
        "hora_suplente": hora(r.suplente) if r.suplente else None,
    } for r in reemplazos(al, tm)]

    por_id = jugadores.set_index("jugador_id")
    nombres = por_id.nombre
    agencia = [{
        "pedir": nombres[x.pedir], "pos": x.pos, "soltar": nombres[x.soltar],
        "lesion": por_id.loc[x.pedir, "lesion"],
        "ganancia": round(float(x.ganancia), 1),
    } for x in agencia_libre.recomendar(jugadores, tablas, mis_ids, semana).itertuples()]

    rol: list[dict] = []
    if all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        uso = nflverse.tablas(crudos)
        rol = agencia_libre.ganando_rol(uso, jugadores).head(8).round(2).to_dict("records")
        ultima = int(uso.semana.max()) if len(uso) else 0
        avisos.append(f"Uso de jugadores (nflverse) hasta la semana {ultima}.")
    else:
        avisos.append("Sin datos de uso de nflverse: no se calculó quién gana rol.")

    return Reporte(
        tipo=tipo, semana=semana,
        generado=ahora.tz_convert(ZONA).strftime("%Y-%m-%d %H:%M"),
        esperado=round(al.esperado, 1), alineacion=alineacion, cambios=cambios,
        reemplazos=remp, agencia=agencia, rol=rol, avisos=avisos,
    )
