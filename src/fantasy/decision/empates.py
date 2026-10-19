"""Decisiones parejas de la alineación: cuándo el titular y su mejor suplente están casi
iguales, con lo que las apuestas esperan de cada equipo. Solo informa; no cambia nada."""

import io
from dataclasses import dataclass

import pandas as pd

from fantasy.decision.alineacion import FLEX_POS, Alineacion
from fantasy.modelo import contexto

UMBRAL_EMPATE = 1.0
UMBRAL_CASI = 2.0


@dataclass(frozen=True)
class Empate:
    slot: str
    titular: int
    alternativa: int
    diferencia: float
    tipo: str  # "empate" | "casi"
    pts_titular: float | None
    pts_alternativa: float | None


def pts_por_equipo(juegos_csv: str | None, calendario: dict, temporada: int,
                   semana: int) -> dict[int, float]:
    """proTeamId de ESPN → puntos que las apuestas esperan de ese equipo en la semana."""
    if juegos_csv is None:
        return {}
    juegos = pd.read_csv(io.StringIO(juegos_csv), low_memory=False)
    lin = contexto.lineas(juegos[juegos.season == temporada])
    lin = dict(zip(lin.loc[lin.semana == semana, "equipo"],
                   lin.loc[lin.semana == semana, "pts_equipo"], strict=True))
    salida = {}
    for t in calendario["settings"]["proTeams"]:
        v = lin.get(contexto.a_nflverse(t["abbrev"]))
        if v is not None and pd.notna(v):
            salida[int(t["id"])] = float(v)
    return salida


def buscar(al: Alineacion, t: pd.DataFrame, pts: dict[int, float]) -> list[Empate]:
    idx = t.set_index("jugador_id")
    banca = t[~t.jugador_id.isin(al.ids()) & ~t.bloqueado.astype(bool) & (t.esperado > 0)]
    banca = banca.sort_values("esperado", ascending=False, kind="stable")
    salida = []
    for slot, j in al.slots:
        f = idx.loc[j]
        if bool(f.bloqueado):
            continue
        cand = banca[banca.pos.isin(FLEX_POS if slot == "FLEX" else (slot,))]
        if cand.empty:
            continue
        alt = cand.iloc[0]
        d = round(abs(float(f.esperado) - float(alt.esperado)), 2)
        if d > UMBRAL_CASI:
            continue
        salida.append(Empate(
            slot, int(j), int(alt.jugador_id), d,
            "empate" if d <= UMBRAL_EMPATE else "casi",
            pts.get(int(f.equipo_nfl_id)), pts.get(int(alt.equipo_nfl_id))))
    return salida
