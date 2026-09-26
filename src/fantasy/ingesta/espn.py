"""Lectura de la API pública de ESPN fantasy: descarga y parsers."""

import json
import time
import urllib.error
import urllib.request

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


LECTURA = "https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons"
AGENTE = "fantasy-nfl (github.com/Mariocgaitan/fantasy-nfl)"
LOTE = 50


def obtener_json(url, filtro=None, *, abrir=urllib.request.urlopen, intentos=3, espera=2.0,
                 dormir=time.sleep) -> dict:
    headers = {"User-Agent": AGENTE}
    if filtro is not None:
        headers["X-Fantasy-Filter"] = json.dumps(filtro)
    ultimo: Exception | None = None
    for i in range(intentos):
        try:
            with abrir(urllib.request.Request(url, headers=headers), timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise DatosInvalidos(f"ESPN respondió {e.code} en {url}") from e
            ultimo = e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            ultimo = e
        if i < intentos - 1:
            dormir(espera * 2**i)
    raise DatosInvalidos(f"ESPN no respondió tras {intentos} intentos: {ultimo}")


def bajar_espn(temporada: int, liga_id: int, *, get=obtener_json) -> dict[str, dict]:
    base = f"{LECTURA}/{temporada}/segments/0"
    liga = get(f"{base}/leagues/{liga_id}?view=mTeam&view=mRoster&view=mSettings&view=mMatchup")
    validar_liga(liga)
    calendario = get(f"{LECTURA}/{temporada}?view=proTeamSchedules_wl")
    libres = get(f"{base}/leagues/{liga_id}?view=kona_player_info", {"players": {
        "filterStatus": {"value": ["FREEAGENT", "WAIVERS"]},
        "filterSlotIds": {"value": [0, 2, 4, 6]},
        "limit": 150,
        "sortPercOwned": {"sortPriority": 1, "sortAsc": False},
    }})
    ids = sorted({e["playerId"] for t in liga["teams"] for e in t["roster"]["entries"]}
                 | {pe["id"] for pe in libres.get("players", [])})
    jugadores: list[dict] = []
    for i in range(0, len(ids), LOTE):
        filtro = {"players": {"filterIds": {"value": ids[i:i + LOTE]}}}
        jugadores += get(f"{base}/leaguedefaults/3?view=kona_player_info", filtro)["players"]
    return {"liga": liga, "calendario": calendario, "agentes_libres": libres,
            "proyecciones": {"players": jugadores}}
