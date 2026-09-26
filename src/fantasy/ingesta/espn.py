"""Lectura de la API pública de ESPN fantasy: descarga y parsers."""

import pandas as pd

from fantasy.esquemas import (
    JUGADORES,
    PARTIDOS,
    PLANTILLAS,
    PROYECCIONES,
    DatosInvalidos,
    validar,
)

POSICIONES = {1: "QB", 2: "RB", 3: "WR", 4: "TE"}
SLOTS = {0: "QB", 2: "RB", 4: "WR", 6: "TE", 23: "FLEX", 20: "BANCA", 21: "IR"}
EQUIPOS_LIGA = 8
MAX_PLANTILLA = 15  # 14 + IR


def semana_actual(liga: dict) -> int:
    return int(liga["scoringPeriodId"])


def validar_liga(liga: dict) -> None:
    equipos = liga.get("teams") or []
    if len(equipos) != EQUIPOS_LIGA:
        raise DatosInvalidos(f"liga: {len(equipos)} equipos, se esperaban {EQUIPOS_LIGA}")
    for t in equipos:
        n = len((t.get("roster") or {}).get("entries") or [])
        if not 1 <= n <= MAX_PLANTILLA:
            raise DatosInvalidos(f"liga: el equipo {t.get('id')} tiene {n} jugadores")


def parsear_plantillas(liga: dict) -> pd.DataFrame:
    validar_liga(liga)
    filas = [
        {
            "equipo_id": t["id"],
            "jugador_id": e["playerId"],
            "slot": SLOTS.get(e["lineupSlotId"], "OTRO"),
            "bloqueado": bool(e["playerPoolEntry"].get("lineupLocked", False)),
        }
        for t in liga["teams"]
        for e in t["roster"]["entries"]
    ]
    return validar(pd.DataFrame(filas, columns=PLANTILLAS), PLANTILLAS, "plantillas")


def parsear_proyecciones(proyecciones: dict, temporada: int) -> pd.DataFrame:
    filas = [
        {"jugador_id": pe["id"], "semana": int(s["scoringPeriodId"]),
         "puntos": float(s.get("appliedTotal") or 0.0)}
        for pe in proyecciones.get("players", [])
        for s in pe["player"].get("stats") or []
        if s.get("seasonId") == temporada and s.get("statSourceId") == 1
        and s.get("statSplitTypeId") == 1 and s.get("scoringPeriodId", 0) > 0
    ]
    df = pd.DataFrame(filas, columns=PROYECCIONES)
    if df.empty:
        raise DatosInvalidos("proyecciones: ESPN no devolvió proyecciones semanales")
    return validar(df, PROYECCIONES, "proyecciones")


def _dueno_pct(jugador: dict) -> tuple[float, float]:
    o = jugador.get("ownership") or {}
    return float(o.get("percentOwned", 0.0)), float(o.get("percentChange", 0.0))


def parsear_jugadores(proyecciones: dict, liga: dict, libres: dict) -> pd.DataFrame:
    dueno: dict[int, int] = {}
    propiedad: dict[int, tuple[float, float]] = {}
    for t in liga["teams"]:
        for e in t["roster"]["entries"]:
            dueno[e["playerId"]] = t["id"]
            propiedad[e["playerId"]] = _dueno_pct(e["playerPoolEntry"]["player"])
    en_waivers = set()
    for pe in libres.get("players", []):
        propiedad.setdefault(pe["id"], _dueno_pct(pe.get("player") or {}))
        if pe.get("status") == "WAIVERS":
            en_waivers.add(pe["id"])
    filas = []
    for pe in proyecciones.get("players", []):
        p = pe["player"]
        pos = POSICIONES.get(p.get("defaultPositionId"))
        if pos is None:
            continue
        jid = pe["id"]
        equipo = dueno.get(jid, 0)
        if equipo:
            disponibilidad = "EQUIPO"
        else:
            disponibilidad = "WAIVERS" if jid in en_waivers else "LIBRE"
        pct, cambio = propiedad.get(jid, (0.0, 0.0))
        filas.append({
            "jugador_id": jid, "nombre": p.get("fullName", str(jid)), "pos": pos,
            "equipo_nfl_id": int(p.get("proTeamId") or 0),
            "lesion": p.get("injuryStatus") or "ACTIVE",
            "equipo_fantasy_id": equipo, "disponibilidad": disponibilidad,
            "dueno_pct": pct, "dueno_cambio": cambio,
        })
    df = pd.DataFrame(filas, columns=JUGADORES).drop_duplicates("jugador_id")
    return validar(df, JUGADORES, "jugadores")


def parsear_calendario(calendario: dict) -> pd.DataFrame:
    filas = []
    for t in calendario["settings"]["proTeams"]:
        if t["id"] == 0:
            continue
        for semana, juegos in (t.get("proGamesByScoringPeriod") or {}).items():
            for g in juegos:
                local = g["homeProTeamId"] == t["id"]
                filas.append({
                    "equipo_nfl_id": t["id"], "semana": int(semana),
                    "inicio_utc": pd.Timestamp(g["date"], unit="ms", tz="UTC"),
                    "rival_nfl_id": g["awayProTeamId"] if local else g["homeProTeamId"],
                })
    return validar(pd.DataFrame(filas, columns=PARTIDOS), PARTIDOS, "calendario")
