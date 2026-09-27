"""Probabilidad de jugar según el estado de lesión de ESPN (valores sin validar)."""

P_JUGAR = {
    "ACTIVE": 1.0, "QUESTIONABLE": 0.75, "DOUBTFUL": 0.25, "DAY_TO_DAY": 0.5,
    "OUT": 0.0, "INJURY_RESERVE": 0.0, "SUSPENSION": 0.0,
}
DESCONOCIDO = 0.5


def p_jugar(estado: str | None) -> float:
    return P_JUGAR.get(estado or "ACTIVE", DESCONOCIDO)
