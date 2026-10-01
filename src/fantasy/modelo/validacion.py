"""Criterio de la decisión 19, corrida sellada de 2025 y validación en vivo de 2026."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from fantasy.horario import ZONA
from fantasy.ingesta import espn
from fantasy.modelo import candidatos, variables
from fantasy.modelo.evaluar import relevantes, resumen
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


def _hora(carpeta: Path) -> pd.Timestamp:
    return pd.to_datetime(carpeta.name, format="%Y-%m-%dT%H-%M").tz_localize(ZONA)


def _primer_partido(carpeta: Path, semana: int) -> pd.Timestamp | None:
    cal = cargar_solo(carpeta, "calendario")
    inicios = espn.parsear_calendario(cal)
    inicios = inicios[inicios.semana == semana].inicio_utc
    return inicios.min() if len(inicios) else None


def cargar_solo(carpeta: Path, nombre: str) -> dict:
    import gzip
    import json
    return json.loads(gzip.decompress((carpeta / f"{nombre}.json.gz").read_bytes()))


def instantaneas_previas(datos: Path, temporada: int = 2026, desde: int = 5) -> dict[int, Path]:
    raiz = datos / "instantaneas" / str(temporada)
    salida = {}
    for dir_sem in sorted(raiz.glob("sem*")):
        semana = int(dir_sem.name[3:])
        if semana < desde:
            continue
        for carpeta in sorted(dir_sem.iterdir(), reverse=True):
            primero = _primer_partido(carpeta, semana)
            if primero is not None and _hora(carpeta) < primero:
                salida[semana] = carpeta
                break
    return salida


def ultima_instantanea(datos: Path, temporada: int = 2026) -> Path:
    return max((datos / "instantaneas" / str(temporada)).glob("sem*/*"), key=lambda p: p.name)


def validar_en_vivo(modelo, previas: dict, ultimo: dict, destino: Path,
                    min_semanas: int = 8) -> dict:
    reales = espn.parsear_reales(ultimo["proyecciones"], 2026)
    partes = []
    for semana, crudos in sorted(previas.items()):
        f = variables.desde_crudos_v2(crudos, 2026, [semana], equipo_desde_espn=True)
        f = f.drop(columns="real").merge(
            reales[reales.semana == semana][["jugador_id", "puntos"]].rename(
                columns={"puntos": "real"}), on="jugador_id", how="left")
        f = relevantes(f[f.real.notna()])
        if f.empty:
            continue
        partes.append(pd.DataFrame({"semana": semana, "pos": f.pos.values,
                                    "jugador_id": f.jugador_id.values, "real": f.real.values,
                                    "espn": modelo.k * f.proy_espn.values,
                                    "modelo": candidatos.predecir_v2(modelo, f).values}))
    if len(partes) < min_semanas:
        return {"semanas": len(partes), "listo": False}
    pred = pd.concat(partes, ignore_index=True)
    res = _guardar(resumen(pred), destino, {"fuente": "2026 en vivo",
                                            "semanas": sorted(int(s) for s in pred.semana.unique())})
    return {**res, "listo": True}
