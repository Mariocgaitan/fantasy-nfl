"""Instantáneas: las respuestas crudas de cada corrida, comprimidas y fechadas."""

import gzip
import json
from datetime import datetime
from pathlib import Path


def guardar(raiz: Path, temporada: int, semana: int, momento: datetime,
            crudos: dict) -> Path:
    carpeta = (raiz / "instantaneas" / str(temporada) / f"sem{semana:02d}"
               / momento.strftime("%Y-%m-%dT%H-%M"))
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, valor in crudos.items():
        if isinstance(valor, str):
            (carpeta / f"{nombre}.csv.gz").write_bytes(gzip.compress(valor.encode("utf-8")))
        else:
            datos = json.dumps(valor, ensure_ascii=False).encode("utf-8")
            (carpeta / f"{nombre}.json.gz").write_bytes(gzip.compress(datos))
    return carpeta


def cargar(carpeta: Path) -> dict[str, dict | str]:
    crudos: dict[str, dict | str] = {}
    for f in sorted(carpeta.iterdir()):
        nombre = f.name
        comprimido = nombre.endswith(".gz")
        base = nombre[:-3] if comprimido else nombre
        if not base.endswith((".json", ".csv")):
            continue
        datos = f.read_bytes()
        texto = (gzip.decompress(datos) if comprimido else datos).decode("utf-8")
        if base.endswith(".json"):
            crudos[base[:-5]] = json.loads(texto)
        else:
            crudos[base[:-4]] = texto
    return crudos
