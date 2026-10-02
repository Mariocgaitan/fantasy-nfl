"""Reporte → HTML estático (GitHub Pages)."""

from dataclasses import asdict

from jinja2 import Environment, PackageLoader, select_autoescape

from fantasy.reporte.armado import DIAS, Reporte, hora_sidney

_ENTORNO = Environment(loader=PackageLoader("fantasy.reporte", "plantillas"),
                       autoescape=select_autoescape(["html", "j2"]))
_ENTORNO.filters["hora"] = hora_sidney


def generar_html(r: Reporte) -> str:
    return _ENTORNO.get_template("reporte.html.j2").render(dia=DIAS[r.tipo], **asdict(r))
