"""Ranking de draft para CACHORRITAS LEAGUE (ESPN, 8 equipos, PPR, QB/2RB/2WR/TE/FLEX).

Idea: con 2 semanas jugadas, el USO (targets, acarreos, air yards) predice mejor
que los puntos. Se ajusta un modelo de "puntos esperados por uso" (xFP) con 2025,
se aplica a 2026 sem 1-2, y se mezcla con un prior (proyección ROS de expertos o
PPG 2025) vía shrinkage bayesiano. Luego valor sobre reemplazo (VOR) para 8 equipos.
"""
import re
import numpy as np
import pandas as pd

K_PRIOR = 3.0          # el prior pesa como 3 partidos
W_XFP = 0.7            # dentro de lo observado: 70% uso, 30% puntos reales
WEEKS_LEFT = 15        # semanas 3-17

# Proyección ROS de expertos (PPG, NFL Fantasy Edge, semana 3)
PRIOR = {
 'QB': {'Josh Allen':22.3,'Lamar Jackson':18.4,'Brock Purdy':17.9,'Jalen Hurts':17.8,'Dak Prescott':17.6,
        'Caleb Williams':17.4,'Patrick Mahomes':17.1,'Jayden Daniels':17.0,'Drake Maye':17.0,'Joe Burrow':16.9,
        'Trevor Lawrence':16.8,'Jared Goff':16.6,'Tyler Shough':16.1,'Jaxson Dart':16.1,'Justin Herbert':15.9,
        'Matthew Stafford':15.7,'Jordan Love':15.7,'Bo Nix':15.7,'Malik Willis':15.0,'Baker Mayfield':14.9},
 'RB': {'Jahmyr Gibbs':19.6,'Bijan Robinson':18.4,'Jonathan Taylor':16.6,'Christian McCaffrey':16.4,
        'Kenneth Walker':15.4,'Derrick Henry':15.3,'Ashton Jeanty':15.0,'James Cook':14.6,'Chase Brown':14.3,
        "De'Von Achane":14.0,'Omarion Hampton':13.4,"D'Andre Swift":12.9,'Saquon Barkley':12.8,'Breece Hall':12.4,
        'Javonte Williams':12.3,'David Montgomery':12.1,'Kyren Williams':12.0,'Bucky Irving':11.6,
        'Jeremiyah Love':11.6,'Travis Etienne':11.5,'Cam Skattebo':11.3,'Quinshon Judkins':10.6,
        'Bhayshul Tuten':10.0,'TreVeyon Henderson':9.7,'Jaylen Warren':9.5,'Chuba Hubbard':9.5,
        'Kyle Monangai':9.3,'Rhamondre Stevenson':9.3,'Jadarian Price':9.1,'Jordan Mason':8.7,'Rico Dowdle':8.5,
        'Tony Pollard':8.5,'J.K. Dobbins':8.3,'Jonathon Brooks':8.1,'RJ Harvey':8.0,'MarShawn Lloyd':8.0,
        'Kenneth Gainwell':7.9,'Aaron Jones':7.9,'Josh Jacobs':7.7,'Blake Corum':7.6,'Rachaad White':7.4,
        'Jacory Croskey-Merritt':7.4,'Chris Rodriguez':6.7,'Tyjae Spears':6.4,'Tyrone Tracy':5.4},
 'WR': {'Jaxon Smith-Njigba':18.0,'Amon-Ra St. Brown':17.5,'Puka Nacua':17.1,"Ja'Marr Chase":17.0,
        'CeeDee Lamb':16.3,'Nico Collins':15.0,'Justin Jefferson':14.6,'Chris Olave':14.6,'Zay Flowers':13.5,
        'DeVonta Smith':13.4,'Drake London':13.1,'Christian Watson':13.0,'George Pickens':13.0,
        'Garrett Wilson':12.8,'Ladd McConkey':12.7,'Parker Washington':12.6,'Rashee Rice':12.5,
        'Tee Higgins':12.4,'Mike Evans':12.4,'Malik Nabers':12.4,'Tetairoa McMillan':12.4,'Jaylen Waddle':12.2,
        'Emeka Egbuka':12.2,'Davante Adams':12.1,'Luther Burden':11.2,'Terry McLaurin':11.1,'Rome Odunze':11.0,
        'Jalen Coker':11.0,'Jameson Williams':10.9,'Brian Thomas':10.4,'Jayden Reed':10.0,'DJ Moore':10.0,
        'Stefon Diggs':9.9,'DK Metcalf':9.8,'Matthew Golden':9.8,'Josh Downs':9.6,'Chris Godwin':9.5,
        'Carnell Tate':9.5,'Alec Pierce':9.4,'Marvin Harrison':9.4,'Michael Pittman':9.4,'Khalil Shakir':9.3,
        'Jakobi Meyers':9.2,'Deebo Samuel':9.1,'A.J. Brown':9.1,'Michael Wilson':9.0,'Xavier Worthy':9.0,
        "Wan'Dale Robinson":9.0,'Courtland Sutton':9.0,'Romeo Doubs':8.6,'Denzel Boston':8.6,
        'Jordan Addison':8.6,'KC Concepcion':8.6,'Makai Lemon':8.5,'Quentin Johnston':8.4},
 'TE': {'Trey McBride':14.0,'Brock Bowers':12.6,'Tyler Warren':11.3,'Sam LaPorta':11.2,'Colston Loveland':10.6,
        'Travis Kelce':10.5,'Dalton Kincaid':10.4,'Isaiah Likely':9.9,'Harold Fannin':9.7,'George Kittle':9.6,
        'Dalton Schultz':9.4,'Tucker Kraft':9.3,'Jake Ferguson':9.2,'Mark Andrews':9.1,'T.J. Hockenson':8.7},
}

# Semanas que se estima pierden (de 15 restantes). Fuente: reportes de lesiones semana 3.
MISS = {'Jaxson Dart':15,'Jayden Higgins':15,'Jonathon Brooks':15,'David Njoku':8,'Charlie Kolar':8,
        'Jordan Mason':6,'A.J. Brown':6,'Jayden Daniels':5,'Dallas Goedert':3,'Caleb Williams':2,
        'J.K. Dobbins':2,'Rico Dowdle':2,'DJ Moore':2,'Alec Pierce':2,'Jayden Reed':2,'Brock Bowers':1,
        'Puka Nacua':1,'Nico Collins':1,'Zay Flowers':1,'Saquon Barkley':1,'Mike Evans':1,
        'Malik Nabers':1,'Jadarian Price':1,'RJ Harvey':1,'Michael Pittman':1}

# Titulares demandados en la liga -> nivel de reemplazo (8 equipos; FLEX ~ 4 RB / 4 WR)
REPL_RANK = {'QB': 9, 'TE': 9, 'RB': 21, 'WR': 22}


def norm(s):
    s = s.lower().replace('.', '').replace("'", '').replace('-', ' ')
    s = re.sub(r'\b(jr|sr|ii|iii|iv|v)\b', '', s)
    return re.sub(r'[^a-z ]', '', re.sub(r'\s+', ' ', s)).strip()


def fit_xfp(w25):
    """Puntos PPR esperados por uso, ajustado en 2025 semana a semana."""
    coefs = {}
    for pos, cols in {'QB': ['attempts', 'carries', 'passing_air_yards'],
                      'RB': ['carries', 'targets', 'receiving_air_yards'],
                      'WR': ['carries', 'targets', 'receiving_air_yards'],
                      'TE': ['targets', 'receiving_air_yards']}.items():
        d = w25[w25.position == pos][cols + ['fantasy_points_ppr']].fillna(0)
        X = np.c_[np.ones(len(d)), d[cols].values]
        b, *_ = np.linalg.lstsq(X, d.fantasy_points_ppr.values, rcond=None)
        pred = X @ b
        r2 = 1 - ((d.fantasy_points_ppr - pred) ** 2).sum() / ((d.fantasy_points_ppr - d.fantasy_points_ppr.mean()) ** 2).sum()
        coefs[pos] = (cols, b, r2)
    return coefs


def main():
    w25 = pd.read_csv('stats_player_week_2025.csv', low_memory=False)
    w25 = w25[w25.season_type == 'REG']
    w26 = pd.read_csv('stats_player_week_2026.csv', low_memory=False)
    snaps = pd.read_csv('snap_counts_2026.csv')

    coefs = fit_xfp(w25)
    for p, (c, b, r2) in coefs.items():
        print(f'xFP {p}: R2={r2:.2f}  ' + ', '.join(f'{n}={v:.3f}' for n, v in zip(['int'] + c, b)))

    w26 = w26[w26.position.isin(['QB', 'RB', 'WR', 'TE'])].copy()
    w26['xfp'] = 0.0
    for pos, (cols, b, _) in coefs.items():
        m = w26.position == pos
        w26.loc[m, 'xfp'] = b[0] + w26.loc[m, cols].fillna(0).values @ b[1:]

    g = w26.groupby(['player_display_name', 'position']).agg(
        team=('team', 'last'), gp=('week', 'nunique'), ppr=('fantasy_points_ppr', 'mean'),
        xfp=('xfp', 'mean'), tgt=('targets', 'mean'), car=('carries', 'mean'),
        tshare=('target_share', 'mean')).reset_index()

    snaps['k'] = snaps.player.map(norm)
    sp = snaps.groupby('k').offense_pct.mean()
    g['snap'] = g.player_display_name.map(norm).map(sp)

    # prior 2025: PPG si jugó >=6 partidos
    s25 = w25[w25.position.isin(['QB', 'RB', 'WR', 'TE'])].groupby('player_display_name').agg(
        gp25=('week', 'nunique'), ppg25=('fantasy_points_ppr', 'mean'))
    g = g.join(s25, on='player_display_name')

    expert = {norm(n): v for pos in PRIOR for n, v in PRIOR[pos].items()}
    g['k'] = g.player_display_name.map(norm)
    g['expert'] = g.k.map(expert)

    # jugadores del prior experto que no han jugado en 2026 (lesionados) -> añadirlos
    have = set(g.k)
    extra = [{'player_display_name': n, 'position': pos, 'gp': 0, 'k': norm(n), 'expert': v}
             for pos in PRIOR for n, v in PRIOR[pos].items() if norm(n) not in have]
    g = pd.concat([g, pd.DataFrame(extra)], ignore_index=True)

    # prior: experto > 2025 (encogido 15% hacia la media) > nivel bajo por posición
    low = {'QB': 12.0, 'RB': 5.0, 'WR': 5.0, 'TE': 4.0}
    ppg25 = np.where(g.gp25 >= 6, 0.85 * g.ppg25 + 0.15 * g.position.map(low), np.nan)
    g['prior'] = g.expert.fillna(pd.Series(ppg25)).fillna(g.position.map(low))

    obs = W_XFP * g.xfp.fillna(0) + (1 - W_XFP) * g.ppr.fillna(0)
    n = g.gp.fillna(0)
    g['proj'] = (K_PRIOR * g.prior + n * obs) / (K_PRIOR + n)

    miss = {norm(k): v for k, v in MISS.items()}
    g['miss'] = g.k.map(miss).fillna(0)
    g['proj_ros'] = g.proj * (WEEKS_LEFT - g.miss) / WEEKS_LEFT

    repl = {}
    for pos, r in REPL_RANK.items():
        vals = g[g.position == pos].proj_ros.sort_values(ascending=False).values
        repl[pos] = vals[r - 1]
    g['vor'] = g.proj_ros - g.position.map(repl)
    g['delta'] = g.proj - g.prior          # + = el uso real supera la expectativa
    g = g.sort_values('vor', ascending=False).reset_index(drop=True)
    g.index += 1
    g['pos_rank'] = g.groupby('position').cumcount() + 1
    print('Reemplazo:', {k: round(v, 1) for k, v in repl.items()})
    g.to_csv('ranking.csv')
    return g


if __name__ == '__main__':
    g = main()
    cols = ['player_display_name', 'position', 'pos_rank', 'team', 'gp', 'snap', 'tgt', 'car',
            'ppr', 'xfp', 'prior', 'proj_ros', 'vor', 'delta', 'miss']
    pd.set_option('display.width', 250)
    print(g[cols].head(130).round(2).to_string())
