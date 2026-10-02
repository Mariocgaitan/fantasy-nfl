"""Aviso por correo desde Gmail (contraseña de aplicación guardada como secreto)."""

import smtplib
from email.message import EmailMessage

from fantasy.decision.acciones import contar
from fantasy.reporte.armado import DIAS, Reporte, hora_sidney

SERVIDOR = ("smtp.gmail.com", 465)

def resumen(r: Reporte) -> str:
    n = contar(r.acciones)
    cabeza = f"Reporte {DIAS[r.tipo]} (semana {r.semana})"
    if not n["urgente"] and not n["recomendado"]:
        return f"{cabeza}: nada que hacer."
    partes = []
    if n["urgente"]:
        partes.append(f"{n['urgente']} urgente{'s' if n['urgente'] > 1 else ''}")
    if n["recomendado"]:
        partes.append(f"{n['recomendado']} recomendada{'s' if n['recomendado'] > 1 else ''}")
    lineas = [f"{cabeza}: {', '.join(partes)}."]
    for a in r.acciones:
        if a.urgencia == "urgente":
            limite = f" — antes del {hora_sidney(a.limite)}" if a.limite is not None else ""
            lineas.append(f"🔴 {a.texto}{limite}")
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
