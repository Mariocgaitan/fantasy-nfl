import io
import json
import urllib.error

import pytest

from fantasy.esquemas import DatosInvalidos
from fantasy.ingesta import espn


class Respuesta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def abridor(respuestas, vistos):
    def abrir(req, timeout):
        vistos.append(req)
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return Respuesta(json.dumps(r).encode())
    return abrir


def test_reintenta_errores_de_servidor_y_manda_filtro():
    vistos = []
    err = urllib.error.HTTPError("u", 503, "caido", {}, None)
    datos = espn.obtener_json("https://x", {"a": 1}, abrir=abridor([err, {"ok": 1}], vistos),
                              dormir=lambda s: None)
    assert datos == {"ok": 1}
    assert len(vistos) == 2
    assert json.loads(vistos[0].get_header("X-fantasy-filter")) == {"a": 1}


def test_error_4xx_no_se_reintenta():
    vistos = []
    err = urllib.error.HTTPError("u", 400, "mal", {}, None)
    with pytest.raises(DatosInvalidos, match="400"):
        espn.obtener_json("https://x", abrir=abridor([err], vistos), dormir=lambda s: None)
    assert len(vistos) == 1


def test_se_rinde_tras_tres_intentos():
    err = urllib.error.URLError("sin red")
    with pytest.raises(DatosInvalidos, match="3 intentos"):
        espn.obtener_json("https://x", abrir=abridor([err, err, err], []), dormir=lambda s: None)


def test_bajar_espn_pide_proyecciones_en_lotes(fixture_dir):
    liga = json.loads((fixture_dir / "liga.json").read_text(encoding="utf-8"))
    libres = json.loads((fixture_dir / "agentes_libres.json").read_text(encoding="utf-8"))
    llamadas = []

    def get(url, filtro=None):
        llamadas.append((url, filtro))
        if "view=mTeam" in url:
            return liga
        if "proTeamSchedules" in url:
            return {"settings": {"proTeams": []}}
        if "leagues/" in url and "kona_player_info" in url:
            return libres
        ids = filtro["players"]["filterIds"]["value"]
        return {"players": [{"id": i, "player": {"stats": []}} for i in ids]}

    crudos = espn.bajar_espn(2026, 898754986, get=get)
    lotes = [f for u, f in llamadas if "leaguedefaults/3" in u]
    total = len({e["playerId"] for t in liga["teams"] for e in t["roster"]["entries"]}
                | {p["id"] for p in libres["players"]})
    assert all(len(f["players"]["filterIds"]["value"]) <= 50 for f in lotes)
    assert len(crudos["proyecciones"]["players"]) == total
    assert set(crudos) == {"liga", "calendario", "agentes_libres", "proyecciones"}


def test_corte_de_conexion_al_leer_se_reintenta_y_termina_en_datos_invalidos():
    # Revisión 1: ConnectionResetError / IncompleteRead no son URLError.
    import http.client

    errores = [ConnectionResetError("reset"), http.client.IncompleteRead(b""),
               ConnectionResetError("reset")]
    with pytest.raises(DatosInvalidos, match="3 intentos"):
        espn.obtener_json("https://x", abrir=abridor(errores, []), dormir=lambda s: None)
