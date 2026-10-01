"""Uso semanal por jugador (snaps, targets, acarreos) desde nflverse."""

import http.client
import io
import time
import urllib.error
import urllib.request

import pandas as pd

from fantasy.esquemas import USO, DatosInvalidos, validar

BASE = "https://github.com/nflverse/nflverse-data/releases/download"
ARCHIVOS = {
    "semanal": "stats_player/stats_player_week_{t}.csv",
    "snaps": "snap_counts/snap_counts_{t}.csv",
    "jugadores": "players/players.csv",
}
COLUMNAS = {
    "semanal": ["player_id", "player_display_name", "position", "team", "season", "week",
                "season_type", "carries", "targets", "receptions", "fantasy_points_ppr",
                "opponent_team", "target_share", "air_yards_share"],
    "snaps": ["season", "week", "player", "pfr_player_id", "position", "team",
              "offense_snaps", "offense_pct"],
    "jugadores": ["gsis_id", "pfr_id", "espn_id", "display_name", "position"],
}
REQUERIDAS = {  # lo que usa uso_semanal
    "semanal": ["player_id", "season_type", "week", "targets", "carries"],
    "snaps": ["week", "pfr_player_id", "offense_pct"],
    "jugadores": ["gsis_id", "pfr_id", "espn_id"],
}
POSICIONES = ["QB", "RB", "WR", "TE"]


def _leer_csv(url: str, abrir, intentos: int, espera: float, dormir) -> pd.DataFrame:
    ultimo: Exception | None = None
    for i in range(intentos):
        try:
            with abrir(url, timeout=120) as r:
                return pd.read_csv(io.BytesIO(r.read()), low_memory=False)
        except (OSError, http.client.HTTPException) as e:
            ultimo = e
        if i < intentos - 1:
            dormir(espera * 2**i)
    raise DatosInvalidos(f"nflverse: no se pudo bajar {url} tras {intentos} intentos: {ultimo}")


def bajar_nflverse(temporada: int, *, abrir=urllib.request.urlopen, intentos: int = 3,
                   espera: float = 5.0, dormir=time.sleep) -> dict[str, str]:
    crudos = {}
    for nombre, ruta in ARCHIVOS.items():
        url = f"{BASE}/{ruta.format(t=temporada)}"
        try:
            df = _leer_csv(url, abrir, intentos, espera, dormir)
        except pd.errors.ParserError as e:
            raise DatosInvalidos(f"nflverse: {nombre} no es un CSV válido: {e}") from e
        faltan = [c for c in REQUERIDAS[nombre] if c not in df.columns]
        if faltan:
            raise DatosInvalidos(f"nflverse: {nombre} ya no trae las columnas {faltan}")
        df = df[[c for c in COLUMNAS[nombre] if c in df.columns]]
        if "position" in df.columns:
            df = df[df["position"].isin(POSICIONES)]
        if nombre == "jugadores":
            df = df[df["espn_id"].notna()]
        crudos[nombre] = df.to_csv(index=False)
    return crudos


URL_JUEGOS = "https://github.com/nflverse/nfldata/raw/master/data/games.csv"
COLUMNAS_JUEGOS = ["season", "week", "gameday", "gametime", "home_team", "away_team",
                   "spread_line", "total_line"]
SELLADA = 2025


def bajar_juegos(temporadas, *, abrir=urllib.request.urlopen, permitir_sellada=False,
                 dormir=time.sleep) -> str:
    if SELLADA in temporadas and not permitir_sellada:
        raise ValueError("2025 está sellada para la validación final (decisión 20)")
    df = _leer_csv(URL_JUEGOS, abrir, 3, 5.0, dormir)
    df = df[(df["game_type"] == "REG") & df["season"].isin(temporadas)]
    return df[COLUMNAS_JUEGOS].to_csv(index=False)


def uso_extendido(semanal: pd.DataFrame, jugadores: pd.DataFrame) -> pd.DataFrame:
    ids = jugadores.dropna(subset=["espn_id"])[["gsis_id", "espn_id"]]
    s = semanal[semanal["season_type"] == "REG"].merge(ids, left_on="player_id",
                                                        right_on="gsis_id")
    s = s.rename(columns={"espn_id": "jugador_id", "week": "semana", "team": "equipo",
                          "opponent_team": "rival"})
    s[["target_share", "air_yards_share"]] = s[["target_share", "air_yards_share"]].fillna(0.0)
    s["jugador_id"] = s["jugador_id"].astype("int64")
    s["semana"] = s["semana"].astype("int64")
    return s[["jugador_id", "semana", "equipo", "rival", "target_share", "air_yards_share"]]


def uso_semanal(semanal: pd.DataFrame, snaps: pd.DataFrame,
                jugadores: pd.DataFrame) -> pd.DataFrame:
    ids = jugadores.dropna(subset=["espn_id"])
    s = semanal[semanal["season_type"] == "REG"].merge(
        ids[["gsis_id", "espn_id"]], left_on="player_id", right_on="gsis_id")
    s = s.groupby(["espn_id", "week"], as_index=False)[["targets", "carries"]].sum()
    n = snaps.merge(ids[["pfr_id", "espn_id"]], left_on="pfr_player_id", right_on="pfr_id")
    n = n.groupby(["espn_id", "week"], as_index=False)["offense_pct"].max()
    u = s.merge(n, on=["espn_id", "week"], how="outer")
    # Sin fila de snaps no es 0% de snaps: se deja vacío para no inventar subidas de rol.
    u[["targets", "carries"]] = u[["targets", "carries"]].fillna(0)
    u = u.rename(columns={"espn_id": "jugador_id", "week": "semana",
                          "offense_pct": "snaps_pct", "carries": "acarreos"})
    u["jugador_id"] = u["jugador_id"].astype("int64")
    u["semana"] = u["semana"].astype("int64")
    return validar(u, USO, "uso")


def tablas(crudos: dict[str, str]) -> pd.DataFrame:
    leer = {n: pd.read_csv(io.StringIO(crudos[n]), low_memory=False)
            for n in ("semanal", "snaps", "jugadores")}
    return uso_semanal(leer["semanal"], leer["snaps"], leer["jugadores"])
