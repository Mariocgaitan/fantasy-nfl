"""Cuándo toca cada reporte (hora de Sídney) y de qué semana es."""

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

ZONA = ZoneInfo("Australia/Sydney")
REPORTES = {  # día de la semana (lunes = 0), hora local
    "martes": (1, time(19, 0)),
    "viernes": (4, time(8, 0)),
    "domingo": (6, time(20, 0)),
}
# Hasta cuándo sirve cada reporte. GitHub llega a retrasar el cron varias horas, así que el
# workflow corre cada media hora y genera el reporte pendiente mientras siga siendo útil.
VENTANAS = {
    "martes": timedelta(hours=20),   # hasta el miércoles 15:00, antes de los waivers (17:00)
    "viernes": timedelta(hours=2),   # hasta las 10:00, antes del partido del jueves (~10:15)
    "domingo": timedelta(hours=6),   # hasta las 02:00, antes de los primeros partidos (~03:00)
}


def slot_actual(ahora: datetime) -> tuple[str, datetime] | None:
    """El reporte que toca ahora y su hora de inicio (en UTC), o None."""
    local = ahora.astimezone(ZONA)
    for atras in (0, 1):
        dia = local.date() - timedelta(days=atras)
        for tipo, (dia_semana, hora) in REPORTES.items():
            if dia.weekday() != dia_semana:
                continue
            inicio = datetime.combine(dia, hora, tzinfo=ZONA)
            if inicio <= local < inicio + VENTANAS[tipo]:
                return tipo, inicio.astimezone(UTC)
    return None


def reporte_que_toca(ahora: datetime) -> str | None:
    slot = slot_actual(ahora)
    return slot[0] if slot else None


def semana_objetivo(semana_espn: int, partidos: pd.DataFrame, ahora: pd.Timestamp) -> int:
    ultimo = partidos.loc[partidos.semana == semana_espn, "inicio_utc"].max()
    return semana_espn + 1 if pd.notna(ultimo) and ultimo <= ahora else semana_espn


WAIVERS = time(17, 0)  # hora de Sídney; todos los días menos martes


def proximo_waiver(ahora: pd.Timestamp) -> pd.Timestamp:
    """El próximo proceso de waivers después de `ahora`, en UTC."""
    local = ahora.astimezone(ZONA)
    for dias in range(8):
        dia = local.date() + timedelta(days=dias)
        if dia.weekday() == 1:  # martes: no hay proceso
            continue
        cuando = datetime.combine(dia, WAIVERS, tzinfo=ZONA)
        if cuando > local:
            return pd.Timestamp(cuando.astimezone(UTC))
    raise AssertionError("siempre hay un proceso de waivers en la semana")
