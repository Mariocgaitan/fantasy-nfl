"""Segunda opinión: el modelo propio para la semana en curso. Nunca decide (decisión 15),
así que tampoco puede bloquear el reporte: cualquier falla se vuelve un aviso."""

import math
from pathlib import Path

from fantasy.modelo import candidatos, ridge, variables


def segunda_opinion(crudos: dict, temporada: int, semana: int,
                    ruta: Path) -> tuple[dict[int, float], str | None]:
    if not ruta.exists():
        return {}, f"Sin modelo en {ruta}: no se muestra la segunda opinión."
    if not all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        return {}, "Sin uso de nflverse: no se muestra la segunda opinión del modelo."
    v2 = ruta.suffix == ".joblib"
    if v2 and "juegos" not in crudos:
        return {}, "Sin líneas de apuestas: no se muestra la segunda opinión del modelo."
    try:
        if v2:
            m = candidatos.cargar_v2(ruta)
            f = variables.desde_crudos_v2(crudos, temporada, [semana], equipo_desde_espn=True)
            pred = candidatos.predecir_v2(m, f)
        else:
            m = ridge.cargar(ruta)
            f = variables.desde_crudos(crudos, temporada, semanas=[semana])
            pred = ridge.predecir(m, f)
    except Exception as e:  # noqa: BLE001 — el modelo nunca bloquea el reporte
        return {}, f"El modelo no se pudo aplicar ({type(e).__name__}: {e}): sin segunda opinión."
    # Si ESPN lo proyecta en 0 (descansa o no juega), el modelo no tiene nada que opinar.
    return {int(j): float(p) for j, p, e in zip(f.jugador_id, pred, f.proy_espn, strict=True)
            if e > 0 and not math.isnan(p)}, None


prediccion_modelo = segunda_opinion
