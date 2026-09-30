"""Histórico para entrenar el modelo: 2023–2024. 2025 está sellada (validación final)."""

import gzip
import json
from pathlib import Path

from fantasy.ingesta.espn import LECTURA, obtener_json

TEMPORADAS_ENTRENAMIENTO = (2023, 2024)
SELLADA = 2025
CAMPOS_JUGADOR = ("id", "fullName", "defaultPositionId", "proTeamId")
CAMPOS_STAT = ("seasonId", "scoringPeriodId", "statSourceId", "statSplitTypeId", "appliedTotal")
NFLVERSE = ("semanal", "snaps", "jugadores")


def _no_sellada(temporada: int) -> None:
    if temporada >= SELLADA:
        raise ValueError(f"{temporada}: 2025 está sellada para la validación final (decisión 20)")


def bajar_espn_historico(temporada: int, *, get=obtener_json) -> dict:
    _no_sellada(temporada)
    crudo = get(f"{LECTURA}/{temporada}/segments/0/leaguedefaults/3?view=kona_player_info",
                {"players": {"filterSlotIds": {"value": [0, 2, 4, 6]}, "limit": 1500,
                             "sortPercOwned": {"sortPriority": 1, "sortAsc": False}}})
    jugadores = []
    for pe in crudo.get("players", []):
        p = pe["player"]
        stats = [{k: s.get(k) for k in CAMPOS_STAT} for s in p.get("stats") or []
                 if s.get("seasonId") == temporada and s.get("statSplitTypeId") == 1
                 and s.get("statSourceId") in (0, 1)]
        jugadores.append({"id": pe["id"],
                          "player": {**{k: p.get(k) for k in CAMPOS_JUGADOR}, "stats": stats}})
    return {"players": jugadores}


def guardar_historico(raiz: Path, temporada: int, espn: dict, nflverse: dict[str, str]) -> None:
    _no_sellada(temporada)
    raiz.mkdir(parents=True, exist_ok=True)
    (raiz / f"espn_{temporada}.json.gz").write_bytes(
        gzip.compress(json.dumps(espn, ensure_ascii=False).encode("utf-8")))
    for nombre in NFLVERSE:
        (raiz / f"nflverse_{temporada}_{nombre}.csv.gz").write_bytes(
            gzip.compress(nflverse[nombre].encode("utf-8")))


def cargar_historico(raiz: Path, temporada: int) -> dict:
    _no_sellada(temporada)
    datos = {"proyecciones": json.loads(
        gzip.decompress((raiz / f"espn_{temporada}.json.gz").read_bytes()))}
    for nombre in NFLVERSE:
        datos[nombre] = gzip.decompress(
            (raiz / f"nflverse_{temporada}_{nombre}.csv.gz").read_bytes()).decode("utf-8")
    return datos
