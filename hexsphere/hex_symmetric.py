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
Symmetry-invariant Hamiltonian circuits on a global hex9 layer.

A HOW-TO for patterned Hamiltonians: constrain the tour's *edge set* to be
invariant under a chosen isometry of the octahedron, then count solutions.

Method (three steps, each a small addition to the plain model in
hex_hamiltonian.py):

  1. ACTION ON CELLS.  An octahedral isometry is a signed permutation
     matrix M acting on c_oct coordinates.  Map every cell centroid
     through M and match it to its nearest centroid: that permutation
     pi is the isometry's action on cells.  We then VERIFY combinatorially
     that pi is a graph automorphism (adjacency preserved) - geometry
     proposes, combinatorics disposes.  If the check fails, the candidate
     is not a symmetry of the grid at all (e.g. if the hex arrangement is
     chiral, mirrors will fail here) and we refuse to model it.

  2. EDGE VARIABLES.  AddCircuit works on directed arcs; symmetry is a
     property of the undirected edge set.  For each undirected edge {u,v}
     introduce e_uv with  e_uv == arc(u,v) + arc(v,u).  (Both arcs true
     would be a 2-cycle, impossible in a single Hamiltonian circuit with
     n > 2, so the sum never exceeds 1.)

  3. INVARIANCE.  For every edge, add  e_{u,v} == e_{pi(u),pi(v)}.
     Chaining these equalities around each edge orbit makes the edge set
     invariant under the whole cyclic group <pi>.

Theory notes (why some symmetries can never work):

  * The stabiliser of a cycle graph C_n is dihedral, so a Hamiltonian
    cycle can be invariant under a CYCLIC rotation group or a single
    reflection, but never under the full octahedral group.
  * FIXED-CELL OBSTRUCTION: if pi fixes a cell c but not c's place in the
    tour, pi must permute c's two tour-neighbours.  An involution may swap
    them; an element of order > 2 cannot act non-trivially on 2 items, and
    fixing both propagates around the tour, forcing pi = identity.  Hence
    any pi of order >= 3 with a fixed cell is INFEASIBLE a priori.  The
    solver confirms this, but we report it up front.
  * Counting: as in hex_hamiltonian.py, each undirected cycle is found
    twice (two orientations); undirected count = solutions / 2.

Usage:
    python3 hex_symmetric.py                 # level 0, all symmetries
    python3 hex_symmetric.py -l 1 -s antipodal -t 60
    python3 hex_symmetric.py -l 0 -s c4-vertex -w
"""
import argparse
import time
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree
from ortools.sat.python import cp_model

from hex_hamiltonian import build_layer_graph, Counter

# Candidate isometries of the octahedron, as matrices on c_oct coordinates.
# Vertex axes pass through octahedron vertices (+-x, +-y, +-z); face axes
# through face centroids (+-1,+-1,+-1)/sqrt(3); edge axes through edge
# midpoints.  'mirror-z' is a reflection - included deliberately: if the
# hex arrangement is chiral it will fail the automorphism check, which is
# itself a result.
SYMMETRIES = {
    'antipodal': np.array([[-1, 0, 0], [0, -1, 0], [0, 0, -1]]),   # order 2, free
    'c2-vertex': np.array([[-1, 0, 0], [0, -1, 0], [0, 0, 1]]),    # 180deg about z
    'c4-vertex': np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]),     # 90deg about z
    'c3-face':   np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]]),      # 120deg about (1,1,1)
    'c2-edge':   np.array([[0, 1, 0], [1, 0, 0], [0, 0, -1]]),     # 180deg about x=y
    'mirror-z':  np.array([[1, 0, 0], [0, 1, 0], [0, 0, -1]]),     # reflection z=0
}


def cell_permutation(cent: np.ndarray, matrix: np.ndarray, adj: dict):
    """The isometry's action on cells, verified as a graph automorphism.

    Returns (pi, orbits) or (None, reason) if the candidate is not a
    symmetry of this grid.
    """
    n = len(cent)
    dist, pi = cKDTree(cent).query(cent @ matrix.T)
    spacing = np.linalg.norm(cent[adj[0][0]] - cent[0])   # ~ one cell pitch
    if dist.max() > 0.05 * spacing:
        return None, (f'centroid images miss the grid by up to '
                      f'{dist.max():.2e} ({dist.max() / spacing:.1%} of a cell '
                      f'pitch) - not a grid symmetry')
    if len(set(pi)) != n:
        return None, 'centroid matching is not a bijection'
    for u in range(n):
        if {pi[v] for v in adj[u]} != set(adj[pi[u]]):
            return None, f'adjacency not preserved at cell {u} - not an automorphism'

    # Orbit decomposition of <pi> (cycle structure of the permutation).
    seen, orbits = np.zeros(n, bool), []
    for s in range(n):
        if not seen[s]:
            orbit, c = [], s
            while not seen[c]:
                seen[c] = True
                orbit.append(c)
                c = pi[c]
            orbits.append(orbit)
    return pi, orbits


def count_symmetric(n: int, adj: dict, pi: np.ndarray,
                    time_limit: float | None,
                    show_one: bool = False) -> list[int] | None:
    model = cp_model.CpModel()
    arc = {}                                   # (u, v) -> directed arc literal
    arcs = []
    for u, tails in adj.items():
        for v in tails:
            lit = model.NewBoolVar(f'{u}->{v}')
            arc[(u, v)] = lit
            arcs.append((u, v, lit))
    model.AddCircuit(arcs)

    # Undirected edge variables (step 2 of the how-to).
    edge = {}
    for u, tails in adj.items():
        for v in tails:
            if u < v:
                e = model.NewBoolVar(f'e{u}-{v}')
                model.Add(arc[(u, v)] + arc[(v, u)] == e)
                edge[(u, v)] = e

    # Invariance under pi (step 3): e == e_image for every edge.
    for (u, v), e in edge.items():
        iu, iv = int(pi[u]), int(pi[v])
        img = edge[(iu, iv) if iu < iv else (iv, iu)]
        if img is not e:
            model.Add(e == img)

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    if time_limit:
        solver.parameters.max_time_in_seconds = time_limit
    counter = Counter()
    t0 = time.time()
    status = solver.Solve(model, counter)
    dt = time.time() - t0

    if status == cp_model.INFEASIBLE:
        print(f'  INFEASIBLE: no invariant Hamiltonian circuit exists ({dt:.2f}s)')
        return None
    directed = counter.solutions
    qual = 'exactly' if status == cp_model.OPTIMAL else 'at least (time limit hit)'
    print(f'  {solver.StatusName(status)}: {qual} {directed} directed '
          f'= {directed // 2} undirected invariant Hamiltonian cycles ({dt:.2f}s)')

    if show_one and directed:
        solver2 = cp_model.CpSolver()
        if solver2.Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            succ = {h: t for (h, t), lit in arc.items() if solver2.Value(lit)}
            tour, cur = [0], succ[0]
            while cur != 0:
                tour.append(cur)
                cur = succ[cur]
            print(f'  witness tour: {tour}')
            return tour
    return None


def run(level: int, names: list[str], time_limit: float | None,
        witness: bool, plot: bool = False):
    n, adj, cent, polys = build_layer_graph(level, with_polys=True)
    for name in names:
        matrix = SYMMETRIES[name]
        order = 1
        m = matrix.copy()
        while not np.array_equal(m, np.eye(3, dtype=m.dtype)):
            m = m @ matrix
            order += 1
        print(f'\n== {name} (order {order}) ==')
        pi, orbits = cell_permutation(cent, matrix, adj)
        if pi is None:
            print(f'  SKIPPED: {orbits}')
            continue
        sizes = defaultdict(int)
        for o in orbits:
            sizes[len(o)] += 1
        fixed = sizes.get(1, 0)
        print('  cell orbits: ' + ', '.join(f'{c}x size {s}'
                                            for s, c in sorted(sizes.items())))
        if fixed and order > 2:
            print(f'  NOTE: {fixed} fixed cell(s) under an order-{order} map '
                  f'=> provably infeasible (see docstring); solver will confirm.')
        tour = count_symmetric(n, adj, pi, time_limit, show_one=witness or plot)
        if plot and tour:
            from hex_view import plot_tour
            plot_tour(polys, tour, f'{name}-invariant Hamiltonian tour, '
                      f'hex9 level {level} ({n} cells)',
                      f'output/L{level}_{name}.png')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l', '--level', type=int, default=0,
                    help='hex9 layer (12 * 9^L cells; default 0)')
    ap.add_argument('-s', '--symmetry', choices=[*SYMMETRIES, 'all'],
                    default='all', help='which isometry to enforce (default all)')
    ap.add_argument('-t', '--time-limit', type=float, default=None,
                    help='solver time limit in seconds per symmetry')
    ap.add_argument('-w', '--witness', action='store_true',
                    help='print one example tour per feasible symmetry')
    ap.add_argument('-p', '--plot', action='store_true',
                    help='save a figure per witness tour (implies -w)')
    args = ap.parse_args()
    names = list(SYMMETRIES) if args.symmetry == 'all' else [args.symmetry]
    run(args.level, names, args.time_limit, args.witness, args.plot)
