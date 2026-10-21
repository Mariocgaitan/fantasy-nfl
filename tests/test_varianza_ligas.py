import numpy as np
import pandas as pd

from fantasy.varianza import ligas
from tests.varianza_util import art_prueba


def _pool(rng, n=200):
    pos = rng.choice(["QB", "RB", "WR", "TE"], n, p=[0.15, 0.35, 0.35, 0.15])
    return pd.DataFrame({"jugador_id": np.arange(n), "pos": pos, "valor": rng.uniform(1, 25, n)})


def test_draft_respeta_topes_y_titulares():
    rng = np.random.default_rng(0)
    equipos = ligas.draft(_pool(rng), rng)
    pos = _pool(np.random.default_rng(0)).set_index("jugador_id").pos
    assert len(equipos) == 8 and all(len(e) == 14 for e in equipos)
    assert len({j for e in equipos for j in e}) == 8 * 14
    for e in equipos:
        c = pos.loc[e].value_counts()
        assert c.get("QB", 0) <= 3 and c.get("RB", 0) <= 6 and c.get("TE", 0) <= 3
        assert c.get("QB", 0) >= 1 and c.get("RB", 0) >= 2 and c.get("WR", 0) >= 2
        assert c.get("TE", 0) >= 1


def _temporada_falsa(rng):
    pool = _pool(rng)
    filas = []
    for w in range(1, 6):
        for r in pool.itertuples():
            filas.append({"jugador_id": r.jugador_id, "semana": w, "pos": r.pos,
                          "proy_espn": r.valor, "real": r.valor + rng.normal(0, 8),
                          "equipo": f"T{r.jugador_id % 32}", "rush_share": 0.0,
                          "snap_pct": 0.8, "target_share": 0.1, "rel_depth": 1.0,
                          "eficiencia": 1.0})
    return pd.DataFrame(filas)


def test_temporada_produce_un_resultado_por_equipo_y_semana():
    rng = np.random.default_rng(1)
    res = ligas.temporada(_temporada_falsa(rng), art_prueba(), n_ligas=2,
                          semanas=range(3, 5), n_sim=500)
    assert len(res) == 2 * 2 * 8
    assert res.p.between(0, 1).all()
    assert set(res.gana_pg.unique()) <= {0.0, 0.5, 1.0}
    assert (res.gana_pg[~res.cambia] == res.gana_esp[~res.cambia]).all()
