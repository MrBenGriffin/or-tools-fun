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
Block-recursive Hamiltonian circuits - the space-filling-curve route.

Self-similarity, not global symmetry, is what makes Hilbert-type curves:
every truncation of the curve must itself be a valid coarse traversal.
Here we impose exactly that, one level deep:

  OWNERSHIP.  Partition the fine cells (level L+1) into blocks, one per
  coarse cell (level L).  The default is hex9's CANONICAL ownership
  (h9_cell_ancestor: the mode-0 d_cell roll-up, pure address space), which
  guarantees EXACTLY 9 descendants per hexagon: the 7 fine hexes wholly
  inside, plus 2 of the 6 vertex-hexes (one fine hex is centred on each
  coarse vertex, shared 3 ways; the canonical fold assigns each to one
  parent, balanced).  Each block's edge-connectivity is verified, and the
  blocks are classified by the angular separation of their two vertex-
  hexes around the parent centre.

  --geometric switches to the earlier nearest-centroid assignment (kept
  for comparison; unbalanced 7..13 blocks, warp-dependent tie detection -
  a lineage-flavoured approximation, not the hex9 partition).

  CONTIGUITY.  A tour visits a block contiguously iff exactly one used
  arc leaves the block (circuit conservation then gives exactly one
  entering).  One constraint per coarse cell:

      sum(arc u->v : owner[u] == p != owner[v]) == 1

  CONTRACTION.  Under these constraints, collapsing each block-run of the
  fine tour to its owner yields a Hamiltonian cycle of the COARSE layer -
  the level-(L+1) curve "is" a level-L curve when squinted at.  This is
  well-defined because any two blocks that touch have edge-adjacent
  parents: around an ordinary grid vertex three hexes meet pairwise, and
  at the 6 octahedron vertices the two meeting cells share two edges.
  The witness path verifies the contraction machine-checkably.

Counting is as ever directed circuits / 2.  The count here answers: how
many one-level SFC-compatible tours exist?  (A full recursive curve family
needs this at every level; a FINITE-RULE curve additionally needs the
per-block paths to depend only on (block context, entry, exit) - that
uniform-grammar channelling is the natural next extension.)

Usage:
    python3 hex_blocks.py                 # fine L1 over coarse L0
    python3 hex_blocks.py -c 1 -t 300     # fine L2 over coarse L1
    python3 hex_blocks.py -w -p           # witness + figure (blocks coloured)
"""
import argparse
import time
from collections import defaultdict
import numpy as np
from ortools.sat.python import cp_model
from hex_hamiltonian import build_layer_graph, Counter


def _verify_blocks(owner: np.ndarray, n_coarse: int, fine_adj: dict) -> dict:
    """Sizes histogram + per-block edge-connectivity assertion."""
    blocks = defaultdict(list)
    for f, p in enumerate(owner):
        blocks[int(p)].append(f)
    sizes = defaultdict(int)
    for p, members in blocks.items():
        sizes[len(members)] += 1
        m = set(members)
        seen, queue = {members[0]}, [members[0]]
        while queue:
            u = queue.pop()
            for v in fine_adj[u]:
                if v in m and v not in seen:
                    seen.add(v)
                    queue.append(v)
        assert seen == m, f'block {p} is not edge-connected: {sorted(m - seen)}'
    assert len(blocks) == n_coarse
    return sizes


def canonical_ownership(fine_uuids: list, coarse_uuids: list, coarse_level: int,
                        fine_adj: dict) -> np.ndarray:
    """Owner per fine cell via hex9's canonical mode-0 roll-up.

    h9_cell_ancestor is pure address space (region-thread truncation +
    canonical fold), so this is THE hex9 ownership partition - exactly 9
    fine cells per coarse cell, asserted below.
    """
    from hhg9.h9.uuid_address import h9_cell_ancestor
    anc = h9_cell_ancestor(fine_uuids, coarse_level)
    cmap = {u: i for i, u in enumerate(coarse_uuids)}
    owner = np.array([cmap[a] for a in anc])
    sizes = _verify_blocks(owner, len(coarse_uuids), fine_adj)
    assert dict(sizes) == {9: len(coarse_uuids)}, f'not 9-regular: {dict(sizes)}'
    print(f'  ownership: canonical roll-up, {len(coarse_uuids)} blocks of '
          f'exactly 9 (verified, all edge-connected)')
    return owner


def ownership(fine_cent: np.ndarray, coarse_cent: np.ndarray,
              fine_adj: dict) -> np.ndarray:
    """Geometric owner per fine cell: nearest coarse centroid in c_oct.

    Kept for comparison with the canonical partition.  Vertex-hexes are
    equidistant to 3 coarse centroids only up to fold/warp noise, so tie
    detection is unreliable and blocks come out unbalanced (7..13).
    """
    d2 = ((fine_cent[:, None, :] - coarse_cent[None, :, :]) ** 2).sum(axis=2)
    best = d2.min(axis=1)
    ties = d2 <= best[:, None] * (1 + 1e-3)
    owner = np.array([np.flatnonzero(t)[0] for t in ties])
    n_tied = int((ties.sum(axis=1) > 1).sum())
    sizes = _verify_blocks(owner, len(coarse_cent), fine_adj)
    print(f'  ownership: geometric, {n_tied} detected ties, block sizes '
          + ', '.join(f'{c}x size {s}' for s, c in sorted(sizes.items())))
    return owner


# ---------------------------------------------------------------------------
# Pattern analysis: "which distinct in-block paths does a tour use?"
#
# Each block-run of the tour is reduced to its TURN SEQUENCE: at every cell
# of the run, the angle (in units of 60 degrees) between the incoming and
# outgoing edge, measured in that cell's own unfolded net frame (exact on
# the polyhedral surface; only the 60-degree SNAP of the difference is
# needed, so per-cell frame offsets cancel).  The external edges at entry
# and exit are included, so the signature fixes how the path hangs on its
# doors.  Rotations of a pattern leave the sequence unchanged; reflection
# negates it (mod 6); reversal reverses AND negates - the canonical form is
# the minimum over those four variants, i.e. patterns are compared up to
# congruence and direction.
# ---------------------------------------------------------------------------

class TurnFrame:
    """Cached per-cell edge directions for turn measurement.

    Directions are measured in each cell's own unfolded net frame, so
    only DIFFERENCES between two directions at the same cell are
    meaningful - and those are exact multiples of 60 degrees up to warp
    distortion, which the snap absorbs.
    """

    def __init__(self, adj: dict, polys: np.ndarray):
        from hex_view import net_positions
        self.polys = polys
        self.poly2, self.cent2 = net_positions(polys)
        self._dir = {}
        for a, nbrs in adj.items():
            for b in nbrs:
                hits = [vi for vi in range(6)
                        if np.any(np.all(np.isclose(polys[a, vi], polys[b],
                                                    atol=1e-12), axis=1))]
                tip = self.poly2[a, hits].mean(axis=0) - self.cent2[a]
                self._dir[(a, b)] = float(np.degrees(np.arctan2(tip[1], tip[0])))

    def turn(self, prev: int, cur: int, nxt: int) -> int:
        """Turn (units of 30 deg, 0..11) from prev->cur to cur->nxt at cur.

        Ordinary cells only produce EVEN values (60-degree lattice turns).
        The 12 octahedron-vertex cells are cone points (240 degrees of
        surface angle) with a doubled edge, so their turns land on ODD
        multiples of 30 - a 60-degree snap would collapse genuinely
        distinct turns there and undercount pattern classes.
        """
        t = ((self._dir[(cur, nxt)] - self._dir[(cur, prev)]) % 360.0) / 30.0
        k = int(round(t)) % 12
        if abs(t - round(t)) > 0.4:
            print(f'  [warn] turn at cell {cur} is {t * 30:.0f} deg - poor snap')
        return k

    def chain_signature(self, chain: list[int]) -> tuple:
        """Canonical turn signature of chain[1:-1] (ends are external doors)."""
        turns = tuple(self.turn(chain[i - 1], chain[i], chain[i + 1])
                      for i in range(1, len(chain) - 1))
        return _canonical_pattern(turns)


def _canonical_pattern(turns: tuple) -> tuple:
    neg = tuple((-x) % 12 for x in turns)
    return min(turns, neg, tuple(reversed(neg)), tuple(reversed(turns)))


def sig_str(sig: tuple) -> str:
    """Compact display: one char per turn, 30-degree units 0..11 -> 0-9ab."""
    return ''.join('0123456789ab'[t] for t in sig)


def tour_patterns(tour: list[int], owner: np.ndarray,
                  frame: 'TurnFrame') -> dict:
    """Signature class -> count over the tour's block-runs."""
    n = len(tour)
    first = next(i for i in range(1, n)
                 if owner[tour[i]] != owner[tour[i - 1]])
    seq = tour[first:] + tour[:first]              # starts at a block boundary

    runs, run = [], [seq[0]]
    for c in seq[1:]:
        if owner[c] == owner[run[-1]]:
            run.append(c)
        else:
            runs.append(run)
            run = [c]
    runs.append(run)

    patterns = defaultdict(int)
    for r, run in enumerate(runs):
        prev_c = runs[r - 1][-1]                   # external entry neighbour
        next_c = runs[(r + 1) % len(runs)][0]      # external exit neighbour
        patterns[frame.chain_signature([prev_c] + run + [next_c])] += 1
    return dict(patterns)


def pattern_report(tour: list[int], owner: np.ndarray, polys: np.ndarray,
                   adj: dict = None, frame: 'TurnFrame' = None):
    """Classify each block-run of the tour; print the distinct pattern set."""
    if frame is None:
        frame = TurnFrame(adj, polys)
    patterns = tour_patterns(tour, owner, frame)
    n_blocks = sum(patterns.values())
    print(f'  witness uses {len(patterns)} distinct block patterns '
          f'across {n_blocks} blocks (turn sequences, canonical up to '
          f'rotation/reflection/reversal):')
    for sig, count in sorted(patterns.items(), key=lambda kv: -kv[1]):
        print(f'    {count:>3}x  {sig_str(sig)}')


def count_block_recursive(n: int, adj: dict, owner: np.ndarray,
                          coarse_adj: dict, time_limit: float | None,
                          show_one: bool = False) -> list[int] | None:
    model = cp_model.CpModel()
    arc = {(u, v): model.NewBoolVar(f'{u}->{v}')
           for u, tails in adj.items() for v in tails}
    model.AddCircuit([(u, v, lit) for (u, v), lit in arc.items()])

    # Contiguity: exactly one used arc leaves each coarse block.
    leaving = defaultdict(list)
    for (u, v), lit in arc.items():
        if owner[u] != owner[v]:
            leaving[int(owner[u])].append(lit)
    for p, lits in leaving.items():
        model.Add(sum(lits) == 1)

    # Phase 1 - existence, with the full parallel portfolio.  Solution
    # enumeration forces sequential search, far too weak to FIND a first
    # solution on larger instances (L2: 972 cells + 108 block constraints),
    # so decide feasibility first and only then enumerate.
    feas = cp_model.CpSolver()
    if time_limit:
        feas.parameters.max_time_in_seconds = time_limit
    t0 = time.time()
    f_status = feas.Solve(model)
    dt = time.time() - t0
    if f_status == cp_model.INFEASIBLE:
        print(f'  INFEASIBLE: no block-recursive Hamiltonian circuit ({dt:.2f}s)')
        return None
    if f_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        print(f'  UNKNOWN: existence undecided within the time limit ({dt:.2f}s)')
        return None
    print(f'  FEASIBLE: block-recursive circuits exist '
          f'(first found in {dt:.2f}s); enumerating...')

    # Phase 2 - count by enumeration (sequential by construction).
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    if time_limit:
        solver.parameters.max_time_in_seconds = time_limit
    counter = Counter()
    t0 = time.time()
    status = solver.Solve(model, counter)
    dt = time.time() - t0
    directed = counter.solutions
    qual = 'exactly' if status == cp_model.OPTIMAL else 'at least (time limit hit)'
    print(f'  {solver.StatusName(status)}: {qual} {directed} directed '
          f'= {directed // 2} undirected block-recursive Hamiltonian cycles '
          f'({dt:.2f}s)')

    if show_one:
        succ = {u: v for (u, v), lit in arc.items() if feas.Value(lit)}
        tour, cur = [0], succ[0]
        while cur != 0:
            tour.append(cur)
            cur = succ[cur]
        # contraction: owner sequence, runs collapsed, rotated to a
        # block boundary so a block split across the arbitrary start
        # cell is not double-counted.
        owners = [int(owner[c]) for c in tour]
        first = next(i for i in range(1, len(owners))
                     if owners[i] != owners[i - 1])
        owners = owners[first:] + owners[:first]
        contracted = [p for i, p in enumerate(owners)
                      if i == 0 or p != owners[i - 1]]
        assert len(contracted) == len(coarse_adj), 'a block was re-entered'
        assert len(set(contracted)) == len(contracted)
        ring = contracted + [contracted[0]]
        assert all(b in coarse_adj[a] for a, b in zip(ring, ring[1:])), \
            'contraction is not a coarse tour'
        print(f'  witness tour: {tour}')
        print(f'  contracts to coarse Hamiltonian cycle '
              f'(machine-verified): {contracted}')
        return tour
    return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-c', '--coarse', type=int, default=0,
                    help='coarse layer L; fine layer is L+1 (default 0)')
    ap.add_argument('-t', '--time-limit', type=float, default=None,
                    help='solver time limit in seconds')
    ap.add_argument('-w', '--witness', action='store_true',
                    help='print witness tour + verified contraction + patterns')
    ap.add_argument('-p', '--plot', action='store_true',
                    help='save a figure: tour over ownership-coloured blocks')
    ap.add_argument('-g', '--geometric', action='store_true',
                    help='use nearest-centroid ownership instead of canonical')
    args = ap.parse_args()

    nc, coarse_adj, coarse_cent, coarse_uuids = build_layer_graph(
        args.coarse, with_centroids=True, with_uuids=True)
    n, adj, cent, polys, uuids = build_layer_graph(
        args.coarse + 1, with_polys=True, with_uuids=True)
    if args.geometric:
        owner = ownership(cent, coarse_cent, adj)
    else:
        owner = canonical_ownership(uuids, coarse_uuids, args.coarse, adj)
    tour = count_block_recursive(n, adj, owner, coarse_adj, args.time_limit,
                                 show_one=args.witness or args.plot)
    if tour:
        pattern_report(tour, owner, polys, adj)
    if args.plot and tour:
        from hex_view import plot_tour
        plot_tour(polys, tour,
                  f'Block-recursive Hamiltonian tour, hex9 level '
                  f'{args.coarse + 1} over level {args.coarse} blocks',
                  f'output/L{args.coarse + 1}_blocks.png',
                  cell_groups=[int(p) for p in owner])
