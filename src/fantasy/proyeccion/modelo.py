"""Segunda opinión: el modelo propio para la semana en curso. Nunca decide (decisión 15)."""

import math
from pathlib import Path

from fantasy.modelo import ridge, variables


def segunda_opinion(crudos: dict, temporada: int, semana: int,
                    ruta: Path) -> tuple[dict[int, float], str | None]:
    if not ruta.exists():
        return {}, f"Sin modelo en {ruta}: no se muestra la segunda opinión."
    try:
        m = ridge.cargar(ruta)
    except (ValueError, KeyError, TypeError) as e:
        return {}, f"El modelo guardado no sirve ({e}): no se muestra la segunda opinión."
    f = variables.desde_crudos(crudos, temporada, semanas=[semana])
    if not all(k in crudos for k in ("semanal", "snaps", "jugadores")):
        return {}, "Sin uso de nflverse: no se muestra la segunda opinión del modelo."
    pred = ridge.predecir(m, f)
    return {int(j): float(p) for j, p in zip(f.jugador_id, pred, strict=True)
            if not math.isnan(p)}, None
