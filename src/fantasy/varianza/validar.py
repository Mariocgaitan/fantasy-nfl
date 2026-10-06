"""Criterio de la probabilidad de ganar (decisión 25) y su corrida única sobre 2025."""

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from fantasy.modelo.estado import huella
from fantasy.varianza import artefacto, ligas

RESULTADO = "2025_pganar.json"
REGISTRO = "registro_pganar.json"
N_BOOT = 10_000
MIN_TRAMO = 100
TOLERANCIA = 0.05


def criterio(res: pd.DataFrame, semilla: int = 0, n_boot: int = N_BOOT) -> dict:
    d = res.assign(delta=res.gana_pg - res.gana_esp)
    por_semana = d.groupby("semana").delta.agg(["sum", "size"])
    rng = np.random.default_rng(semilla)
    idx = rng.integers(0, len(por_semana), size=(n_boot, len(por_semana)))
    sumas, tamanos = por_semana["sum"].to_numpy(), por_semana["size"].to_numpy()
    boot = sumas[idx].sum(axis=1) / tamanos[idx].sum(axis=1)
    bajo, alto = (float(x) for x in np.percentile(boot, [2.5, 97.5]))
    delta = float(d.delta.mean())
    tramo = np.minimum((d.p * 10).astype(int), 9)
    calibracion = [{"tramo": f"{10 * k}-{10 * k + 10}%", "n": len(g),
                    "pronostico": float(g.p.mean()), "real": float(g.gana_pg.mean())}
                   for k, g in d.groupby(tramo)]
    evaluables = [c for c in calibracion if c["n"] >= MIN_TRAMO]
    paso_2 = bool(evaluables) and all(abs(c["real"] - c["pronostico"]) < TOLERANCIA
                                      for c in evaluables)
    return {"delta": delta, "ic95": [bajo, alto], "paso_1": bool(delta > 0 and bajo > 0),
            "paso_2": paso_2, "calibracion": calibracion, "enfrentamientos": len(d),
            "cambios": int(d.cambia.sum())}


def estado(raiz: Path, ruta_artefacto: Path) -> dict:
    ruta = raiz / RESULTADO
    if not ruta.exists():
        return {"existe": False, "paso_1": False, "paso_2": False}
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"existe": True, "paso_1": False, "paso_2": False}
    if not ruta_artefacto.exists() or huella(ruta_artefacto) != datos.get("sha256"):
        return {"existe": True, "paso_1": False, "paso_2": False}
    return {"existe": True, "paso_1": datos.get("paso_1") is True,
            "paso_2": datos.get("paso_2") is True}


def validar_sellado(registro: dict, ruta_artefacto: Path, obtener_2025, destino: Path, *,
                    git_limpio, varianza_igual) -> dict:
    """Corre una sola vez. Todas las verificaciones van antes de tocar 2025."""
    if destino.exists():
        raise RuntimeError(f"la validación de la varianza ya se corrió: {destino}")
    if not git_limpio():
        raise RuntimeError("el repo tiene cambios sin commit: congela todo antes de validar")
    if not varianza_igual(registro["commit"]):
        raise RuntimeError("src/fantasy/varianza cambió desde el registro: vuelve a registrar")
    if huella(ruta_artefacto) != registro["sha256"]:
        raise RuntimeError("la huella del artefacto no coincide con el registro")
    art = artefacto.cargar(ruta_artefacto)
    res = ligas.temporada(obtener_2025(), art, n_ligas=registro["ligas"],
                          n_sim=registro["n_sim"], semilla=registro["semilla"])
    salida = {**criterio(res, semilla=registro["semilla"]), "fuente": "2025 sellada",
              "sha256": registro["sha256"], "k": registro.get("k"),
              "fecha": datetime.now(UTC).isoformat()}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(salida, indent=1, ensure_ascii=False), encoding="utf-8")
    return salida
