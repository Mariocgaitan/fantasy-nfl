"""Asistente de draft en vivo. Uso: python draft.py

Comandos:
  x nombre   -> otro equipo se llevó a ese jugador (basta parte del nombre: 'x gibbs')
  m nombre   -> TÚ elegiste a ese jugador
  u nombre   -> deshacer (vuelve a estar disponible)
  q          -> salir
  (Enter)    -> volver a mostrar la recomendación
"""
import difflib
import json
import os
import pandas as pd

STATE = 'estado_draft.json'
NEED = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1}        # titulares fijos
MAX_USEFUL = {'QB': 1, 'TE': 1, 'RB': 6, 'WR': 6}   # en liga de 8 no hace falta QB/TE de repuesto

r = pd.read_csv('ranking.csv', index_col=0)
r = r[r.vor > -4].copy()
names = r.player_display_name.tolist()

st = {'taken': [], 'mine': []}
if os.path.exists(STATE):
    st = json.load(open(STATE))


def find(q):
    q = q.lower()
    hits = [n for n in names if q in n.lower()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        print('  Varios:', ', '.join(hits[:6]), '-> escribe más del nombre')
        return None
    close = difflib.get_close_matches(q, [n.lower() for n in names], n=1, cutoff=0.6)
    if close:
        return next(n for n in names if n.lower() == close[0])
    print('  No encontrado:', q)
    return None


def show():
    mine = r[r.player_display_name.isin(st['mine'])]
    have = mine.position.value_counts().to_dict()
    avail = r[~r.player_display_name.isin(st['taken'] + st['mine'])].copy()

    # valor ajustado a TU plantilla
    def adj(row):
        n = have.get(row.position, 0)
        if n >= MAX_USEFUL[row.position]:
            return -99                                  # no sirve
        if n >= NEED[row.position]:
            flex_ok = row.position in ('RB', 'WR') and have.get('RB', 0) + have.get('WR', 0) < 5
            return row.vor * (0.8 if flex_ok else 0.45)  # banca/flex vale menos
        return row.vor
    avail['mi_valor'] = avail.apply(adj, axis=1)
    avail = avail.sort_values('mi_valor', ascending=False)

    print('\n' + '=' * 78)
    print(f"Pick #{len(st['taken']) + len(st['mine']) + 1}  |  Tu equipo ({len(st['mine'])}/14): "
          + (', '.join(f"{n} ({mine.set_index('player_display_name').position[n]})" for n in st['mine']) or '-'))
    faltan = [f'{p}x{NEED[p] - have.get(p, 0)}' for p in NEED if have.get(p, 0) < NEED[p]]
    print('Te falta de titulares:', ', '.join(faltan) or 'nada (busca FLEX + banca)')
    print('-' * 78)
    print(f"{'':3}{'Jugador':26}{'Pos':5}{'Eq':5}{'Proy':>6}{'VOR':>6}{'Uso vs esp':>11}  Nota")
    for i, (_, x) in enumerate(avail.head(12).iterrows(), 1):
        nota = []
        if x.miss > 0:
            nota.append(f'lesión ~{int(x.miss)} sem')
        if x.delta >= 2:
            nota.append('▲ uso por encima de lo esperado')
        elif x.delta <= -1.5:
            nota.append('▼ uso por debajo')
        tag = '>>' if i == 1 else '  '
        print(f"{tag} {x.player_display_name[:25]:26}{x.position:5}{str(x.team)[:4]:5}{x.proj_ros:6.1f}"
              f"{x.mi_valor:6.1f}{x.delta:+11.1f}  {'; '.join(nota)}")
    best = avail.groupby('position').head(1).set_index('position').player_display_name.to_dict()
    print('Mejor por posición:', ' | '.join(f'{p}: {best.get(p, "-")}' for p in ['RB', 'WR', 'QB', 'TE']))


show()
while True:
    try:
        cmd = input('\n> ').strip()
    except EOFError:
        break
    if cmd == 'q':
        break
    if len(cmd) > 2 and cmd[1] == ' ' and cmd[0] in 'xmu':
        n = find(cmd[2:].strip())
        if n:
            for k in ('taken', 'mine'):
                if n in st[k]:
                    st[k].remove(n)
            if cmd[0] == 'x':
                st['taken'].append(n)
            elif cmd[0] == 'm':
                st['mine'].append(n)
            print('  ok:', n, {'x': 'tomado', 'm': 'MÍO', 'u': 'disponible'}[cmd[0]])
            json.dump(st, open(STATE, 'w'))
    show()
