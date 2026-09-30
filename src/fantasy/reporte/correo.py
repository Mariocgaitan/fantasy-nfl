"""Aviso por correo desde Gmail (contraseña de aplicación guardada como secreto)."""

import smtplib
from email.message import EmailMessage

from fantasy.reporte.armado import DIAS, Reporte, estado

SERVIDOR = ("smtp.gmail.com", 465)


def resumen(r: Reporte) -> str:
    lineas = [f"Semana {r.semana} · reporte {DIAS[r.tipo]} · SIN VALIDAR (decide ESPN)"]
    lineas.append("Alineación: " + (" · ".join(r.cambios) if r.cambios else "sin cambios"))
    if r.agencia:
        a = r.agencia[0]
        nota = f" ({estado(a['lesion'])})" if a.get("lesion", "ACTIVE") != "ACTIVE" else ""
        lineas.append(f"Agencia libre: pedir {a['pedir']}{nota}, soltar {a['soltar']} "
                      f"(+{a['ganancia']})")
    if r.intercambios:
        x = r.intercambios[0]
        lineas.append(f"Intercambio: das {', '.join(x['das'])} a {x['rival']} por "
                      f"{', '.join(x['recibes'])} (+{x['ganancia']}, veto {x['riesgo']})")
    sin = [x["titular"] for x in r.reemplazos if x["suplente"] is None]
    if sin:
        lineas.append("Sin respaldo útil: " + ", ".join(sin))
    return "\n".join(lineas)


def enviar(credenciales: tuple[str, str], destino: str, titulo: str, cuerpo: str,
           enlace: str | None, *, smtp=smtplib.SMTP_SSL) -> None:
    usuario, clave = credenciales
    msg = EmailMessage()
    msg["From"] = usuario
    msg["To"] = destino
    msg["Subject"] = titulo
    msg.set_content(cuerpo + (f"\n\nReporte completo: {enlace}\n" if enlace else "\n"))
    with smtp(*SERVIDOR, timeout=30) as s:
        s.login(usuario, clave)
        s.send_message(msg)
