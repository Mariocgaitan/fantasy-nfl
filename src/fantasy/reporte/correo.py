"""Aviso por correo a través del reenvío de ntfy.sh (sin cuenta ni contraseña)."""

import urllib.parse
import urllib.request

from fantasy.reporte.armado import DIAS, Reporte


def resumen(r: Reporte) -> str:
    lineas = [f"Semana {r.semana} · reporte {DIAS[r.tipo]} · SIN VALIDAR (decide ESPN)"]
    lineas.append("Alineación: " + (" · ".join(r.cambios) if r.cambios else "sin cambios"))
    if r.agencia:
        a = r.agencia[0]
        lineas.append(f"Agencia libre: pedir {a['pedir']}, soltar {a['soltar']} (+{a['ganancia']})")
    sin = [x["titular"] for x in r.reemplazos if x["suplente"] is None]
    if sin:
        lineas.append("Sin respaldo útil: " + ", ".join(sin))
    return "\n".join(lineas)


def enviar(tema: str, destino: str, titulo: str, cuerpo: str, enlace: str | None, *,
           abrir=urllib.request.urlopen) -> None:
    params = {"title": titulo, "email": destino}
    if enlace:
        params["click"] = enlace
    url = f"https://ntfy.sh/{tema}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, data=cuerpo.encode("utf-8"), method="POST")
    with abrir(req, timeout=30):
        pass
