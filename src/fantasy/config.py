"""Constantes de la liga CACHORRITAS."""

from pathlib import Path

TEMPORADA = 2026
LIGA_ID = 898754986
EQUIPO_ID = 5  # BanKAI
SEMANA_FINAL = 17  # última semana de playoffs de la liga
RUTA_MODELO = Path("modelos/modelo_v1.json")
RUTA_MODELO_V2 = Path("modelos/modelo_v2.joblib")
RUTA_VALIDACION = Path("validacion")
UMBRAL_DISCREPA = 3.0  # puntos entre modelo y ESPN para marcar ⚑
