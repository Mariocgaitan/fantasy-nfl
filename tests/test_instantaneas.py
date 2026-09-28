from datetime import datetime
from zoneinfo import ZoneInfo

from fantasy.almacen import instantaneas


def test_guardar_y_cargar_ida_y_vuelta(tmp_path):
    crudos = {"liga": {"teams": [1, 2]}, "semanal": "a,b\n1,2\n"}
    carpeta = instantaneas.guardar(tmp_path, 2026, 4, datetime(2026, 9, 29, 19, 0, tzinfo=ZoneInfo("Australia/Sydney")), crudos)
    assert carpeta == tmp_path / "instantaneas" / "2026" / "sem04" / "2026-09-29T19-00"
    assert sorted(p.name for p in carpeta.iterdir()) == ["liga.json.gz", "semanal.csv.gz"]
    assert instantaneas.cargar(carpeta) == crudos


def test_cargar_lee_fixtures_sin_comprimir(fixture_dir):
    crudos = instantaneas.cargar(fixture_dir)
    assert {"liga", "calendario", "agentes_libres", "proyecciones",
            "semanal", "snaps", "jugadores"} <= set(crudos)
    assert isinstance(crudos["semanal"], str)
