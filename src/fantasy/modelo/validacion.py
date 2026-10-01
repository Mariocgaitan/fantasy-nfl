"""Criterio de la decisión 19, corrida sellada de 2025 y validación en vivo de 2026."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fantasy.modelo.evaluar import resumen
from fantasy.modelo.seleccion import walk_forward_v2


def criterio(res: dict) -> bool:
    gana_global = res["delta"] < 0 and res["ic95"][1] < 0
    gana_posiciones = all(m <= e for m, e in res["por_pos"].values())
    return bool(gana_global and gana_posiciones)


def _guardar(res: dict, destino: Path, extra: dict) -> dict:
    salida = {**extra, "mae_modelo": res["mae_modelo"], "mae_espn_calibrada": res["mae_espn"],
              "delta": res["delta"], "ic95": list(res["ic95"]),
              "por_pos": {p: list(v) for p, v in res["por_pos"].items()},
              "paso": criterio(res), "fecha": datetime.now(UTC).isoformat()}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    return salida


def validar_sellado(registro, modelo_guardado, previas, obtener_2025, destino: Path,
                    git_limpio) -> dict:
    if destino.exists():
        raise RuntimeError(f"la validación sellada ya se corrió: {destino}")
    if not git_limpio():
        raise RuntimeError("el repo tiene cambios sin commit: congela todo antes de validar")
    if modelo_guardado.config != registro["config"] or modelo_guardado.k != registro["k"]:
        raise RuntimeError("el modelo guardado no coincide con el registro")
    pred = walk_forward_v2(previas, obtener_2025(), registro["config"], k=registro["k"])
    return _guardar(resumen(pred), destino, {"fuente": "2025 sellada",
                                             "config": registro["config"],
                                             "k": registro["k"],
                                             "semanas": sorted(int(s) for s in pred.semana.unique())})
