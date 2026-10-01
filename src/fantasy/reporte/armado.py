"""De respuestas crudas a un Reporte listo para pintar. Sin red ni disco."""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from fantasy.config import (
    RUTA_MODELO,
    RUTA_MODELO_V2,
    RUTA_VALIDACION,
    SEMANA_FINAL,
    TEMPORADA,
    UMBRAL_DISCREPA,
)
from fantasy.decision import agencia_libre
from fantasy.decision import intercambios as intercambios_mod
from fantasy.decision.agencia_libre import ADP_INTOCABLE
from fantasy.decision.alineacion import TITULARES, aplicar_regla_duda, optima, reemplazos
from fantasy.horario import ZONA, semana_objetivo
from fantasy.ingesta import espn, nflverse
from fantasy.modelo.estado import estado_validacion
from fantasy.proyeccion.modelo import prediccion_modelo

DIAS = {"martes": "del martes", "viernes": "del viernes", "domingo": "del domingo"}
DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
ESTADOS = {
    "ACTIVE": "sano", "QUESTIONABLE": "en duda", "DOUBTFUL": "dudoso", "OUT": "fuera",
    "INJURY_RESERVE": "lesionado (IR)", "SUSPENSION": "suspendido", "DAY_TO_DAY": "día a día",
}


def estado(lesion: str) -> str:
    return ESTADOS.get(lesion, lesion.lower())


class TemporadaTerminada(Exception):
    """Ya no quedan semanas de la liga por decidir."""


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
    intercambios: list[dict] = field(default_factory=list)
    validado: str | None = None
    avisos: list[str] = field(default_factory=list)


def armar(crudos: dict, ahora: pd.Timestamp, tipo: str, equipo_id: int,
          avisos: list[str] | None = None, ruta_modelo: Path | None = None,
          ruta_validacion: Path | None = None) -> Reporte:
    avisos = list(avisos or [])
    liga = crudos["liga"]
    plantillas = espn.parsear_plantillas(liga)
    jugadores = espn.parsear_jugadores(crudos["proyecciones"], liga, crudos["agentes_libres"])
    proyecciones = espn.parsear_proyecciones(crudos["proyecciones"], TEMPORADA)
    partidos = espn.parsear_calendario(crudos["calendario"])
    semana = semana_objetivo(espn.semana_actual(liga), partidos, ahora)
    if semana > SEMANA_FINAL:
        raise TemporadaTerminada(f"la temporada de la liga terminó (semana {semana})")

    mia = plantillas[plantillas.equipo_id == equipo_id]
    tablas = agencia_libre.tablas_por_semana(jugadores, proyecciones, partidos, mia, semana, ahora)
    ruta = ruta_modelo or (RUTA_MODELO_V2 if RUTA_MODELO_V2.exists() else RUTA_MODELO)
    modelo, aviso_modelo = prediccion_modelo(crudos, TEMPORADA, semana, ruta)
    if aviso_modelo:
        avisos.append(aviso_modelo)
    estado_val = estado_validacion(ruta_validacion or RUTA_VALIDACION, ruta)
    espn_semana = dict(zip(tablas[semana].jugador_id, tablas[semana].proy, strict=True))
    manda = estado_val["manda"] and bool(modelo)
    if estado_val["manda"] and not modelo:
        avisos.append("El modelo está validado pero hoy no pudo predecir: decide ESPN.")
    if manda:
        # Validado (spec 10.7): todo pasa a ESPN calibrada y la semana objetivo usa al modelo.
        for tw in tablas.values():
            tw["proy"] = tw["proy"] * estado_val["k"]
            tw["esperado"] = tw["proy"] * tw["p_jugar"]
        t0 = tablas[semana]
        nueva = t0["jugador_id"].map(modelo)
        t0["proy"] = nueva.where(nueva.notna(), t0["proy"]).clip(lower=0.0)
        t0["esperado"] = t0["proy"] * t0["p_jugar"]
    t = tablas[semana]
    mis_ids = set(mia.jugador_id)
    adp = espn.parsear_adp(liga)
    intocables = {j for j in mis_ids if adp.get(j, 200.0) < ADP_INTOCABLE}
    tm = t[t.jugador_id.isin(mis_ids)]
    al = aplicar_regla_duda(optima(tm), tm)
    idx = tm.set_index("jugador_id")

    alineacion = [{
        "slot": s, "nombre": idx.loc[j, "nombre"], "pos": idx.loc[j, "pos"],
        "proy": round(float(idx.loc[j, "proy"]), 1), "lesion": idx.loc[j, "lesion"],
        "estado": ("descansa" if pd.isna(idx.loc[j, "inicio_utc"])
                   else estado(idx.loc[j, "lesion"])),
        "bloqueado": bool(idx.loc[j, "bloqueado"]),
        "espn": round(float(espn_semana.get(j, 0.0)), 1),
        "modelo": round(modelo[j], 1) if j in modelo else None,
        "discrepa": j in modelo and abs(modelo[j] - float(espn_semana.get(j, 0.0))) > UMBRAL_DISCREPA,
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
        "lesion_suplente": idx.loc[r.suplente, "lesion"] if r.suplente else None,
        "estado_suplente": estado(idx.loc[r.suplente, "lesion"]) if r.suplente else None,
    } for r in reemplazos(al, tm)]

    por_id = jugadores.set_index("jugador_id")
    nombres = por_id.nombre
    sugeridas = agencia_libre.recomendar(jugadores, tablas, mis_ids, semana,
                                         intocables=intocables)
    agencia = [{
        "pedir": nombres[x.pedir], "pos": x.pos, "soltar": nombres[x.soltar],
        "lesion": por_id.loc[x.pedir, "lesion"],
        "estado": estado(por_id.loc[x.pedir, "lesion"]),
        "ganancia": round(float(x.ganancia), 1),
    } for x in sugeridas.itertuples()]

    rol: list[dict] = []
    if all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        uso = nflverse.tablas(crudos)
        rol = agencia_libre.ganando_rol(uso, jugadores).head(8).round(2).to_dict("records")
        ultima = int(uso.semana.max()) if len(uso) else 0
        avisos.append(f"Uso de jugadores (nflverse) hasta la semana {ultima}.")
    else:
        avisos.append("Sin datos de uso de nflverse: no se calculó quién gana rol.")

    propuestas: list[dict] = []
    if tipo == "martes":
        equipos = {t["id"]: t["name"].strip() for t in liga["teams"]}
        rival = espn.rival_de(liga, equipo_id, semana)
        try:
            # Agencia libre manda: sus libres no se reusan de relleno en los intercambios.
            encontradas = intercambios_mod.buscar(plantillas, jugadores, tablas, equipo_id,
                                                  adp, rival,
                                                  excluir=set(sugeridas.pedir.astype(int)))
        except Exception as e:  # noqa: BLE001 — un fallo aquí no tumba el resto del reporte
            encontradas = []
            avisos.append(f"No se pudieron calcular los intercambios: {type(e).__name__}: {e}")
        for x in encontradas:
            propuestas.append({
                "rival": equipos[x.rival],
                "das": [nombres[i] for i in x.das],
                "recibes": [nombres[i] for i in x.recibes],
                "relleno": [nombres[i] for i in x.relleno],
                "sueltas": [nombres[i] for i in x.sueltas],
                "ganancia": round(x.ganancia, 1),
                "riesgo": x.riesgo_veto,
                "lesiones": [f"{nombres[i]} ({estado(por_id.loc[i, 'lesion'])})"
                             for i in x.recibes if por_id.loc[i, "lesion"] != "ACTIVE"],
            })

    return Reporte(
        tipo=tipo, semana=semana,
        generado=ahora.tz_convert(ZONA).strftime("%Y-%m-%d %H:%M"),
        esperado=round(al.esperado, 1), alineacion=alineacion, cambios=cambios,
        reemplazos=remp, agencia=agencia, rol=rol, intercambios=propuestas, avisos=avisos,
        validado=estado_val["fuente"] if manda else None,
    )
