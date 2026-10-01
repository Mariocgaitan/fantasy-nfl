"""¿Ya pasó el modelo la validación? (decisiones 19 y 23)."""

import json
from pathlib import Path

FUENTES = (("2025.json", "2025 sellada"), ("2026_vivo.json", "2026 en vivo"))


def estado_validacion(raiz: Path) -> dict:
    for archivo, fuente in FUENTES:
        ruta = raiz / archivo
        if ruta.exists():
            try:
                if json.loads(ruta.read_text(encoding="utf-8")).get("paso") is True:
                    return {"manda": True, "fuente": fuente}
            except (ValueError, OSError):
                continue
    return {"manda": False, "fuente": None}
