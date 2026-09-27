"""Cuándo toca cada reporte (hora de Sídney) y de qué semana es."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

ZONA = ZoneInfo("Australia/Sydney")
REPORTES = {  # día de la semana (lunes = 0), hora local
    "martes": (1, time(19, 0)),
    "viernes": (4, time(8, 0)),
    "domingo": (6, time(20, 0)),
}
TOLERANCIA = timedelta(minutes=90)


def reporte_que_toca(ahora: datetime) -> str | None:
    local = ahora.astimezone(ZONA)
    for tipo, (dia, hora) in REPORTES.items():
        if local.weekday() != dia:
            continue
        objetivo = datetime.combine(local.date(), hora, tzinfo=ZONA)
        if objetivo <= local < objetivo + TOLERANCIA:
            return tipo
    return None


def semana_objetivo(semana_espn: int, partidos: pd.DataFrame, ahora: pd.Timestamp) -> int:
    ultimo = partidos.loc[partidos.semana == semana_espn, "inicio_utc"].max()
    return semana_espn + 1 if pd.notna(ultimo) and ultimo <= ahora else semana_espn
