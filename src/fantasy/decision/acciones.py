"""Del reporte armado a una lista de acciones: 🔴 urgente, 🟡 recomendado, ⚪ en el radar."""

from dataclasses import dataclass

import pandas as pd

GANANCIA_SEMANAL_MIN = 1.0
EN_DUDA = ("QUESTIONABLE", "DOUBTFUL", "DAY_TO_DAY")
ORDEN = {"urgente": 0, "recomendado": 1, "radar": 2}
COMO_ENTRA = {"LIBRE": "libre, entra al instante",
              "WAIVERS": "waivers: se procesa a las 17:00"}


@dataclass(frozen=True)
class Accion:
    urgencia: str                 # "urgente" | "recomendado" | "radar"
    texto: str
    porque: str
    limite: pd.Timestamp | None   # UTC
    tipo: str


def construir(*, cambios, limite_cambios, alineacion, reemplazos, pedidos, lugares, agencia,
              intercambios, rol, max_rol=5) -> list[Accion]:
    acc: list[Accion] = []
    if cambios:
        acc.append(Accion("urgente", "Cambia tu alineación: " + " · ".join(cambios),
                          "tu alineación actual no es la mejor según ESPN", limite_cambios,
                          "alineacion"))
    suplente = {r["titular"]: r["suplente"] for r in reemplazos}
    for f in alineacion:
        if f["lesion"] in EN_DUDA and not f["bloqueado"] and suplente.get(f["nombre"]):
            acc.append(Accion("urgente", f"Si {f['nombre']} queda fuera, mete a "
                                         f"{suplente[f['nombre']]}",
                              f"{f['nombre']} está {f['estado']}; ESPN confirma quién no juega "
                              "~90 minutos antes del partido", f["inicio_utc"], "inactivo"))
    for p in pedidos:
        soltar = f", suelta a {p['soltar']}" if p.get("soltar") else ""
        acc.append(Accion("urgente", f"Pide a {p['nombre']} ({p['pos']}){soltar} "
                                     f"({COMO_ENTRA[p['disponibilidad']]})",
                          f"{p['titular']} no juega y no tienes quien lo reemplace",
                          p["limite"], "pedir"))
    for x in lugares:
        if x["motivo"] == "respaldo":
            porque = f"{x['cubre']} no tiene quien lo cubra si queda fuera"
        else:
            porque = (f"le sirve a {x['rival']} (+{x['valor_rival']:.0f} en su alineación) "
                      "para un intercambio")
        acc.append(Accion("recomendado", f"Pide a {x['nombre']} ({x['pos']}) sin soltar a "
                                         f"nadie ({COMO_ENTRA[x['disponibilidad']]})",
                          porque, x["limite"], "lugar"))
    buenas, flojas, vistas = [], [], set()
    for a in sorted(agencia, key=lambda a: -a["semanal"]):
        if a["semanal"] >= GANANCIA_SEMANAL_MIN:
            if a["pos"] not in vistas:
                vistas.add(a["pos"])
                buenas.append(a)
        else:
            flojas.append(a)
    for a in buenas:
        acc.append(Accion("recomendado", f"Pide a {a['pedir']} ({a['pos']}), suelta a "
                                         f"{a['soltar']}", f"+{a['semanal']:.1f} puntos por "
                                                           "semana", None, "agencia"))
    for x in intercambios:
        acc.append(Accion("recomendado", f"Propón a {x['rival']}: das {', '.join(x['das'])} "
                                         f"por {', '.join(x['recibes'])}",
                          f"+{x['semanal']:.1f} puntos por semana · riesgo de veto "
                          f"{x['riesgo']} · propón uno a la vez", None, "intercambio"))
    if flojas:
        a = flojas[0]
        acc.append(Accion("radar", f"Agencia libre: el mejor cambio ({a['pedir']} por "
                                   f"{a['soltar']}) gana +{a['semanal']:.1f} por semana",
                          "no vale la pena", None, "agencia"))
    for x in rol[:max_rol]:
        if x["dueno"]:
            acc.append(Accion("radar", f"{x['nombre']} ({x['pos']}), en la banca de "
                                       f"{x['dueno']}, está ganando rol",
                              "objetivo barato para el próximo intercambio", None, "rol"))
        else:
            acc.append(Accion("radar", f"{x['nombre']} ({x['pos']}) está ganando rol y está "
                                       "libre", "pídelo si se abre un lugar", None, "rol"))
    lejos = pd.Timestamp.max.tz_localize("UTC")
    return sorted(acc, key=lambda a: (ORDEN[a.urgencia],
                                      a.limite if a.urgencia == "urgente" and a.limite is not None
                                      else lejos))


def contar(acciones: list[Accion]) -> dict[str, int]:
    n = dict.fromkeys(ORDEN, 0)
    for a in acciones:
        n[a.urgencia] += 1
    return n
