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
Pattern-minimal block-recursive Hamiltonian circuits - the grammar search.

hex_blocks.py showed that an UNCONSTRAINED block-recursive tour is pattern-
diverse (11 distinct block patterns across 12 blocks at L1).  A finite-rule
space-filling curve needs the opposite: as few distinct in-block patterns
as possible.  This script finds the minimum.

Model (block-level configuration selection):

  CONFIGS.  For each canonical 9-block, enumerate every possible traversal
  configuration: an entry door arc u->v (u outside, v inside), a
  Hamiltonian path of the block from v to some x, and an exit door arc
  x->y.  Each config has a canonical turn-signature (hex_blocks.TurnFrame:
  turns at all 9 cells including the door edges, canonical up to rotation/
  reflection/reversal).

  CHANNELING.  On top of the usual AddCircuit + one-arc-leaves-each-block
  model, each block selects exactly one config; the selected config forces
  its 10 arcs true.  AddCircuit gives every cell exactly one outgoing arc,
  so the selected config IS the block's actual traversal (sound), and any
  block-contiguous tour restricts to some enumerated config per block
  (complete - the enumeration is exhaustive).

  OBJECTIVE.  used[k] = 1 if any block selects a config of signature class
  k; minimize sum(used).  The optimum is the minimum size of a "pattern
  alphabet" for a one-level recursive tour - the zone-level analogue of
  the d-cell arc-type question (there: no 1-type grammar, 6-type system
  exists).

Usage:
    python3 hex_patterns.py                 # L1 over L0, no time limit
    python3 hex_patterns.py -t 300 -p       # 5 min cap + figure
"""
import argparse
import time
from collections import defaultdict

import numpy as np
from ortools.sat.python import cp_model

from hex_hamiltonian import build_layer_graph
from hex_blocks import canonical_ownership, TurnFrame, pattern_report, sig_str


def block_ham_paths(members: list[int], adj: dict) -> list[list[int]]:
    """All directed Hamiltonian paths of the block's induced subgraph."""
    mset = set(members)
    inner = {c: [v for v in adj[c] if v in mset] for c in members}
    paths = []

    def dfs(cur, path):
        if len(path) == len(members):
            paths.append(path.copy())
            return
        for nxt in inner[cur]:
            if nxt not in path_set:
                path_set.add(nxt)
                path.append(nxt)
                dfs(nxt, path)
                path.pop()
                path_set.remove(nxt)

    for start in members:
        path_set = {start}
        dfs(start, [start])
    return paths


def enumerate_configs(owner: np.ndarray, adj: dict, frame: TurnFrame,
                      keep: set | None = None):
    """Per block: list of (entry u, path v..x, exit y, signature class id).

    Returns (configs, class_sigs) where configs[b] is a list of
    (u, path, y, class_id) and class_sigs maps class_id -> signature.
    With *keep*, only configs whose signature is in that set are stored -
    signatures are still computed for every candidate, but memory stays
    proportional to the kept set (necessary at L4+, ~6M raw configs).
    """
    blocks = defaultdict(list)
    for c, p in enumerate(owner):
        blocks[int(p)].append(c)

    class_ids, class_sigs = {}, []
    configs = {}
    n_paths = []
    for b, members in sorted(blocks.items()):
        mset = set(members)
        paths = block_ham_paths(members, adj)
        n_paths.append(len(paths))
        rows = []
        for path in paths:
            v, x = path[0], path[-1]
            outs_v = [u for u in adj[v] if u not in mset]
            outs_x = [y for y in adj[x] if y not in mset]
            for u in outs_v:
                for y in outs_x:
                    sig = frame.chain_signature([u] + path + [y])
                    if keep is not None and sig not in keep:
                        continue
                    k = class_ids.setdefault(sig, len(class_ids))
                    if k == len(class_sigs):
                        class_sigs.append(sig)
                    rows.append((u, path, y, k))
        configs[b] = rows
    print(f'  configs: {sum(len(v) for v in configs.values())} total over '
          f'{len(configs)} blocks (Ham paths/block: min {min(n_paths)}, '
          f'max {max(n_paths)}); {len(class_sigs)} distinct signature classes')
    return configs, class_sigs


def minimise_patterns(n: int, adj: dict, owner: np.ndarray, frame: TurnFrame,
                      time_limit: float | None, workers: int = 6,
                      alphabet: list[tuple] | None = None):
    """Minimise distinct patterns; with *alphabet*, restrict configs to those
    signature classes first (feasibility of a GIVEN pattern alphabet)."""
    configs, class_sigs = enumerate_configs(owner, adj, frame)
    if alphabet is not None:
        allowed = {sig for sig in alphabet}
        configs = {b: [r for r in rows if class_sigs[r[3]] in allowed]
                   for b, rows in configs.items()}
        starved = [b for b, rows in configs.items() if not rows]
        print(f'  alphabet restriction: {len(allowed)} classes allowed; '
              f'configs left: {sum(len(v) for v in configs.values())}'
              + (f'; blocks with NO config: {starved} => INFEASIBLE'
                 if starved else ''))
        if starved:
            return None

    model = cp_model.CpModel()
    arc = {(u, v): model.NewBoolVar(f'{u}->{v}')
           for u, tails in adj.items() for v in tails}
    model.AddCircuit([(u, v, lit) for (u, v), lit in arc.items()])
    leaving = defaultdict(list)
    for (u, v), lit in arc.items():
        if owner[u] != owner[v]:
            leaving[int(owner[u])].append(lit)
    for lits in leaving.values():
        model.Add(sum(lits) == 1)

    used = [model.NewBoolVar(f'used{k}') for k in range(len(class_sigs))]
    for b, rows in configs.items():
        cvars = []
        for i, (u, path, y, k) in enumerate(rows):
            cv = model.NewBoolVar(f'b{b}c{i}')
            cvars.append(cv)
            arcs_needed = ([arc[(u, path[0])], arc[(path[-1], y)]]
                           + [arc[(a, bb)] for a, bb in zip(path, path[1:])])
            model.AddBoolAnd(arcs_needed).OnlyEnforceIf(cv)
            model.AddImplication(cv, used[k])
        model.AddExactlyOne(cvars)
    model.Minimize(sum(used))

    solver = cp_model.CpSolver()
    if time_limit:
        solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    solver.parameters.log_search_progress = False
    t0 = time.time()
    status = solver.Solve(model)
    dt = time.time() - t0

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f'  {solver.StatusName(status)}: no solution within limit ({dt:.1f}s)')
        return None
    k_min = int(solver.ObjectiveValue())
    bound = int(solver.BestObjectiveBound())
    qual = ('PROVEN minimum' if status == cp_model.OPTIMAL
            else f'best found (proven lower bound {bound})')
    print(f'  minimum distinct block patterns: {k_min} - {qual} ({dt:.1f}s)')
    for k, u in enumerate(used):
        if solver.Value(u):
            print(f'    pattern {sig_str(class_sigs[k])}')

    succ = {u: v for (u, v), lit in arc.items() if solver.Value(lit)}
    tour, cur = [0], succ[0]
    while cur != 0:
        tour.append(cur)
        cur = succ[cur]
    return tour


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-c', '--coarse', type=int, default=0,
                    help='coarse layer L; fine layer is L+1 (default 0)')
    ap.add_argument('-t', '--time-limit', type=float, default=None,
                    help='solver time limit in seconds')
    ap.add_argument('-p', '--plot', action='store_true',
                    help='save a figure of the pattern-minimal tour')
    ap.add_argument('-j', '--workers', type=int, default=6,
                    help='CP-SAT parallel workers (default 6)')
    ap.add_argument('-a', '--alphabet', type=str, default=None,
                    help='comma-separated pattern signatures (chars 0-9ab, '
                         'e.g. from a previous run) - restrict the tour to '
                         'these classes and test feasibility')
    args = ap.parse_args()
    alphabet = None
    if args.alphabet:
        digits = '0123456789ab'
        alphabet = [tuple(digits.index(c) for c in s.strip())
                    for s in args.alphabet.split(',')]

    nc, coarse_adj, coarse_cent, coarse_uuids = build_layer_graph(
        args.coarse, with_centroids=True, with_uuids=True)
    n, adj, cent, polys, uuids = build_layer_graph(
        args.coarse + 1, with_polys=True, with_uuids=True)
    owner = canonical_ownership(uuids, coarse_uuids, args.coarse, adj)
    frame = TurnFrame(adj, polys)
    tour = minimise_patterns(n, adj, owner, frame, args.time_limit,
                             workers=args.workers, alphabet=alphabet)
    if tour is not None:
        pattern_report(tour, owner, polys, adj, frame=frame)
        if args.plot:
            from hex_view import plot_tour
            plot_tour(polys, tour,
                      f'Pattern-minimal block-recursive tour, hex9 level '
                      f'{args.coarse + 1} over level {args.coarse} blocks',
                      f'output/L{args.coarse + 1}_patterns.png',
                      cell_groups=[int(p) for p in owner])
