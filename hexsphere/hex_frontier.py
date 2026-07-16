# Copyright 2026 Ben Griffin; All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""
hex_frontier: targeted L6 closure of the frontier row chains.

The learned row-state transducer (hex_hilbert.py --learn) is complete at
L5 except for the two FRONTIER rows (the 583... and 483... lineage
chains, 12 blocks each at L5): their outgoing T2 transitions need the
rows of their children, which live at L6.  A wholesale L6 learner run
extrapolates to ~78 GB; this script computes only what the frontier
needs:

  1. regenerate the curve to L5 (identifies the frontier blocks and the
     L5 tour context of their members),
  2. build the global L6 graph (numpy/scipy heavy but affordable; NO
     config enumeration),
  3. distil door tables for just the involved blocks - frontier members
     plus their tour neighbours - with a LOCAL TurnFrame (net_positions
     and TurnFrame.__init__ are per-cell Python loops, the two things
     that must not run globally at L6),
  4. refine each frontier member locally and translate its 9 children
     into (slot, rank) rows, matched against the known row set.

Verdict: if every child row is already known, the chains fold back and
the row FSM is CLOSED with complete T2 - saved as
output/h9curve_rowtables_L5c.pkl (same schema, frontier emptied).  Any
new row is reported with its exemplar: the chain continues to L7.
"""
import gc
import pickle
import time
from collections import defaultdict

import numpy as np

from hex_hamiltonian import build_layer_graph
from hex_hilbert import generate_with_states, label_digits, _slot
from hex_blocks import TurnFrame
from hex_patterns import block_ham_paths
from hex_curve import ALPHABET
from hex_view import net_positions

TABLES = 'output/h9curve_rowtables_L5.pkl'
L = 5                                     # frontier level; children at L+1


class LocalTurnFrame(TurnFrame):
    """TurnFrame over a cell subset: same _dir semantics, global ids.

    Only .turn/.chain_signature are used downstream and both read _dir
    alone, so the base initialiser (global net unfold - a Python loop
    per cell, hours at L6) is replaced with a compacted local one.
    """

    def __init__(self, cells, adj, polys):                  # noqa: super
        ext = sorted(set(cells) | {b for a in cells for b in adj[a]})
        loc = {g: i for i, g in enumerate(ext)}
        sub = polys[ext]
        self.polys = sub
        self.poly2, self.cent2 = net_positions(sub)
        self._dir = {}
        for a in cells:
            la = loc[a]
            for b in adj[a]:
                lb = loc[b]
                hits = [vi for vi in range(6)
                        if np.any(np.all(np.isclose(sub[la, vi], sub[lb],
                                                    atol=1e-12), axis=1))]
                tip = self.poly2[la, hits].mean(axis=0) - self.cent2[la]
                self._dir[(a, b)] = float(np.degrees(
                    np.arctan2(tip[1], tip[0])))


def main():
    with open(TABLES, 'rb') as f:
        tables = pickle.load(f)
    known = {row: c for c, row in tables['rows'].items()}
    frontier = set(tables['frontier'])
    print(f'known rows: {len(known)}; frontier: {sorted(frontier)}')

    # ---- 1. curve to L5: frontier blocks + tour context ----------------
    t0 = time.time()
    tours, layers = generate_with_states(L)
    print(f'curve generated to L{L} in {time.time() - t0:.0f}s')
    pos_c = {c: i for i, c in enumerate(tours[L - 1])}
    pos_f = {c: i for i, c in enumerate(tours[L])}
    own5 = layers[L]['owner']
    uu5, uu4 = layers[L]['uuids'], layers[L]['coarse_uuids']
    n5 = layers[L]['n']

    d5 = [label_digits(u, L) for u in uu5]
    d4 = [label_digits(u, L - 1) for u in uu4]
    row_members = defaultdict(dict)           # L4 par -> rank -> L5 cell
    rows5 = defaultdict(dict)
    for c in range(n5):
        par = int(own5[c])
        r = pos_f[c] - 9 * pos_c[par]
        rows5[par][_slot(d4[par], d5[c])] = r
        row_members[par][r] = c
    f_pars = [par for par, m in rows5.items()
              if known.get(tuple(sorted(m.items()))) in frontier]
    f_rows = {par: known[tuple(sorted(rows5[par].items()))] for par in f_pars}
    print(f'frontier blocks found: {len(f_pars)} '
          f'({sorted(set(f_rows.values()))}); exemplar L4 digits: '
          + ' '.join(sorted(d4[p] for p in f_pars)[:4]) + ' ...')

    tour5, m5 = tours[L], len(tours[L])
    members = sorted({c for par in f_pars for c in row_members[par].values()})
    ctx = {}                                  # member -> (prev, next) L5 cells
    for c in members:
        i = pos_f[c]
        ctx[c] = (tour5[i - 1], tour5[(i + 1) % m5])
    needed = set(members) | {b for pn in ctx.values() for b in pn}
    print(f'blocks needing L6 configs: {len(needed)} '
          f'({len(members)} members + tour neighbours)')

    keep_d5 = {c: d5[c] for c in members}
    keep_u5 = list(uu5)                       # index -> uuid (cmap below)
    del tours, layers, rows5, d5, d4, pos_c
    gc.collect()

    # ---- 2. global L6 graph (no configs) --------------------------------
    t0 = time.time()
    n6, adj6, cent6, polys6, uu6 = build_layer_graph(
        L + 1, with_polys=True, with_uuids=True)
    print(f'L6 graph built in {time.time() - t0:.0f}s')

    t0 = time.time()
    from hhg9.h9 import uuid_address as ua
    anc = ua.h9_cell_ancestor(uu6, L)
    cmap5 = {u: i for i, u in enumerate(keep_u5)}
    owner6 = np.fromiter((cmap5[a] for a in anc), dtype=np.int64, count=n6)
    del anc
    gc.collect()
    print(f'L6 ownership in {time.time() - t0:.0f}s')

    # ---- 3. local door tables -------------------------------------------
    t0 = time.time()
    need_arr = np.fromiter(sorted(needed), dtype=np.int64)
    sel = np.flatnonzero(np.isin(owner6, need_arr))
    blocks6 = defaultdict(list)
    for c6 in sel:
        blocks6[int(owner6[c6])].append(int(c6))
    assert all(len(v) == 9 for v in blocks6.values())
    cells6 = [c for b in needed for c in blocks6[b]]
    frame = LocalTurnFrame(cells6, adj6, polys6)
    print(f'local TurnFrame over {len(cells6)} cells '
          f'in {time.time() - t0:.0f}s')

    t0 = time.time()
    table = defaultdict(dict)
    exits, entries = defaultdict(set), defaultdict(set)
    for b in sorted(needed):
        mem = blocks6[b]
        mset = set(mem)
        for path in block_ham_paths(mem, adj6):
            v, x = path[0], path[-1]
            for u in (u for u in adj6[v] if u not in mset):
                for y in (y for y in adj6[x] if y not in mset):
                    if frame.chain_signature([u] + path + [y]) not in ALPHABET:
                        continue
                    key = ((u, path[0]), (path[-1], y))
                    assert key not in table[b], f'door {key} not unique @ {b}'
                    table[b][key] = path
                    entries[(int(owner6[u]), b)].add(key[0])
                    exits[(b, int(owner6[y]))].add(key[1])
    crossing = {}
    for pair in set(exits) & set(entries):
        e, n_ = exits[pair], entries[pair]
        assert e == n_, f'handshake broken at {pair}: {e} vs {n_}'
        assert len(e) in (1, 2)
        crossing[pair] = min(e)               # canonical-edge tie-break
    print(f'door tables for {len(needed)} blocks in {time.time() - t0:.0f}s; '
          f'{len(crossing)} crossings')

    # ---- 4. refine frontier members, classify child rows ----------------
    new_rows, t2_new = {}, defaultdict(dict)  # frontier row -> rank -> child
    for par in f_pars:
        fid = f_rows[par]
        for r, c in sorted(row_members[par].items()):
            prev, nxt = ctx[c]
            key = (crossing[(prev, c)], crossing[(c, nxt)])
            assert key in table[c], f'no path for member {c} doors {key}'
            path = table[c][key]
            d_par = keep_d5[c]
            row = tuple(sorted(
                (_slot(d_par, label_digits(uu6[c6], L + 1)), i)
                for i, c6 in enumerate(path)))
            cid = known.get(row)
            if cid is None:
                cid = new_rows.setdefault(row, len(known) + len(new_rows))
            if r in t2_new[fid]:
                assert t2_new[fid][r] == cid, \
                    f'T2 disagreement at ({fid},{r}): ' \
                    f'{t2_new[fid][r]} vs {cid} (block {par})'
            t2_new[fid][r] = cid

    for fid in sorted(t2_new):
        line = ' '.join(f'{r}>{t2_new[fid][r]}' for r in sorted(t2_new[fid]))
        print(f'row {fid} T2: [{line}]')
    if new_rows:
        print(f'NEW rows discovered at L{L + 1}: {sorted(new_rows.values())} '
              f'- the chain continues (next stop L{L + 2})')
        for row, cid in new_rows.items():
            print(f'  row {cid}: {row}')
    else:
        print(f'ALL child rows known - chains fold back: row FSM CLOSED '
              f'at {len(known)} states, T2 complete')
        for fid in t2_new:
            for r, cid in t2_new[fid].items():
                tables['T2'][(fid, r)] = cid
        tables['frontier'] = []
        holes = sum(1 for c in tables['rows'] for r in range(9)
                    if (c, r) not in tables['T2'])
        assert holes == 0, f'{holes} T2 holes remain'
        out = 'output/h9curve_rowtables_L5c.pkl'
        with open(out, 'wb') as f:
            pickle.dump(tables, f)
        print(f'closed tables saved: {out} '
              f'({len(tables["T2"])} T2 entries, 0 holes)')


if __name__ == '__main__':
    main()
