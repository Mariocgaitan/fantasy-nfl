"""Criterio de la decisión 19, corrida sellada de 2025 y validación en vivo de 2026."""

import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from fantasy.horario import ZONA
from fantasy.ingesta import espn
from fantasy.modelo import candidatos, variables
from fantasy.modelo.estado import huella
from fantasy.modelo.evaluar import relevantes, resumen
from fantasy.modelo.seleccion import walk_forward_v2

# Lo que necesita una instantánea para alimentar al modelo v2.
ARCHIVOS_NECESARIOS = ("calendario.json.gz", "proyecciones.json.gz", "semanal.csv.gz",
                       "snaps.csv.gz", "jugadores.csv.gz", "juegos.csv.gz")
FIN_DE_PARTIDO = timedelta(hours=4)  # margen tras el último inicio de la semana


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


def validar_sellado(registro, modelo_guardado, previas, obtener_2025, destino: Path, *,
                    git_limpio, src_igual, ruta_modelo: Path, head: str | None = None) -> dict:
    """Corre una sola vez. Todas las verificaciones van antes de tocar 2025."""
    if destino.exists():
        raise RuntimeError(f"la validación sellada ya se corrió: {destino}")
    if not git_limpio():
        raise RuntimeError("el repo tiene cambios sin commit: congela todo antes de validar")
    if not src_igual(registro["commit"]):
        raise RuntimeError("el código de src/ cambió desde el registro: vuelve a seleccionar")
    if modelo_guardado.config != registro["config"] or modelo_guardado.k != registro["k"]:
        raise RuntimeError("el modelo guardado no coincide con el registro")
    if huella(ruta_modelo) != registro["sha256"]:
        raise RuntimeError("la huella del modelo no coincide con el registro")
    pred = walk_forward_v2(previas, obtener_2025(), registro["config"], k=registro["k"])
    return _guardar(resumen(pred), destino, {
        "fuente": "2025 sellada", "config": registro["config"], "k": registro["k"],
        "sha256": registro["sha256"], "head": head,
        "semanas": sorted(int(s) for s in pred.semana.unique())})


def _hora(carpeta: Path) -> pd.Timestamp:
    return pd.to_datetime(carpeta.name, format="%Y-%m-%dT%H-%M").tz_localize(ZONA)


def cargar_solo(carpeta: Path, nombre: str) -> dict:
    return json.loads(gzip.decompress((carpeta / f"{nombre}.json.gz").read_bytes()))


def _inicios(carpeta: Path, semana: int) -> pd.Series:
    cal = espn.parsear_calendario(cargar_solo(carpeta, "calendario"))
    return cal[cal.semana == semana].inicio_utc


def _completa(carpeta: Path) -> bool:
    return all((carpeta / n).exists() for n in ARCHIVOS_NECESARIOS)


def instantaneas_previas(datos: Path, temporada: int = 2026, desde: int = 5) -> dict[int, Path]:
    """Por semana, la instantánea completa más reciente tomada antes de su primer partido."""
    raiz = datos / "instantaneas" / str(temporada)
    salida = {}
    for dir_sem in sorted(raiz.glob("sem*")):
        semana = int(dir_sem.name[3:])
        if semana < desde:
            continue
        for carpeta in sorted(dir_sem.iterdir(), reverse=True):
            if not _completa(carpeta):
                continue  # nflverse no estaba disponible en esa corrida
            inicios = _inicios(carpeta, semana)
            if len(inicios) and _hora(carpeta) < inicios.min():
                salida[semana] = carpeta
                break
    return salida


def instantanea_posterior(datos: Path, semana: int, temporada: int = 2026) -> Path | None:
    """La primera instantánea tomada después de que terminó la semana (puntos definitivos)."""
    candidatas = sorted((datos / "instantaneas" / str(temporada)).glob("sem*/*"),
                        key=lambda p: p.name)
    for carpeta in candidatas:
        if not (carpeta / "calendario.json.gz").exists():
            continue
        inicios = _inicios(carpeta, semana)
        if len(inicios) and _hora(carpeta) > inicios.max() + FIN_DE_PARTIDO:
            return carpeta
    return None


def validar_en_vivo(modelo, previas: dict, posteriores: dict, destino: Path,
                    min_semanas: int = 8) -> dict:
    """`previas`: semana → crudos de antes del partido; `posteriores`: semana → crudos de
    después de la semana. El primer resultado con 8 semanas queda congelado."""
    if destino.exists():
        guardado = json.loads(destino.read_text(encoding="utf-8"))
        return {**guardado, "listo": True, "congelado": True}
    partes = []
    for semana, crudos in sorted(previas.items()):
        if semana not in posteriores:
            continue  # la semana todavía no termina
        reales = espn.parsear_reales(posteriores[semana]["proyecciones"], 2026)
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
    res = _guardar(resumen(pred), destino, {
        "fuente": "2026 en vivo", "k": modelo.k,
        "semanas": sorted(int(s) for s in pred.semana.unique())})
    return {**res, "listo": True, "congelado": False}
