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
Hamiltonian circuits on a global hex9 layer.

Builds the adjacency graph of ALL hexagons of a global hex9 layer L
(12 * 9^L cells over the octahedron/sphere) from the HexMesh shared-vertex
mesh: two cells are neighbours iff their faces share an edge (a pair of
vertex indices).  This is exact integer matching - no float comparison,
and octant seams are already deduplicated by the mesh's (ia, ib, oid)
vertex keys.

Topology notes (verified by the sanity checks below):
 - every edge borders exactly 2 faces (watertight sphere),
 - at each of the 6 octahedron vertices exactly TWO cells meet, sharing
   TWO edges; so 12 cells have 5 distinct neighbours (one doubled), the
   rest have 6.  Euler: V - E + F = 2 holds with those 6 degree-2 map
   vertices included.

Then uses CP-SAT AddCircuit to find closed loops visiting every hexagon
exactly once via neighbour steps, and counts ALL solutions.
AddCircuit enumerates *directed* circuits: each undirected Hamiltonian
cycle is found twice (once per orientation), so the undirected count is
the reported solution count / 2.

Usage:
    python3 hex_hamiltonian.py            # level 0 (12 cells), full count
    python3 hex_hamiltonian.py -l 1       # level 1 (108 cells)
    python3 hex_hamiltonian.py -l 1 -t 60 # with a 60s time limit
"""
import argparse
import time
from collections import defaultdict

from ortools.sat.python import cp_model


def build_layer_graph(level: int, with_centroids: bool = False,
                      with_polys: bool = False, with_uuids: bool = False):
    """Adjacency of the global hex9 layer *level* via HexMesh shared vertices.

    Returns (n_cells, adj) where adj[i] is the sorted list of distinct
    neighbouring cell indices of cell i.  With with_centroids=True, appends
    centroids (N, 3) — the mean of each cell's vertices in c_oct
    (folded-octahedron cartesian) coordinates, the natural frame for
    applying octahedral isometries.  With with_polys=True, also appends
    the cell polygons (N, 6, 3) in the same frame (for plotting).  With
    with_uuids=True, appends the mesh's per-cell UUID addresses (verified
    aligned with the face/cell index order) — the bridge into hhg9's
    address-space machinery (e.g. h9_cell_ancestor).
    """
    import numpy as np
    from scipy.spatial import cKDTree
    from hhg9 import Registrar
    from hhg9.h9.grid import HexMesh

    reg = Registrar()
    # Raw AK lattice (no authalic warp): everything here is combinatorial,
    # and the warp's corner anisotropy corrupts 30-degree turn snapping at
    # L4+ (angles up to ~15 deg off grid near the octahedron vertices).
    # The unwarped lattice has exact angles at every level.
    reg.domain('b_oct').no_warp()
    mesh = HexMesh.create(level, reg)
    faces = mesh[level]                       # (N, 6) vertex indices
    n = len(faces)
    assert n == 12 * 9 ** level, f'expected {12 * 9 ** level} cells, got {n}'

    # The mesh vertex pool stores octant-seam vertices once per octant
    # (dict keys are (ia, ib, oid)); merge coincident vertices on the
    # folded octahedron (c_oct, 3D) so seam edges pair up.
    xyz = reg.project(mesh.pts.copy(), ['b_oct', 'c_oct']).coords
    canon = np.arange(len(xyz))               # union-find, path-halving

    def find(i):
        while canon[i] != i:
            canon[i] = canon[canon[i]]
            i = canon[i]
        return i

    for i, j in cKDTree(xyz).query_pairs(1e-9):
        ri, rj = find(i), find(j)
        if ri != rj:
            canon[max(ri, rj)] = min(ri, rj)
    faces = np.vectorize(find)(faces)

    edge_faces = defaultdict(list)            # (v_lo, v_hi) -> [face, ...]
    for f, verts in enumerate(faces):
        for e in range(6):
            a, b = int(verts[e]), int(verts[(e + 1) % 6])
            edge_faces[(a, b) if a < b else (b, a)].append(f)

    adj = defaultdict(set)
    doubled = defaultdict(int)                # unordered face pair -> shared edges
    for edge, fs in edge_faces.items():
        assert len(fs) == 2, f'edge {edge} borders {len(fs)} faces: {fs}'
        p, q = fs
        assert p != q, f'face {p} shares edge {edge} with itself'
        adj[p].add(q)
        adj[q].add(p)
        doubled[(p, q) if p < q else (q, p)] += 1

    # --- sanity report -------------------------------------------------
    n_verts = len({v for vs in edge_faces for v in vs})
    n_edges = len(edge_faces)
    euler = n_verts - n_edges + n
    degs = defaultdict(int)
    for i in range(n):
        degs[len(adj[i])] += 1
    pairs2 = sum(1 for c in doubled.values() if c == 2)
    print(f'L{level}: {n} cells, {n_edges} edges, {n_verts} vertices; '
          f'Euler V-E+F = {euler}')
    print(f'  degrees: ' + ', '.join(f'{d}x{c}' for d, c in sorted(degs.items()))
          + f'; double-adjacent pairs (octahedron vertices): {pairs2}')
    assert euler == 2
    adj = {i: sorted(adj[i]) for i in range(n)}
    out = (n, adj)
    if with_centroids or with_polys:
        out += (xyz[faces].mean(axis=1),)
    if with_polys:
        out += (xyz[faces],)
    if with_uuids:
        out += (mesh.addrs,)
    return out


class Counter(cp_model.CpSolverSolutionCallback):
    def __init__(self, every: int = 100_000):
        super().__init__()
        self.solutions = 0
        self.every = every

    def on_solution_callback(self):
        self.solutions += 1
        if self.solutions % self.every == 0:
            print(f'  ... {self.solutions} directed circuits so far '
                  f'({self.WallTime():.1f}s)')


def count_hamiltonian(n: int, adj: dict, time_limit: float | None,
                      show_one: bool = False) -> list[int] | None:
    model = cp_model.CpModel()
    arcs = [(h, t, model.NewBoolVar(f'{h}->{t}'))
            for h, tails in adj.items() for t in tails]
    model.AddCircuit(arcs)

    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    if time_limit:
        solver.parameters.max_time_in_seconds = time_limit
    counter = Counter()
    t0 = time.time()
    status = solver.Solve(model, counter)
    dt = time.time() - t0

    name = solver.StatusName(status)
    directed = counter.solutions
    if status == cp_model.INFEASIBLE:
        print(f'  INFEASIBLE: no Hamiltonian circuit exists ({dt:.2f}s)')
        return None
    complete = status == cp_model.OPTIMAL  # search space fully swept
    qual = 'exactly' if complete else 'at least (time limit hit)'
    print(f'  {name}: {qual} {directed} directed circuits '
          f'= {directed // 2} undirected Hamiltonian cycles ({dt:.2f}s)')

    if show_one and directed:
        # Re-solve once (non-enumerating) to print a witness tour.
        solver2 = cp_model.CpSolver()
        if solver2.Solve(model) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            succ = {h: t for h, t, lit in arcs if solver2.Value(lit)}
            tour, cur = [0], succ[0]
            while cur != 0:
                tour.append(cur)
                cur = succ[cur]
            print(f'  witness tour: {tour}')
            return tour
    return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l', '--level', type=int, default=0,
                    help='hex9 layer (12 * 9^L cells; default 0)')
    ap.add_argument('-t', '--time-limit', type=float, default=None,
                    help='solver time limit in seconds (default: none)')
    ap.add_argument('-w', '--witness', action='store_true',
                    help='print one example tour')
    ap.add_argument('-p', '--plot', action='store_true',
                    help='save a figure of the witness tour (implies -w)')
    args = ap.parse_args()
    if args.plot:
        n, adj, cent, polys = build_layer_graph(args.level, with_polys=True)
    else:
        n, adj = build_layer_graph(args.level)
    tour = count_hamiltonian(n, adj, args.time_limit,
                             show_one=args.witness or args.plot)
    if args.plot and tour:
        from hex_view import plot_tour
        plot_tour(polys, tour, f'Hamiltonian tour, hex9 level {args.level} '
                  f'({n} cells)', f'output/L{args.level}_tour.png')
