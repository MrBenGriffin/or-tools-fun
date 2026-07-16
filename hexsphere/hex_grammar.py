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
Grammar tools for the 3-pattern alphabet: door rule + self-similarity.

hex_patterns.py established (both CP-SAT proven):
  * the minimum pattern alphabet for a one-level block-recursive tour is 3,
    at L1-over-L0 AND at L2-over-L1;
  * one triple is feasible at both levels (the "universal" alphabet below);
    other optimal triples are not (L1's first optimum is infeasible at L2).

This script adds the two structural checks that turn an alphabet into a
GRAMMAR (a deterministic generator, Hilbert-style):

--rule : DOOR FUNCTIONALITY.  For each block and each (entry arc, exit
  arc) pair, how many alphabet members can realise it?  Measured result
  for the universal triple at L1: every block supports 18 door-pairs,
  each realised by EXACTLY ONE pattern via EXACTLY ONE internal path -
  'pattern = f(doors)' with no residual choice.  All per-block selection
  freedom therefore lives one level up (who hands the block its doors).

default : TWO-LEVEL SELF-SIMILARITY (the closure check).  One model over
  the level-(c+2) cells requiring simultaneously:
    - fine tour block-contiguous over level-(c+1) blocks AND over
      level-c super-blocks (81 descendants contiguous);
    - every level-(c+1) block uses an alphabet pattern (config channel);
    - the CONTRACTED level-(c+1) tour uses alphabet patterns over the
      level-c blocks, via door variables: for mid cells a,b the door
      door[a,b] = sum of fine arcs crossing between their blocks (block
      contiguity makes it 0/1), and a coarse config forces its mid-level
      path arcs as doors.
  Feasibility = there exists a curve whose every truncation, at both
  scales at once, is an alphabet tour - a genuinely self-similar
  two-level curve.  The witness is verified by independent contraction
  and re-classification at both levels.

Usage:
    python3 hex_grammar.py --rule            # door-functionality census, L1
    python3 hex_grammar.py                   # self-similarity check, c=0
    python3 hex_grammar.py -t 1800 -j 6 -p   # with time cap and figure
"""
import argparse
import time
from collections import defaultdict

import numpy as np
from ortools.sat.python import cp_model

from hex_hamiltonian import build_layer_graph
from hex_blocks import (canonical_ownership, TurnFrame, tour_patterns,
                        pattern_report, sig_str)
from hex_patterns import enumerate_configs

DIGITS = '0123456789ab'
# The level-universal alphabet (hex_patterns.py: optimal at L2-over-L1,
# feasible at L1-over-L0; L1's own first optimum does NOT extend to L2).
UNIVERSAL = ('24a84a848', '42a4a84a6', '2a64268a6')
# The PROVEN-minimum self-similar alphabet (--minimise, 240.8s): UNIVERSAL
# plus the two patterns supplying the 1-away (+-120 deg) transits.  Door-
# functional (30 = 6 entry x 5 exit door-pairs per block, one config each,
# one transit class per pattern) and turn-closed (ordinary blocks provide
# exactly the turn set {2,4,6,8,a} the patterns consume).
FIVE = UNIVERSAL + ('6246a84a6', '284a8824a')


def parse_alphabet(strs) -> set:
    return {tuple(DIGITS.index(ch) for ch in s.strip()) for s in strs}


def door_rule(coarse: int, alphabet: set):
    """Census: (block, entry arc, exit arc) -> alphabet members that fit."""
    nc, cadj, ccent, cuu = build_layer_graph(coarse, with_centroids=True,
                                             with_uuids=True)
    n, adj, cent, polys, uu = build_layer_graph(coarse + 1, with_polys=True,
                                                with_uuids=True)
    owner = canonical_ownership(uu, cuu, coarse, adj)
    frame = TurnFrame(adj, polys)
    configs, class_sigs = enumerate_configs(owner, adj, frame)

    doors = defaultdict(set)
    per_block = defaultdict(set)
    n_configs = 0
    for b, rows in configs.items():
        for u, path, y, k in rows:
            sig = class_sigs[k]
            if sig in alphabet:
                key = (b, (u, path[0]), (path[-1], y))
                doors[key].add(sig)
                per_block[b].add(key[1:])
                n_configs += 1
    multi = {k: v for k, v in doors.items() if len(v) > 1}
    pairs = sorted(len(v) for v in per_block.values())
    print(f'  alphabet supports {len(doors)} (block, door-pair) contexts over '
          f'{len(per_block)} blocks (per block: {pairs[0]}..{pairs[-1]}); '
          f'{n_configs} realising configs')
    if multi:
        print(f'  NOT door-functional: {len(multi)} contexts admit >1 pattern')
        for k, v in list(multi.items())[:8]:
            print(f'    block {k[0]} in{k[1]} out{k[2]}: '
                  f'{[sig_str(s) for s in v]}')
    else:
        uniq = ('; each context has exactly ONE realising config'
                if n_configs == len(doors) else '')
        print(f'  door-functional: pattern = f(entry, exit) everywhere{uniq}')


def handshake(coarse: int, alphabet: set):
    """Crossing handshake: is the fine door arc a pure function of the
    ordered coarse arc?

    For a fully deterministic generator, when a coarse tour steps a -> b,
    block a's config must exit through the SAME fine arc that block b's
    config enters through - regardless of a's entry side and b's exit
    side.  Sufficient (and checkable) form: over all alphabet configs,
    the set of exit arcs a uses towards b and the set of entry arcs b
    accepts from a are one identical singleton per ordered pair (a, b).
    Doubled-edge pairs (the 6 octahedron-vertex adjacencies, two shared
    coarse edges) are reported separately.
    """
    nc, adj_c, cent_c, uu_c = build_layer_graph(coarse, with_centroids=True,
                                                with_uuids=True)
    n, adj, cent, polys, uu = build_layer_graph(coarse + 1, with_polys=True,
                                                with_uuids=True)
    owner = canonical_ownership(uu, uu_c, coarse, adj)
    frame = TurnFrame(adj, polys)
    configs, class_sigs = enumerate_configs(owner, adj, frame)

    exit_by, entry_by = defaultdict(set), defaultdict(set)
    for b, rows in configs.items():
        for u, path, y, k in rows:
            if class_sigs[k] in alphabet:
                entry_by[(int(owner[u]), b)].add((u, path[0]))
                exit_by[(b, int(owner[y]))].add((path[-1], y))

    pairs = sorted(set(exit_by) | set(entry_by))
    doubled = {p for p in pairs                     # two shared coarse edges
               if len({tuple(sorted(e)) for e in exit_by[p] | entry_by[p]}) > 1
               and len(adj_c[p[0]]) < 6}
    ok = mismatch = multi = 0
    for p in pairs:
        e, n_ = exit_by[p], entry_by[p]
        if len(e) == 1 and e == n_:
            ok += 1
        elif e == n_:
            multi += 1
        else:
            mismatch += 1
            if mismatch <= 5:
                print(f'    pair {p}: exits {sorted(e)} vs entries {sorted(n_)}')
    print(f'  ordered adjacent block pairs: {len(pairs)}; '
          f'single agreed crossing: {ok}; agreed-but-multiple: {multi} '
          f'(doubled-edge pairs: {len(doubled)}); disagreeing: {mismatch}')
    if mismatch == 0 and multi == 0:
        print('  HANDSHAKE HOLDS: crossing = f(ordered coarse arc); '
              'refinement is a pure local function - the recursive '
              'generator is complete.')
    elif mismatch == 0:
        print('  handshake holds as SETS; multiple-crossing pairs need a '
              'tie-break rule (inspect whether choice correlates with '
              'entry/exit sides).')
    else:
        print('  HANDSHAKE FAILS: crossing depends on more than the coarse '
              'arc - a deterministic generator needs extra state.')


def self_similar(coarse: int, alphabet: set | None, time_limit: float | None,
                 workers: int, plot: bool):
    """Two-level closure: fine tour alphabet-valid over BOTH parent scales.

    With alphabet=None, MINIMISE the union of signature classes used at
    the two scales jointly - i.e. find the smallest self-similar alphabet
    (mid and coarse configs share one class space; a class is 'used' if
    either scale selects it).
    """
    c, m, f = coarse, coarse + 1, coarse + 2
    nc, adj_c, cent_c, uu_c = build_layer_graph(c, with_centroids=True,
                                                with_uuids=True)
    nm, adj_m, cent_m, polys_m, uu_m = build_layer_graph(m, with_polys=True,
                                                         with_uuids=True)
    n, adj, cent, polys, uu = build_layer_graph(f, with_polys=True,
                                                with_uuids=True)

    owner_fm = canonical_ownership(uu, uu_m, m, adj)      # fine -> mid block
    owner_mc = canonical_ownership(uu_m, uu_c, c, adj_m)  # mid  -> coarse
    owner_fc = np.array([owner_mc[p] for p in owner_fm])  # fine -> coarse

    frame_f = TurnFrame(adj, polys)
    frame_m = TurnFrame(adj_m, polys_m)

    cfg_m, sigs_m = enumerate_configs(owner_fm, adj, frame_f)
    cfg_c, sigs_c = enumerate_configs(owner_mc, adj_m, frame_m)
    if alphabet is not None:
        cfg_m = {b: [r for r in rows if sigs_m[r[3]] in alphabet]
                 for b, rows in cfg_m.items()}
        cfg_c = {b: [r for r in rows if sigs_c[r[3]] in alphabet]
                 for b, rows in cfg_c.items()}
        for name, cfg in (('mid', cfg_m), ('coarse', cfg_c)):
            starved = [b for b, rows in cfg.items() if not rows]
            print(f'  {name} configs after alphabet cut: '
                  f'{sum(len(v) for v in cfg.values())}'
                  + (f'; STARVED blocks {starved}' if starved else ''))
            if starved:
                return None

    # One class space across both scales (both levels produce the same
    # signature set; a class counts as used if EITHER scale selects it).
    sig_gid: dict = {}
    model = cp_model.CpModel()
    used: dict = {}

    def used_var(sig):
        k = sig_gid.setdefault(sig, len(sig_gid))
        if k not in used:
            used[k] = model.NewBoolVar(f'used{k}')
        return used[k]
    arc = {(u, v): model.NewBoolVar(f'{u}->{v}')
           for u, tails in adj.items() for v in tails}
    model.AddCircuit([(u, v, lit) for (u, v), lit in arc.items()])

    # Block contiguity at BOTH parent scales.
    for own, nb in ((owner_fm, nm), (owner_fc, nc)):
        leaving = defaultdict(list)
        for (u, v), lit in arc.items():
            if own[u] != own[v]:
                leaving[int(own[u])].append(lit)
        assert len(leaving) == nb
        for lits in leaving.values():
            model.Add(sum(lits) == 1)

    # Mid-block config selection channels onto fine arcs.
    for b, rows in cfg_m.items():
        cvars = []
        for i, (u, path, y, k) in enumerate(rows):
            cv = model.NewBoolVar(f'm{b}c{i}')
            cvars.append(cv)
            need = ([arc[(u, path[0])], arc[(path[-1], y)]]
                    + [arc[(a, bb)] for a, bb in zip(path, path[1:])])
            model.AddBoolAnd(need).OnlyEnforceIf(cv)
            if alphabet is None:
                model.AddImplication(cv, used_var(sigs_m[k]))
        model.AddExactlyOne(cvars)

    # Door variables: mid-level arc (a, b) realised by exactly one fine
    # crossing (contiguity guarantees the sum is 0 or 1).
    crossing = defaultdict(list)
    for (u, v), lit in arc.items():
        a, b = int(owner_fm[u]), int(owner_fm[v])
        if a != b:
            crossing[(a, b)].append(lit)
    door = {}
    for (a, b), lits in crossing.items():
        d = model.NewBoolVar(f'door{a}-{b}')
        model.Add(sum(lits) == d)
        door[(a, b)] = d

    # Coarse-block config selection channels onto doors: the contracted
    # mid-level tour must itself be an alphabet tour over coarse blocks.
    for b, rows in cfg_c.items():
        cvars = []
        for i, (u, path, y, k) in enumerate(rows):
            need_arcs = ([(u, path[0]), (path[-1], y)]
                         + list(zip(path, path[1:])))
            if any(aa not in door for aa in need_arcs):
                continue                       # mid arc with no fine crossing
            cv = model.NewBoolVar(f'c{b}c{i}')
            cvars.append(cv)
            model.AddBoolAnd([door[aa] for aa in need_arcs]).OnlyEnforceIf(cv)
            if alphabet is None:
                model.AddImplication(cv, used_var(sigs_c[k]))
        if not cvars:
            print(f'  coarse block {b}: no realisable config => INFEASIBLE')
            return None
        model.AddExactlyOne(cvars)

    if alphabet is None:
        model.Minimize(sum(used.values()))
        print(f'  minimising union of classes across both scales '
              f'({len(used)} candidate classes)')

    solver = cp_model.CpSolver()
    if time_limit:
        solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = workers
    t0 = time.time()
    status = solver.Solve(model)
    dt = time.time() - t0
    name = solver.StatusName(status)
    if status == cp_model.INFEASIBLE:
        print(f'  INFEASIBLE: no two-level self-similar alphabet tour ({dt:.1f}s)')
        return None
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f'  {name}: undecided within limit ({dt:.1f}s)')
        return None
    if alphabet is None:
        k_min = int(solver.ObjectiveValue())
        bound = int(solver.BestObjectiveBound())
        qual = ('PROVEN minimum' if status == cp_model.OPTIMAL
                else f'best found (proven lower bound {bound})')
        print(f'  minimum self-similar alphabet: {k_min} classes - '
              f'{qual} ({dt:.1f}s)')
        inv = {k: sig for sig, k in sig_gid.items()}
        for k, uv in used.items():
            if solver.Value(uv):
                print(f'    pattern {sig_str(inv[k])}')
    else:
        print(f'  {name}: two-level self-similar tour EXISTS ({dt:.1f}s)')

    # --- independent verification of the witness --------------------------
    succ = {u: v for (u, v), lit in arc.items() if solver.Value(lit)}
    tour, cur = [0], succ[0]
    while cur != 0:
        tour.append(cur)
        cur = succ[cur]
    pats_fm = tour_patterns(tour, owner_fm, frame_f)
    mid_tour = [int(owner_fm[c0]) for i, c0 in enumerate(tour)
                if i == 0 or owner_fm[c0] != owner_fm[tour[i - 1]]]
    if owner_fm[tour[0]] == owner_fm[tour[-1]]:    # run split by start cell
        mid_tour = mid_tour[1:]
    assert len(mid_tour) == nm and len(set(mid_tour)) == nm
    pats_mc = tour_patterns(mid_tour, owner_mc, frame_m)
    check = alphabet if alphabet is not None else set(pats_fm) | set(pats_mc)
    assert set(pats_fm) <= check, 'fine tour leaves alphabet over mid blocks'
    assert set(pats_mc) <= check, 'contracted tour leaves alphabet'
    print(f'  verified: fine tour over mid blocks uses '
          f'{sorted(sig_str(s) for s in pats_fm)};')
    print(f'  contracted mid tour over coarse blocks uses '
          f'{sorted(sig_str(s) for s in pats_mc)}')

    if plot:
        from hex_view import plot_tour
        plot_tour(polys, tour,
                  f'Self-similar 3-pattern tour, hex9 level {f} '
                  f'(alphabet-valid over levels {m} and {c} at once)',
                  f'output/L{f}_selfsimilar.png',
                  cell_groups=[int(p) for p in owner_fm])
    return tour


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('--rule', action='store_true',
                    help='door-functionality census instead of closure check')
    ap.add_argument('--minimise', action='store_true',
                    help='ignore the alphabet: find the SMALLEST class set '
                         'that is self-similar across both scales')
    ap.add_argument('--handshake', action='store_true',
                    help='crossing-handshake census (default alphabet: the '
                         'proven 5-pattern self-similar set)')
    ap.add_argument('-c', '--coarse', type=int, default=0,
                    help='coarse layer (fine is +1 for --rule, +2 for closure)')
    ap.add_argument('-a', '--alphabet', type=str, default=None,
                    help='comma-separated signatures (default: universal triple)')
    ap.add_argument('-t', '--time-limit', type=float, default=None)
    ap.add_argument('-j', '--workers', type=int, default=6,
                    help='CP-SAT parallel workers (default 6)')
    ap.add_argument('-p', '--plot', action='store_true')
    args = ap.parse_args()
    default = FIVE if args.handshake else UNIVERSAL
    alphabet = parse_alphabet(args.alphabet.split(',') if args.alphabet
                              else default)
    if args.minimise:
        alphabet = None
        print('alphabet: open (joint minimisation)')
    else:
        print(f'alphabet: {sorted(sig_str(s) for s in alphabet)}')
    if args.rule:
        door_rule(args.coarse, alphabet)
    elif args.handshake:
        handshake(args.coarse, alphabet)
    else:
        self_similar(args.coarse, alphabet, args.time_limit, args.workers,
                     args.plot)
