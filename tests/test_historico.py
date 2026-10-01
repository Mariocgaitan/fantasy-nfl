import pytest

from fantasy.ingesta import historico


def _get_falso(url, filtro=None):
    assert "leaguedefaults/3" in url and filtro["players"]["limit"] >= 1000
    return {"players": [{"id": 1, "player": {
        "id": 1, "fullName": "A", "defaultPositionId": 3, "proTeamId": 9, "extra": "x",
        "stats": [
            {"seasonId": 2024, "scoringPeriodId": 3, "statSourceId": 1, "statSplitTypeId": 1,
             "appliedTotal": 12.5, "stats": {"53": 5}},
            {"seasonId": 2024, "scoringPeriodId": 3, "statSourceId": 0, "statSplitTypeId": 1,
             "appliedTotal": 15.0, "stats": {}},
            {"seasonId": 2024, "scoringPeriodId": 0, "statSourceId": 1, "statSplitTypeId": 0,
             "appliedTotal": 200.0, "stats": {}},
            {"seasonId": 2023, "scoringPeriodId": 3, "statSourceId": 0, "statSplitTypeId": 1,
             "appliedTotal": 1.0, "stats": {}},
        ]}}]}


def test_bajar_recorta_lo_que_no_se_usa():
    d = historico.bajar_espn_historico(2024, get=_get_falso)
    p = d["players"][0]["player"]
    assert "extra" not in p
    assert [s["statSourceId"] for s in p["stats"]] == [1, 0]
    assert all("stats" not in s for s in p["stats"])


def test_2025_esta_sellada(tmp_path):
    with pytest.raises(ValueError, match="sellada"):
        historico.bajar_espn_historico(2025, get=_get_falso)
    with pytest.raises(ValueError, match="sellada"):
        historico.cargar_historico(tmp_path, 2025)


def test_guardar_y_cargar(tmp_path):
    espn = historico.bajar_espn_historico(2024, get=_get_falso)
    historico.guardar_historico(tmp_path, 2024, espn, {"semanal": "a\n1\n", "snaps": "b\n2\n",
                                                       "jugadores": "c\n3\n", "juegos": "d\n4\n"})
    c = historico.cargar_historico(tmp_path, 2024)
    assert c["proyecciones"] == espn and c["snaps"] == "b\n2\n"
