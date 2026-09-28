import json
from datetime import UTC, datetime

import pandas as pd
import pytest

from fantasy.horario import reporte_que_toca, semana_objetivo
from fantasy.ingesta.espn import parsear_calendario


def utc(s):
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


@pytest.mark.parametrize("momento,esperado", [
    ("2026-09-29T09:00", "martes"),    # 19:00 AEST
    ("2026-09-29T08:00", None),        # 18:00 AEST: todavía no
    ("2026-10-06T08:00", "martes"),    # 19:00 AEDT (después del 4-oct)
    ("2026-10-06T09:00", "martes"),    # 20:00 AEDT: dentro de la tolerancia
    ("2026-10-06T10:31", None),        # 21:31: fuera de la tolerancia
    ("2026-10-01T22:00", "viernes"),   # viernes 2-oct 08:00 AEST
    ("2026-10-04T09:00", "domingo"),   # domingo 4-oct 20:00 AEDT (primer día de verano)
    ("2026-11-03T08:00", "martes"),    # EE. UU. ya cambió de horario; Sídney no se mueve
    ("2026-09-30T09:00", None),        # miércoles
])
def test_reporte_que_toca(momento, esperado):
    assert reporte_que_toca(utc(momento)) == esperado


def test_semana_objetivo_avanza_cuando_ya_empezo_el_ultimo_partido(fixture_dir):
    # Review Focus 4
    cal = json.loads((fixture_dir / "calendario.json").read_text(encoding="utf-8"))
    p = parsear_calendario(cal)
    assert semana_objetivo(3, p, pd.Timestamp("2026-09-25 02:26", tz="UTC")) == 3
    assert semana_objetivo(3, p, pd.Timestamp("2026-09-29 09:00", tz="UTC")) == 4
    assert semana_objetivo(4, p, pd.Timestamp("2026-09-29 09:00", tz="UTC")) == 4


def test_el_cron_del_workflow_cubre_cada_reporte_dos_veces():
    # Revisión 2: si GitHub se salta un cron, tiene que haber otro dentro de la ventana.
    import re
    from datetime import timedelta
    from pathlib import Path

    yml = (Path(__file__).parents[1] / ".github" / "workflows" / "reporte.yml").read_text(
        encoding="utf-8")
    disparos = []
    for minutos, horas, dia in re.findall(r'cron: "([\d,]+) ([\d,]+) \* \* (\d)"', yml):
        for h in horas.split(","):
            for m in minutos.split(","):
                disparos.append((int(dia), int(h), int(m)))
    for semana_inicio in ("2026-09-27", "2026-10-11"):  # sin y con horario de verano
        lunes = datetime.fromisoformat(semana_inicio).replace(tzinfo=UTC) + timedelta(days=1)
        vistos: dict[str, int] = {}
        for dia_cron, h, m in disparos:  # dia_cron: 0 = domingo
            dia = lunes + timedelta(days=(dia_cron - 1) % 7)
            tipo = reporte_que_toca(dia.replace(hour=h, minute=m))
            if tipo:
                vistos[tipo] = vistos.get(tipo, 0) + 1
        assert all(vistos.get(t, 0) >= 2 for t in ("martes", "viernes", "domingo")), vistos
