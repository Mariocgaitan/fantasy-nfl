"""¿Ya pasó el modelo la validación? (decisiones 19 y 23).

Solo manda el archivo de modelo exacto que se validó: su huella (sha256) tiene que
coincidir con la que guardó la validación."""

import hashlib
import json
from pathlib import Path

FUENTES = (("2025.json", "2025 sellada"), ("2026_vivo.json", "2026 en vivo"))


def huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def estado_validacion(raiz: Path, ruta_modelo: Path | None = None) -> dict:
    for archivo, fuente in FUENTES:
        ruta = raiz / archivo
        if not ruta.exists():
            continue
        try:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if datos.get("paso") is not True:
            continue
        if ruta_modelo is not None and (
                not ruta_modelo.exists() or huella(ruta_modelo) != datos.get("sha256")):
            continue  # el modelo en uso no es el que se validó
        return {"manda": True, "fuente": fuente, "k": float(datos.get("k", 1.0))}
    return {"manda": False, "fuente": None, "k": 1.0}
