"""Punto de entrada: `fantasy reporte`."""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from fantasy.almacen import instantaneas
from fantasy.config import EQUIPO_ID, LIGA_ID, TEMPORADA
from fantasy.esquemas import DatosInvalidos
from fantasy.horario import ZONA, reporte_que_toca
from fantasy.ingesta.espn import bajar_espn
from fantasy.ingesta.nflverse import bajar_nflverse
from fantasy.reporte import correo
from fantasy.reporte.armado import armar
from fantasy.reporte.html import generar_html


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fantasy")
    sub = p.add_subparsers(dest="comando", required=True)
    r = sub.add_parser("reporte", help="genera el reporte que toca")
    r.add_argument("--tipo", default="auto", choices=["auto", "martes", "viernes", "domingo"])
    r.add_argument("--salida", type=Path, default=Path("salida"))
    r.add_argument("--instantanea", type=Path, help="corre sin red desde esta carpeta")
    r.add_argument("--ahora", help="momento ISO con zona (para pruebas)")
    r.add_argument("--forzar", action="store_true", help="regenera aunque ya exista")
    r.add_argument("--sin-correo", action="store_true")
    return p


def main(argv: list[str] | None = None, *, entorno: dict | None = None, enviar_fn=None) -> int:
    a = _parser().parse_args(argv)
    entorno = dict(os.environ) if entorno is None else entorno
    enviar_fn = enviar_fn or correo.enviar
    ahora = datetime.fromisoformat(a.ahora) if a.ahora else datetime.now(UTC)
    tipo = reporte_que_toca(ahora) if a.tipo == "auto" else a.tipo
    if tipo is None:
        print("No toca reporte a esta hora.")
        return 0
    tema, destino = entorno.get("NTFY_TOPIC"), entorno.get("NTFY_EMAIL")
    avisar = bool(tema and destino and not a.sin_correo)
    try:
        avisos: list[str] = []
        if a.instantanea:
            crudos = instantaneas.cargar(a.instantanea)
        else:
            crudos = bajar_espn(TEMPORADA, LIGA_ID)
            try:
                crudos |= bajar_nflverse(TEMPORADA)
            except DatosInvalidos as e:
                avisos.append(f"nflverse no disponible: {e}")
        reporte = armar(crudos, pd.Timestamp(ahora), tipo, EQUIPO_ID, avisos)
    except DatosInvalidos as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if avisar:
            enviar_fn(tema, destino, "Fantasy: reporte NO generado", str(e), None)
        return 1

    nombre = f"{TEMPORADA}-sem{reporte.semana:02d}-{tipo}.html"
    archivo = a.salida / "reportes" / nombre
    if archivo.exists() and not a.forzar:
        print(f"Ya existe {archivo}; no se repite.")
        return 0
    if not a.instantanea:
        instantaneas.guardar(a.salida, TEMPORADA, reporte.semana, ahora.astimezone(ZONA), crudos)
    html = generar_html(reporte)
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(html, encoding="utf-8")
    (a.salida / "index.html").write_text(html, encoding="utf-8")
    print(f"Reporte escrito en {archivo}")
    if avisar:
        enlace = entorno.get("PAGES_URL", "").rstrip("/") + f"/reportes/{nombre}"
        titulo = f"Fantasy · semana {reporte.semana} · {tipo}"
        enviar_fn(tema, destino, titulo, correo.resumen(reporte), enlace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
