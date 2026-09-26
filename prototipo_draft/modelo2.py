"""v2: ESPN (proyección semanal, lesiones, ranking de la sala) + rol real sem 1-2 + expertos.

Por jugador:
  prior_pg  = promedio de proyección ESPN (sem 3-17, sin byes) y proyección experta NFE si existe
  rol_pg    = puntos esperados por USO en 2026 (targets, acarreos, air yards) -> señal de rol
  pg        = (K*prior_pg + n*rol_pg) / (K + n)      shrinkage: el prior pesa como K partidos
  ajustes   = QB titular fuera (NYG, WAS, CHI) para sus receptores
  juegos    = semanas 3-17 menos bye menos semanas lesionado
  VOR       = (pg - reemplazo_pg) * juegos           valor total sobre lo que hay en agencia libre
  prob. de que otros lo tomen: modelo sobre el ranking ESPN que ven tus amigos
"""
import json
import numpy as np
import pandas as pd
from modelo import fit_xfp, norm, PRIOR, MISS

K = 4.0
WEEKS = range(3, 18)
POS = {1: 'QB', 2: 'RB', 3: 'WR', 4: 'TE'}
TEAM = {1:'ATL',2:'BUF',3:'CHI',4:'CIN',5:'CLE',6:'DAL',7:'DEN',8:'DET',9:'GB',10:'TEN',11:'IND',12:'KC',
        13:'LV',14:'LAR',15:'MIA',16:'MIN',17:'NE',18:'NO',19:'NYG',20:'NYJ',21:'PHI',22:'ARI',23:'PIT',
        24:'LAC',25:'SF',26:'SEA',27:'TB',28:'WSH',29:'CAR',30:'JAX',33:'BAL',34:'HOU'}
# QB titular fuera -> multiplicador para WR/TE (y leve a RB) de ese equipo
QB_OUT = {'NYG': 0.88, 'WSH': 0.92, 'CHI': 0.96}
IGNORE_ROLE = ['Drake London', 'Kyle Pitts', 'Darnell Mooney']
CTX_MULT = {'Dalton Schultz': 0.90,          # sem 2 inflada por ausencia de Nico Collins
            'Saquon Barkley': 0.85,          # stinger + MRI, Bigsby/Shipley reparten
            'C.J. Stroud': 0.97}
REPL_RANK = {'QB': 9, 'TE': 9, 'RB': 21, 'WR': 22}


def espn_table():
    d = json.load(open('espn.json'))['players']
    rows = []
    for e in d:
        p = e['player']
        pos = POS.get(p.get('defaultPositionId'))
        if not pos:
            continue
        wk = {s['scoringPeriodId']: s.get('appliedTotal', 0) for s in p.get('stats', [])
              if s.get('statSourceId') == 1 and s.get('statSplitTypeId') == 1 and s.get('seasonId') == 2026}
        rows.append(dict(name=p['fullName'], pos=pos, team=TEAM.get(p['proTeamId'], '?'),
                         espn_rank=p['draftRanksByRankType'].get('PPR', {}).get('rank', 999),
                         adp=(e.get('ownership') or p.get('ownership') or {}).get('averageDraftPosition'),
                         inj=p.get('injuryStatus', 'ACTIVE'),
                         outlook=p.get('outlooks', {}).get('outlooksByWeek', {}).get('3', ''),
                         **{f'w{w}': wk.get(w, np.nan) for w in range(1, 19)}))
    return pd.DataFrame(rows)


def main():
    t = espn_table()
    t['k'] = t.name.map(norm)
    # bye: semana donde (casi) todo el equipo proyecta 0
    wcols = [f'w{w}' for w in WEEKS]
    z = t[wcols].fillna(0).eq(0).groupby(t.team).mean()
    bye = {team: int(z.loc[team].idxmax()[1:]) for team in z.index if z.loc[team].max() > 0.6}
    t['bye'] = t.team.map(bye)

    # proyección ESPN por partido jugado (ignora byes y semanas en 0 por lesión)
    pw = t[wcols].where(t[wcols] > 0)
    t['espn_pg'] = pw.mean(axis=1)
    t['espn_games'] = pw.notna().sum(axis=1)

    # rol real 2026
    w25 = pd.read_csv('stats_player_week_2025.csv', low_memory=False)
    w25 = w25[w25.season_type == 'REG']
    w26 = pd.read_csv('stats_player_week_2026.csv', low_memory=False)
    w26 = w26[w26.position.isin(['QB', 'RB', 'WR', 'TE'])].copy()
    coefs = fit_xfp(w25)
    w26['xfp'] = 0.0
    for pos, (cols, b, _) in coefs.items():
        m = w26.position == pos
        w26.loc[m, 'xfp'] = b[0] + w26.loc[m, cols].fillna(0).values @ b[1:]
    g = w26.groupby('player_display_name').agg(gp=('week', 'nunique'), pts=('fantasy_points_ppr', 'mean'),
                                               rol=('xfp', 'mean'), tgt=('targets', 'mean'),
                                               car=('carries', 'mean'), tsh=('target_share', 'mean'))
    g.index = g.index.map(norm)
    g = g[~g.index.duplicated()]
    t = t.join(g, on='k')
    snaps = pd.read_csv('snap_counts_2026.csv')
    t['snap'] = t.k.map(snaps.assign(k=snaps.player.map(norm)).groupby('k').offense_pct.mean())

    expert = {norm(n): v for pos in PRIOR for n, v in PRIOR[pos].items()}
    t['nfe_pg'] = t.k.map(expert)
    t['prior_pg'] = t[['espn_pg', 'nfe_pg']].mean(axis=1)

    n = t.gp.fillna(0)
    # contexto: semanas con QB suplente no representan el rol real (ATL: Penix vuelve en sem 3)
    n = n.where(~t.k.isin([norm(x) for x in IGNORE_ROLE]), 0)
    # élite con historial largo: el prior pesa más (un mal partido no los hunde)
    kk = np.where(t.prior_pg >= 17, 2 * K, K)
    t['pg'] = (kk * t.prior_pg + n * t.rol.fillna(0)) / (kk + n)
    t.loc[t.prior_pg.isna(), 'pg'] = t.rol * n / (K + n)

    t['pg'] = t.pg * t.k.map({norm(a): b for a, b in CTX_MULT.items()}).fillna(1.0)
    mult = t.team.map(QB_OUT).fillna(1.0)
    mult = np.where(t.pos.isin(['WR', 'TE']), mult, np.where(t.pos == 'RB', 1 - (1 - mult) / 2, 1.0))
    t['pg'] = t.pg * mult

    # partidos disponibles sem 3-17
    miss_manual = t.k.map({norm(k): v for k, v in MISS.items()}).fillna(0)
    miss_espn = t.inj.map({'OUT': 1, 'DOUBTFUL': 1, 'QUESTIONABLE': 0.3,
                           'INJURY_RESERVE': 5}).fillna(0)
    t['miss'] = np.maximum(miss_manual, miss_espn)
    t['games'] = (len(WEEKS) - t.bye.between(3, 17).astype(int) - t.miss).clip(lower=0)

    repl = {p: t[t.pos == p].pg.sort_values(ascending=False).iloc[r - 1] for p, r in REPL_RANK.items()}
    t['vor'] = (t.pg - t.pos.map(repl)) * t.games
    t['vs_espn'] = t.pg - t.espn_pg          # + = mi modelo lo ve mejor que ESPN
    t = t.sort_values('vor', ascending=False).reset_index(drop=True)
    t['my_rank'] = t.index + 1
    t['pos_rank'] = t.groupby('pos').cumcount() + 1
    t['gap'] = t.espn_rank - t.my_rank       # + = los demás lo van a tomar más tarde de lo que vale
    print('Reemplazo pg:', {k: round(v, 1) for k, v in repl.items()}, ' byes:', dict(sorted(bye.items())))
    t.to_csv('ranking2.csv', index=False)
    return t


if __name__ == '__main__':
    t = main()
    pd.set_option('display.width', 260)
    c = ['my_rank', 'espn_rank', 'gap', 'name', 'pos', 'pos_rank', 'team', 'inj', 'bye', 'games', 'snap',
         'tgt', 'car', 'pts', 'rol', 'espn_pg', 'nfe_pg', 'pg', 'vor']
    print(t[c].head(120).round(2).to_string(index=False))
