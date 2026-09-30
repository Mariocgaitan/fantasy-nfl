"""Punto de entrada: `fantasy reporte`."""

import argparse
import os
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from fantasy.almacen import instantaneas
from fantasy.config import EQUIPO_ID, LIGA_ID, TEMPORADA
from fantasy.esquemas import DatosInvalidos
from fantasy.horario import ZONA, slot_actual
from fantasy.ingesta.espn import bajar_espn
from fantasy.ingesta.nflverse import bajar_nflverse
from fantasy.reporte import correo
from fantasy.reporte.armado import TemporadaTerminada, armar
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
    h = sub.add_parser("historico", help="baja 2023–2024 para entrenar el modelo")
    h.add_argument("--raiz", type=Path, default=Path("historico"))
    return p


def main(argv: list[str] | None = None, *, entorno: dict | None = None, enviar_fn=None) -> int:
    a = _parser().parse_args(argv)
    if a.comando == "historico":
        from fantasy.ingesta import historico
        for t in historico.TEMPORADAS_ENTRENAMIENTO:
            historico.guardar_historico(a.raiz, t, historico.bajar_espn_historico(t),
                                        bajar_nflverse(t))
            print(f"Histórico {t} guardado en {a.raiz}")
        return 0
    entorno = dict(os.environ) if entorno is None else entorno
    enviar_fn = enviar_fn or correo.enviar
    ahora = datetime.fromisoformat(a.ahora) if a.ahora else datetime.now(UTC)
    marcador = None
    if a.tipo == "auto":
        slot = slot_actual(ahora)
        if slot is None:
            print("No toca reporte a esta hora.")
            return 0
        tipo, inicio = slot
        marcador = a.salida / f"ultimo_{tipo}.txt"
        ya_hecho = marcador.exists() and marcador.read_text().strip() == inicio.isoformat()
        if ya_hecho and not a.forzar:
            print(f"El reporte del {tipo} de esta ventana ya se generó.")
            return 0
    else:
        tipo = a.tipo
    credenciales = (entorno.get("GMAIL_USER"), entorno.get("GMAIL_APP_PASSWORD"))
    destino = entorno.get("CORREO_DESTINO")
    avisar = bool(all(credenciales) and destino and not a.sin_correo)
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
    except TemporadaTerminada as e:
        print(f"Sin reporte: {e}.")
        return 0
    except Exception as e:  # noqa: BLE001 — cualquier falla avisa; nunca en silencio
        traceback.print_exc()
        if avisar:
            _avisar(enviar_fn, credenciales, destino, "Fantasy: reporte NO generado",
                    f"{type(e).__name__}: {e}", None)
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
    if marcador is not None:
        marcador.write_text(inicio.isoformat())
    print(f"Reporte escrito en {archivo}")
    if avisar:
        enlace = entorno.get("PAGES_URL", "").rstrip("/") + f"/reportes/{nombre}"
        titulo = f"Fantasy · semana {reporte.semana} · {tipo}"
        _avisar(enviar_fn, credenciales, destino, titulo, correo.resumen(reporte), enlace)
    return 0


def _avisar(enviar_fn, credenciales, destino, titulo, cuerpo, enlace) -> None:
    """El correo es un extra: si falla, el reporte igual se publica."""
    try:
        enviar_fn(credenciales, destino, titulo, cuerpo, enlace)
    except Exception as e:  # noqa: BLE001 — el correo nunca bloquea la publicación
        print(f"AVISO: no se pudo mandar el correo: {e}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
