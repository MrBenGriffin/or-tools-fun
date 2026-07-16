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
hex_curve: the deterministic hex9 space-filling curve.  NO SOLVER.

Generates a Hamiltonian tour of every global hex9 layer up to a target
level by pure table lookup, using the grammar proven in hex_grammar.py:

  * the FIVE-pattern alphabet (proven minimum self-similar set; one
    pattern per hexagonal transit class: adjacent x2, 1-away x2, opposite);
  * door functionality: each block realises each (entry arc, exit arc)
    context by exactly ONE alphabet config - so given its doors, a
    block's internal 9-cell path is forced;
  * the crossing handshake: the fine arc realising a coarse tour step
    a -> b is unique, except at the 6 octahedron-vertex adjacencies
    (two shared coarse edges) where both candidates are agreed by both
    sides - resolved here by the CANONICAL-EDGE convention: take the
    lexicographically smallest arc.

Algorithm (refine level k -> k+1, applied repeatedly):
    for each step (prev, cur, next) of the level-k tour:
        entry = crossing(prev, cur)      # a fine arc into cur's block
        exit  = crossing(cur, next)      # a fine arc out of cur's block
        emit table[cur][(entry, exit)]   # the unique alphabet path
Concatenation is automatically a Hamiltonian cycle of level k+1, and is
itself alphabet-valid - so refinement recurses to any depth.

The AXIOM is the lexicographically-first Hamiltonian cycle of the 12 L0
cells.  (Any L0 tour works: with all 30 door contexts supported per
block, every coarse step is refinable; alphabet-validity of the axiom is
not required - the first refinement is alphabet-valid by construction.)

Every proven property is re-verified LIVE at each level as it generates
(this is the level-invariance claim being exercised, not assumed):
Hamiltonicity + adjacency of the emitted tour, handshake agreement
(exits(a->b) == entries(a->b) as sets), door-context availability, path
uniqueness, and pattern classes a subset of FIVE.

(ortools is imported transitively for the shared config enumerator but no
model is built and no solver runs.)

Usage:
    python3 hex_curve.py                 # generate to L3 (8748 cells)
    python3 hex_curve.py -l 2 -p         # to L2, with net figure
"""
import argparse
import time
from collections import defaultdict

from hex_hamiltonian import build_layer_graph
from hex_blocks import (canonical_ownership, TurnFrame, tour_patterns,
                        sig_str)
from hex_patterns import enumerate_configs
from hex_grammar import FIVE, parse_alphabet

ALPHABET = parse_alphabet(FIVE)


def axiom_tour(adj: dict) -> list[int]:
    """Lexicographically-first Hamiltonian cycle of the coarsest layer."""
    n = len(adj)
    out = []

    def dfs(path, visited):
        if out:
            return
        if len(path) == n:
            if path[0] in adj[path[-1]]:
                out.extend(path)
            return
        for nxt in adj[path[-1]]:                    # adj lists are sorted
            if nxt not in visited:
                visited.add(nxt)
                path.append(nxt)
                dfs(path, visited)
                path.pop()
                visited.remove(nxt)

    dfs([0], {0})
    assert out, 'no Hamiltonian cycle at the axiom level'
    return out


def rule_tables(owner, adj, frame):
    """Distil the grammar tables for one refinement step.

    Returns (table, crossing) where
      table[block][(entry_arc, exit_arc)] = the unique alphabet path, and
      crossing[(a, b)] = the fine arc realising coarse step a -> b
    (canonical-edge convention at doubled adjacencies).  The handshake
    and uniqueness are re-verified while building.
    """
    cfg, class_sigs = enumerate_configs(owner, adj, frame, keep=ALPHABET)
    table = defaultdict(dict)
    exits, entries = defaultdict(set), defaultdict(set)
    for b, rows in cfg.items():
        for u, path, y, k in rows:
            if class_sigs[k] in ALPHABET:
                e_arc, x_arc = (u, path[0]), (path[-1], y)
                key = (e_arc, x_arc)
                assert key not in table[b], \
                    f'door context {key} of block {b} is not unique'
                table[b][key] = path
                entries[(int(owner[u]), b)].add(e_arc)
                exits[(b, int(owner[y]))].add(x_arc)

    crossing = {}
    for pair in set(exits) | set(entries):
        e, n_ = exits[pair], entries[pair]
        assert e == n_, f'handshake broken at {pair}: {e} vs {n_}'
        assert len(e) in (1, 2), f'unexpected crossing count at {pair}: {e}'
        crossing[pair] = min(e)                      # canonical-edge tie-break
    return table, crossing


def refine(tour: list[int], table: dict, crossing: dict) -> list[int]:
    """One deterministic refinement step: level-k tour -> level-(k+1) tour."""
    m = len(tour)
    fine = []
    for i, cur in enumerate(tour):
        prev, nxt = tour[i - 1], tour[(i + 1) % m]
        key = (crossing[(prev, cur)], crossing[(cur, nxt)])
        assert key in table[cur], \
            f'no alphabet path for block {cur} with doors {key}'
        fine.extend(table[cur][key])
    return fine


def verify(tour: list[int], n: int, adj: dict, owner, frame) -> dict:
    """Independent checks on an emitted tour; returns the pattern census."""
    assert len(tour) == n and len(set(tour)) == n, 'not Hamiltonian'
    sets = {u: set(vs) for u, vs in adj.items()}
    assert all(b in sets[a] for a, b in zip(tour, tour[1:] + [tour[0]])), \
        'tour uses a non-adjacency'
    pats = tour_patterns(tour, owner, frame)
    assert set(pats) <= ALPHABET, 'tour leaves the alphabet'
    return pats


def generate(target: int, plot: bool):
    print(f'alphabet: {sorted(sig_str(s) for s in ALPHABET)}')
    n0, adj0 = build_layer_graph(0)
    tour = axiom_tour(adj0)
    print(f'L0 axiom tour ({len(tour)} cells): {tour}')

    for k in range(target):
        t0 = time.time()
        nc, adj_c, cent_c, uu_c = build_layer_graph(k, with_centroids=True,
                                                    with_uuids=True)
        n, adj, cent, polys, uu = build_layer_graph(k + 1, with_polys=True,
                                                    with_uuids=True)
        owner = canonical_ownership(uu, uu_c, k, adj)
        frame = TurnFrame(adj, polys)
        table, crossing = rule_tables(owner, adj, frame)
        tour = refine(tour, table, crossing)
        pats = verify(tour, n, adj, owner, frame)
        dt = time.time() - t0
        census = ', '.join(f'{sig_str(s)} x{c}'
                           for s, c in sorted(pats.items(),
                                              key=lambda kv: -kv[1]))
        print(f'L{k + 1}: {n} cells generated + verified in {dt:.1f}s '
              f'(patterns: {census})')

        if plot and k + 1 == target:
            from hex_view import plot_tour
            plot_tour(polys, tour,
                      f'hex9 space-filling curve, level {target} '
                      f'({n} cells) - deterministic 5-pattern grammar',
                      f'output/L{target}_curve.png',
                      cell_groups=[int(p) for p in owner])
    return tour


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l', '--level', type=int, default=3,
                    help='target level (12 * 9^L cells; default 3)')
    ap.add_argument('-p', '--plot', action='store_true',
                    help='save a net figure of the finest tour')
    args = ap.parse_args()
    generate(args.level, args.plot)
