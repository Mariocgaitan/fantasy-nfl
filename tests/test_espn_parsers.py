import json

import pandas as pd
import pytest

from fantasy.esquemas import DatosInvalidos
from fantasy.ingesta import espn

WATSON, GOLDEN = 4248528, 4701936  # bloqueados: jugaron el jueves de la semana 3


def _cargar(fixture_dir, nombre):
    return json.loads((fixture_dir / nombre).read_text(encoding="utf-8"))


@pytest.fixture
def crudos(fixture_dir):
    return {n: _cargar(fixture_dir, f"{n}.json")
            for n in ("liga", "calendario", "agentes_libres", "proyecciones")}


def _id(jugadores, nombre):
    return int(jugadores.loc[jugadores.nombre == nombre, "jugador_id"].iloc[0])


def test_semana_actual(crudos):
    assert espn.semana_actual(crudos["liga"]) == 3


def test_plantillas_de_bankai(crudos):
    p = espn.parsear_plantillas(crudos["liga"])
    mia = p[p.equipo_id == 5]
    assert len(mia) == 14
    assert p.equipo_id.nunique() == 8
    assert sorted(mia.slot.value_counts().items()) == [
        ("BANCA", 7), ("FLEX", 1), ("QB", 1), ("RB", 2), ("TE", 1), ("WR", 2)]
    assert set(mia[mia.bloqueado].jugador_id) == {WATSON, GOLDEN}


def test_liga_incompleta_falla(crudos):
    liga = dict(crudos["liga"], teams=crudos["liga"]["teams"][:7])
    with pytest.raises(DatosInvalidos, match="7 equipos"):
        espn.parsear_plantillas(liga)


def test_proyecciones_semanales(crudos):
    j = espn.parsear_jugadores(crudos["proyecciones"], crudos["liga"], crudos["agentes_libres"])
    pr = espn.parsear_proyecciones(crudos["proyecciones"], 2026)
    shough = pr[pr.jugador_id == _id(j, "Tyler Shough")].set_index("semana").puntos
    assert shough[3] == pytest.approx(18.83, abs=0.01)
    assert shough[8] == 0.0  # descanso de los Saints
    assert set(range(1, 19)) <= set(shough.index)


def test_jugadores_disponibilidad_y_lesion(crudos):
    j = espn.parsear_jugadores(crudos["proyecciones"], crudos["liga"], crudos["agentes_libres"])
    fila = j[j.nombre == "Tyler Shough"].iloc[0]
    assert (fila.pos, fila.equipo_fantasy_id, fila.disponibilidad) == ("QB", 5, "EQUIPO")
    assert j[j.nombre == "Nico Collins"].iloc[0].lesion == "OUT"
    assert set(j.pos) <= {"QB", "RB", "WR", "TE"}
    assert j.jugador_id.is_unique
    libres = j[j.disponibilidad != "EQUIPO"]
    assert len(libres) > 50 and (libres.equipo_fantasy_id == 0).all()


def test_jugador_en_plantilla_y_en_libres_cuenta_como_del_equipo(crudos):
    # Review Focus 1: las dos listas se bajan en momentos distintos.
    libres = json.loads(json.dumps(crudos["agentes_libres"]))
    liga = crudos["liga"]
    entrada = liga["teams"][4]["roster"]["entries"][0]
    duplicado = {"id": entrada["playerId"], "status": "WAIVERS", "player": {"ownership": {}}}
    libres["players"].append(duplicado)
    j = espn.parsear_jugadores(crudos["proyecciones"], liga, libres)
    fila = j[j.jugador_id == entrada["playerId"]].iloc[0]
    assert fila.disponibilidad == "EQUIPO" and fila.equipo_fantasy_id == 5


def test_calendario(crudos):
    c = espn.parsear_calendario(crudos["calendario"])
    gb = c[(c.equipo_nfl_id == 9) & (c.semana == 3)].iloc[0]
    assert gb.inicio_utc == pd.Timestamp("2026-09-25 00:15", tz="UTC")
    assert c[(c.equipo_nfl_id == 18) & (c.semana == 8)].empty  # NO descansa en la 8


def test_proyecciones_sin_duplicados(crudos):
    # Revisión 1: ESPN devolvió al jugador 4430802 dos veces en un lote.
    pr = espn.parsear_proyecciones(crudos["proyecciones"], 2026)
    assert not pr.duplicated(["jugador_id", "semana"]).any()


def test_falta_un_jugador_de_plantilla_en_proyecciones_falla(crudos):
    # Revisión 1: nunca decidir en silencio sin un titular.
    proy = dict(crudos["proyecciones"])
    mio = crudos["liga"]["teams"][4]["roster"]["entries"][0]["playerId"]
    proy["players"] = [p for p in proy["players"] if p["id"] != mio]
    with pytest.raises(DatosInvalidos, match="sin proyección"):
        espn.parsear_jugadores(proy, crudos["liga"], crudos["agentes_libres"])


def test_tope_plantilla_suma_titulares_y_banca_sin_ir(fixture_dir):
    from fantasy.almacen.instantaneas import cargar
    from fantasy.ingesta import espn
    assert espn.tope_plantilla(cargar(fixture_dir)["liga"]) == 14
    assert espn.tope_plantilla({"settings": {}}) == 14  # sin datos: el de la liga
