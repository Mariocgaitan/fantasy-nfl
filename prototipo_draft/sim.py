"""Recomendador en vivo con simulación Monte Carlo de los rivales.

Uso: python sim.py            (lee estado.json: {"slot": 3, "taken": [...], "mine": [...]})
Rivales: eligen por "puntaje de comportamiento" = 0.6*log(ADP) + 0.4*log(rank ESPN) + ruido,
con límites de posición razonables (máx 1 QB y 1 TE antes de la ronda 9, 2 después).
"""
import json
import sys
import difflib
import numpy as np
import pandas as pd

TEAMS, ROUNDS, NSIM, NOISE = 8, 14, 2000, 0.40
NEED = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1}
MAX_USEFUL = {'QB': 1, 'TE': 1, 'RB': 6, 'WR': 6}

t = pd.read_csv('ranking2.csv')
t = t[(t.vor > -60) | (t.espn_rank < 160)].reset_index(drop=True)
adp = t.adp.where(t.adp > 0, t.espn_rank.astype(float)).fillna(300)
t['beh'] = 0.6 * np.log(adp.clip(1, 300)) + 0.4 * np.log(t.espn_rank.clip(1, 400))


def resolve(names):
    out, bad = [], []
    for q in names:
        ql = q.lower()
        hits = [n for n in t.name if ql == n.lower()] or [n for n in t.name if ql in n.lower()]
        if len(hits) != 1:
            c = difflib.get_close_matches(ql, [n.lower() for n in t.name], n=1, cutoff=0.6)
            hits = [n for n in t.name if c and n.lower() == c[0]] if len(hits) != 1 else hits
        (out.append(hits[0]) if len(hits) == 1 else bad.append(q))
    return out, bad


def pick_order(slot):
    order = []
    for r in range(ROUNDS):
        seq = range(1, TEAMS + 1) if r % 2 == 0 else range(TEAMS, 0, -1)
        order += list(seq)
    return order                                        # order[i] = equipo que elige en el pick i+1


def main():
    st = json.load(open('estado.json'))
    slot = st['slot']
    taken, b1 = resolve(st.get('taken', []))
    mine, b2 = resolve(st.get('mine', []))
    if b1 + b2:
        print('NO RECONOCIDOS:', b1 + b2)
    order = pick_order(slot)
    cur = len(taken) + len(mine)                        # picks hechos
    my_next = [i for i in range(cur, len(order)) if order[i] == slot]
    if not my_next:
        print('Draft terminado para ti.'); return
    now = my_next[0]
    nxt = my_next[1] if len(my_next) > 1 else None
    nxt2 = my_next[2] if len(my_next) > 2 else None

    gone = set(taken) | set(mine)
    avail = t[~t.name.isin(gone)].reset_index(drop=True)

    # --- simulación: picks de rivales entre ahora y mis próximos dos turnos ---
    rng = np.random.default_rng(0)
    surv0 = np.zeros(len(avail)); surv1 = np.zeros(len(avail)); surv2 = np.zeros(len(avail))
    rival_picks = [order[i] for i in range(cur, now)]   # picks antes de MI turno actual
    between1 = [order[i] for i in range(now + 1, nxt)] if nxt else []
    between2 = [order[i] for i in range(nxt + 1, nxt2)] if nxt2 else []
    pos = avail.pos.values
    for s in range(NSIM):
        score = avail.beh.values + rng.normal(0, NOISE, len(avail))
        alive = np.ones(len(avail), bool)
        cnt = {}
        def rival_pick(team, rnd):
            lim = 1 if rnd < 9 else 2
            for j in np.argsort(np.where(alive, score, np.inf)):
                p = pos[j]
                if p in ('QB', 'TE') and cnt.get((team, p), 0) >= lim:
                    continue
                alive[j] = False; cnt[(team, p)] = cnt.get((team, p), 0) + 1
                return
        for i, team in zip(range(cur, now), rival_picks):
            rival_pick(team, i // TEAMS + 1)
        surv0 += alive                                   # disponibles cuando me toca ahora
        # asumo que yo tomo al mejor por VOR disponible (aprox.), no altera mucho
        for i, team in zip(range(now + 1, nxt or now + 1), between1):
            rival_pick(team, i // TEAMS + 1)
        surv1 += alive
        for i, team in zip(range(nxt + 1 if nxt else 0, nxt2 or 0), between2):
            rival_pick(team, i // TEAMS + 1)
        surv2 += alive
    avail['p_ahora'] = surv0 / NSIM
    avail['p_sig'] = surv1 / NSIM
    avail['p_sig2'] = surv2 / NSIM

    have = t[t.name.isin(mine)].pos.value_counts().to_dict()
    def adj(r):
        n = have.get(r.pos, 0)
        if n >= MAX_USEFUL[r.pos]:
            return -999
        if n >= NEED[r.pos]:
            flex_open = r.pos in ('RB', 'WR') and have.get('RB', 0) + have.get('WR', 0) < 5
            return r.vor * (0.75 if flex_open else 0.35)
        return r.vor
    avail['mi_vor'] = avail.apply(adj, axis=1)
    # urgencia: valor que se pierde si espero = mi_vor * P(que se lo lleven antes de mi siguiente)
    avail['urgencia'] = avail.mi_vor * (1 - avail.p_sig)

    print(f"\nPick global #{cur + 1}. Tu turno: #{now + 1}"
          + (f"  (faltan {now - cur} picks rivales)" if now > cur else "  <<< TE TOCA >>>")
          + (f" | siguiente tuyo: #{nxt + 1}" if nxt else ''))
    print('Tu equipo:', ', '.join(f'{n} ({t.set_index("name").pos[n]})' for n in mine) or '-')
    faltan = [f'{p}x{NEED[p] - have.get(p, 0)}' for p in NEED if have.get(p, 0) < NEED[p]]
    print('Faltan titulares:', ', '.join(faltan) or 'ninguno')
    cols = ['name', 'pos', 'team', 'inj', 'bye', 'espn_rank', 'pg', 'mi_vor', 'p_ahora', 'p_sig', 'p_sig2', 'urgencia']
    top = avail[(avail.mi_vor > -999) & (avail.p_ahora > 0.05)].sort_values('mi_vor', ascending=False).head(15)
    pd.set_option('display.width', 200)
    print(top[cols].round(2).to_string(index=False))
    print('\nMás urgentes (valor que perderías si esperas):')
    print(avail.sort_values('urgencia', ascending=False).head(6)[['name', 'pos', 'mi_vor', 'p_sig', 'urgencia']].round(2).to_string(index=False))
    print('\nPuedes esperar (buen valor, P(sigue vivo en tu siguiente turno) > 70%):')
    wait = avail[(avail.p_sig > 0.7) & (avail.mi_vor > 0)].sort_values('mi_vor', ascending=False).head(6)
    print(wait[['name', 'pos', 'mi_vor', 'p_sig', 'p_sig2']].round(2).to_string(index=False))


if __name__ == '__main__':
    main()
