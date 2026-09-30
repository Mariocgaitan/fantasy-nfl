import pathlib

import pytest

from fantasy.almacen.instantaneas import cargar
from fantasy.ingesta import espn

SEM4 = pathlib.Path(__file__).parent / "fixtures" / "sem04_2026-09-30"


@pytest.fixture(scope="module")
def c():
    return cargar(SEM4)


def _id(c, nombre):
    j = espn.parsear_jugadores(c["proyecciones"], c["liga"], c["agentes_libres"])
    return int(j.loc[j.nombre == nombre, "jugador_id"].iloc[0])


def test_reales_de_2026(c):
    r = espn.parsear_reales(c["proyecciones"], 2026)
    shough = r[r.jugador_id == _id(c, "Tyler Shough")].set_index("semana").puntos
    assert shough.round(1).to_dict() == {1: 23.2, 2: 22.4, 3: 23.8}
    assert not r.duplicated(["jugador_id", "semana"]).any()


def test_adp(c):
    adp = espn.parsear_adp(c["liga"])
    assert adp[_id(c, "Jahmyr Gibbs")] == pytest.approx(1.8, abs=0.05)
    assert adp[_id(c, "Malik Nabers")] == pytest.approx(48.3, abs=0.05)


def test_rival_de_la_semana(c):
    assert espn.rival_de(c["liga"], 5, 4) == 7
    assert espn.rival_de(c["liga"], 4, 4) == 8
    assert espn.rival_de(c["liga"], 5, 99) is None
