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
Quotient (voltage-graph) counting of symmetry-invariant Hamiltonian circuits.

Same question as hex_symmetric.py - how many Hamiltonian cycles of a global
hex9 layer are invariant under an isometry pi - but answered on a graph
k times smaller.  This is the classical voltage-graph correspondence:

  SETUP.  Let <pi> be cyclic of order k acting FREELY on the cells (every
  orbit has size k).  Label each cell by (orbit o, sheet j), where sheet j
  means the cell is pi^j applied to its orbit's representative.  Every
  G-edge {u, v} between different orbits projects to a quotient arc
  o(u) -> o(v) carrying a VOLTAGE d = sheet(v) - sheet(u)  (mod k); the
  reverse arc carries -d.  Distinct voltages between the same orbit pair
  are genuinely parallel arcs - keep them all.

  DOWN.  Let C be a pi-invariant Hamiltonian cycle on which pi acts as a
  rotation (it must, if k > 2; for k = 2 see CAVEAT).  Orbit-mates occupy
  positions exactly n/k apart around C, so any fundamental segment of
  n/k consecutive cells hits each orbit exactly once: C projects to a
  Hamiltonian cycle of the quotient.  Summing voltages around it gives
  m with pi^(shift) = pi^m: the lift closes into ONE cycle iff m
  generates Z_k, i.e. gcd(m, k) = 1.  (A corollary: C can never use an
  intra-orbit edge {x, pi^d x} - orbit-mates sit n/k apart, never
  adjacent, for n/k > 1.)

  UP.  Conversely a quotient Hamiltonian cycle with generator voltage m
  lifts to a single pi-invariant Hamiltonian cycle of G, and the k
  choices of starting sheet all trace the SAME cycle (it is invariant!),
  so the correspondence is a bijection:

      { pi-invariant HCs of G }  <->  { quotient HCs, voltage m: gcd(m,k)=1 }

  As ever with AddCircuit we enumerate directed circuits; reversal negates
  the voltage (k-m is a generator iff m is), so undirected = directed / 2.

  REFLECTION TYPE (k = 2 only).  An involution may instead act on a cycle
  as a free REFLECTION, whose axis crosses two edges of the form {x, pi x}
  - intra-orbit edges.  Removing those two edges splits the cycle into two
  pi-mirrored halves, each projecting to the SAME quotient Hamiltonian
  path between the two "loop-orbits" (orbits owning an intra-orbit edge).
  Conversely ANY quotient Hamiltonian path between two distinct loop-
  orbits lifts (close each end through its intra-orbit edge, mirror the
  path for the return half) - and with no voltage condition at all.  So
  for k = 2 the full count is

      invariant HCs = quotient Ham CYCLES with odd voltage   (rotation)
                    + quotient Ham PATHS between loop-orbits (reflection)

  and we count the paths with the classic trick of adding one mandatory
  virtual arc end -> start between each ordered pair of loop-orbits.
  If there are no intra-orbit edges the reflection term is zero.

The payoff: hex_symmetric.py solves an n-node model with equality
constraints; here the model has n/k nodes, so enumeration digs much
deeper for the same wall-clock.  The -w witness demonstrates the UP
direction executably: it lifts a quotient tour sheet-by-sheet back to a
full tour of G and re-verifies Hamiltonicity and invariance in G.

Usage:
    python3 hex_quotient.py                    # level 0, all symmetries
    python3 hex_quotient.py -l 1 -s c3-face -t 120 -w
"""
import argparse
import time
from math import gcd

import numpy as np
from ortools.sat.python import cp_model

from hex_hamiltonian import build_layer_graph, Counter
from hex_symmetric import SYMMETRIES, cell_permutation


def orbit_labels(pi: np.ndarray, k: int):
    """Label cells by (orbit, sheet) under the free action of <pi>.

    Returns (orbit, sheet, n_orbits, cells) where cells[o][j] is the cell
    with orbit o and sheet j.  Raises if the action is not free.
    """
    n = len(pi)
    orbit = np.full(n, -1)
    sheet = np.zeros(n, dtype=int)
    cells = []
    for s in range(n):
        if orbit[s] < 0:
            members, c = [], s
            while orbit[c] < 0:
                orbit[c] = len(cells)
                sheet[c] = len(members)
                members.append(c)
                c = int(pi[c])
            if len(members) != k:
                raise ValueError(f'orbit of cell {s} has size {len(members)}, '
                                 f'not {k}: action is not free')
            cells.append(members)
    return orbit, sheet, len(cells), cells


def quotient_arcs(n: int, adj: dict, orbit, sheet, k: int):
    """Directed quotient arcs (o1, o2, voltage), plus the loop-orbits.

    Loop-orbits are quotient nodes owning an intra-orbit G-edge {x, pi^d x};
    such edges never appear in a rotation-type tour (see docstring) so they
    are excluded from the arc set, but for k = 2 they are the permitted
    axis-crossings of reflection-type tours.
    """
    arcs, loops = set(), set()
    for u in range(n):
        for v in adj[u]:
            if u < v:
                if orbit[u] == orbit[v]:
                    loops.add(int(orbit[u]))
                    continue
                d = int(sheet[v] - sheet[u]) % k
                arcs.add((int(orbit[u]), int(orbit[v]), d))
                arcs.add((int(orbit[v]), int(orbit[u]), (k - d) % k))
    return sorted(arcs), sorted(loops)


def _solve_and_count(model, lits, label, time_limit):
    """Enumerate a quotient model; return (directed_count, exhausted, succ).

    succ is the successor map of one witness solution (or None): the used
    arc leaving each orbit, as orbit -> (next_orbit, voltage_or_'virt').
    """
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    if time_limit:
        solver.parameters.max_time_in_seconds = time_limit
    counter = Counter()
    t0 = time.time()
    status = solver.Solve(model, counter)
    dt = time.time() - t0

    if status == cp_model.INFEASIBLE:
        print(f'  {label}: INFEASIBLE - none exist ({dt:.2f}s)')
        return 0, True, None
    exhausted = status == cp_model.OPTIMAL
    qual = 'exactly' if exhausted else 'at least (time limit hit)'
    print(f'  {label}: {qual} {counter.solutions} directed '
          f'= {counter.solutions // 2} undirected ({dt:.2f}s)')

    succ = None
    if counter.solutions:
        solver2 = cp_model.CpSolver()
        if solver2.Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            succ = {o1: (o2, d) for (o1, o2, d), lit in lits.items()
                    if solver2.Value(lit)}
    return counter.solutions, exhausted, succ


def count_quotient(n: int, adj: dict, pi: np.ndarray, k: int,
                   time_limit: float | None, show_one: bool = False) -> None:
    orbit, sheet, n_orb, cells = orbit_labels(pi, k)
    arcs, loops = quotient_arcs(n, adj, orbit, sheet, k)
    generators = [m for m in range(1, k) if gcd(m, k) == 1]
    print(f'  quotient: {n_orb} orbit-nodes, {len(arcs)} directed arcs, '
          f'{len(loops)} loop-orbits (intra-orbit G-edges)')

    # --- rotation type: Hamiltonian cycle, total voltage generates Z_k ----
    model = cp_model.CpModel()
    lits = {a: model.NewBoolVar(f'{a[0]}->{a[1]}v{a[2]}') for a in arcs}
    model.AddCircuit([(o1, o2, lit) for (o1, o2, _), lit in lits.items()])
    total = model.NewIntVar(0, k * len(arcs), 'total_voltage')
    model.Add(total == sum(d * lit for (_, _, d), lit in lits.items()))
    t_mod = model.NewIntVar(0, k - 1, 'voltage_mod_k')
    model.AddModuloEquality(t_mod, total, k)
    model.AddAllowedAssignments([t_mod], [[m] for m in generators])

    tours = {}
    rot, rot_done, rot_succ = _solve_and_count(model, lits,
                                               'rotation-type', time_limit)
    if show_one and rot_succ:
        tours['rotation'] = lift_and_verify(n, adj, pi, k, cells, rot_succ)

    # --- reflection type (k = 2): Ham path between two loop-orbits --------
    refl, refl_done = 0, True
    if k == 2 and len(loops) >= 2:
        model_r = cp_model.CpModel()
        lits_r = {a: model_r.NewBoolVar(f'{a[0]}->{a[1]}v{a[2]}') for a in arcs}
        virtual = {(b, a, 'virt'): model_r.NewBoolVar(f'virt{b}->{a}')
                   for a in loops for b in loops if a != b}
        model_r.AddCircuit([(o1, o2, lit) for (o1, o2, _), lit
                            in {**lits_r, **virtual}.items()])
        model_r.Add(sum(virtual.values()) == 1)
        refl, refl_done, refl_succ = _solve_and_count(
            model_r, {**lits_r, **virtual}, 'reflection-type', time_limit)
        if show_one and refl_succ:
            tours['reflection'] = lift_and_verify(n, adj, pi, k, cells, refl_succ)
    elif k == 2:
        print('  reflection-type: 0 (no pair of loop-orbits => impossible)')

    if rot_done and refl_done:
        print(f'  TOTAL: exactly {(rot + refl) // 2} undirected invariant '
              f'Hamiltonian cycles')
    else:
        print(f'  TOTAL: at least {(rot + refl) // 2} undirected invariant '
              f'Hamiltonian cycles (incomplete)')
    return tours


def lift_and_verify(n, adj, pi, k, cells, succ):
    """Lift a quotient tour back to G and machine-check the claimed bijection.

    Rotation type: walk the quotient cycle n-1 times, accumulating sheet.
    Reflection type (marked by the one 'virt' arc b->a): lift the a->b path
    once, then append its pi-mirror reversed - the joins are exactly the two
    intra-orbit edges the reflection axis crosses.
    """
    virt = next(((o1, o2) for o1, (o2, d) in succ.items() if d == 'virt'), None)
    if virt is None:                                  # rotation type
        o, j = 0, 0
        tour = [cells[0][0]]
        for _ in range(n - 1):
            o, d = succ[o]
            j = (j + d) % k
            tour.append(cells[o][j])
    else:                                             # reflection type
        end, start = virt                             # virtual arc closes b->a
        o, j = start, 0
        path = [cells[start][0]]
        while o != end:
            o, d = succ[o]
            j = (j + d) % k
            path.append(cells[o][j])
        tour = path + [int(pi[c]) for c in reversed(path)]
    sets = {u: set(vs) for u, vs in adj.items()}
    assert len(set(tour)) == n, 'lift is not Hamiltonian'
    assert all(b in sets[a] for a, b in zip(tour, tour[1:] + [tour[0]])), \
        'lift is not a tour of G'
    edges = {frozenset(e) for e in zip(tour, tour[1:] + [tour[0]])}
    assert {frozenset((int(pi[a]), int(pi[b]))) for a, b in edges} == edges, \
        'lift is not pi-invariant'
    print(f'  witness tour (lifted to G, verified Hamiltonian + invariant): {tour}')
    return tour


def run(level: int, names: list[str], time_limit: float | None,
        witness: bool, plot: bool = False):
    n, adj, cent, polys = build_layer_graph(level, with_polys=True)
    for name in names:
        matrix = SYMMETRIES[name]
        order, m = 1, matrix.copy()
        while not np.array_equal(m, np.eye(3, dtype=m.dtype)):
            m = m @ matrix
            order += 1
        print(f'\n== {name} (order {order}) ==')
        pi, orbits = cell_permutation(cent, matrix, adj)
        if pi is None:
            print(f'  SKIPPED: {orbits}')
            continue
        try:
            tours = count_quotient(n, adj, pi, order, time_limit,
                                   show_one=witness or plot)
        except ValueError as ex:
            print(f'  SKIPPED: {ex} (use hex_symmetric.py for non-free actions)')
            continue
        if plot:
            from hex_view import plot_tour
            for kind, tour in tours.items():
                plot_tour(polys, tour, f'{name}-invariant ({kind}-type) '
                          f'Hamiltonian tour, hex9 level {level} ({n} cells)',
                          f'output/L{level}_{name}_{kind}.png')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l', '--level', type=int, default=0,
                    help='hex9 layer (12 * 9^L cells; default 0)')
    ap.add_argument('-s', '--symmetry', choices=[*SYMMETRIES, 'all'],
                    default='all', help='which isometry to enforce (default all)')
    ap.add_argument('-t', '--time-limit', type=float, default=None,
                    help='solver time limit in seconds per symmetry')
    ap.add_argument('-w', '--witness', action='store_true',
                    help='lift one quotient tour back to G and verify it')
    ap.add_argument('-p', '--plot', action='store_true',
                    help='save a figure per lifted witness tour (implies -w)')
    args = ap.parse_args()
    names = list(SYMMETRIES) if args.symmetry == 'all' else [args.symmetry]
    run(args.level, names, args.time_limit, args.witness, args.plot)
