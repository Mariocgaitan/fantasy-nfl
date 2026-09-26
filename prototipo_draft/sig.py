"""python sig.py "JG DET, BR ATL" -> nombres completos (iniciales + equipo)."""
import sys, re, pandas as pd
t = pd.read_csv('ranking2.csv')
ALIAS = {'WAS': 'WSH', 'LA': 'LAR', 'JAC': 'JAX', 'KAN': 'KC', 'GNB': 'GB', 'NWE': 'NE', 'NOR': 'NO', 'SFO': 'SF', 'TAM': 'TB', 'LVR': 'LV'}
def ini(n):
    w = [x for x in n.replace('.', '').split() if x not in ('Jr', 'Sr', 'II', 'III', 'IV', 'V')]
    return {(w[0][0] + w[1][0]).upper(), (w[0][0] + w[-1][0]).upper()} if len(w) > 1 else set()
t['ini'] = t.name.map(ini)
for tok in sys.argv[1].split(','):
    tok = tok.strip().upper()
    if not tok: continue
    parts = tok.split()
    i, tm = (parts[0], ALIAS.get(parts[1], parts[1])) if len(parts) > 1 else (tok[:2], tok[2:])
    h = t[(t.ini.map(lambda s: i[:2] in s)) & (t.team.str.startswith(tm))].sort_values('espn_rank')
    print(f'{tok:10} -> ' + (' | '.join(f'{r.name} ({r.pos}, espn#{r.espn_rank})' for r in h.head(3).itertuples()) or '??'))
