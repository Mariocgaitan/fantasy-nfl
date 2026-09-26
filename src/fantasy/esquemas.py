"""Columnas fijas de las tablas que se pasan entre módulos."""

import pandas as pd

PLANTILLAS = ["equipo_id", "jugador_id", "slot", "bloqueado"]
JUGADORES = [
    "jugador_id", "nombre", "pos", "equipo_nfl_id", "lesion",
    "equipo_fantasy_id", "disponibilidad", "dueno_pct", "dueno_cambio",
]
PROYECCIONES = ["jugador_id", "semana", "puntos"]
PARTIDOS = ["equipo_nfl_id", "semana", "inicio_utc", "rival_nfl_id"]
USO = ["jugador_id", "semana", "snaps_pct", "targets", "acarreos"]


class DatosInvalidos(Exception):
    """Los datos de una fuente no alcanzan para decidir."""


def validar(df: pd.DataFrame, columnas: list[str], nombre: str) -> pd.DataFrame:
    faltan = [c for c in columnas if c not in df.columns]
    if faltan:
        raise DatosInvalidos(f"{nombre}: faltan columnas {faltan}")
    return df[columnas].reset_index(drop=True)
