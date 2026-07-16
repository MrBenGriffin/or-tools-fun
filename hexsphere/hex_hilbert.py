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
hex_hilbert: the curve address, and its translation to/from hex9 uuids.

THE CURVE ADDRESS.  A cell's position along the hex9 space-filling curve
(hex_curve.py) has the same shape as its hex9 uuid: an axiom slot (0..11,
position of its L0 ancestor in the axiom tour) followed by one base-9
RANK digit per level - the cell's position within its parent's 9-cell
block-run.  index = ((slot * 9 + r1) * 9 + r2) * 9 ... - a u64 up to ~L18,
directly comparable, range-queryable, and locality-preserving.

THE TRANSLATION.  The uuid encodes the LINEAGE path; the curve recurses
on the OWNERSHIP tree (canonical roll-up; 7 of a block's 9 children are
lineage children, 2 are fosters re-binned from a neighbouring parent).
h9_cell_ancestor bridges the two symbolically, so the ownership chain of
any uuid is available without geometry.  What remains for a SYMBOLIC
(Hilbert-style, table-driven) translation is that rank assignment be a
finite-state process:

    STATE of a block   = its traversal turn sequence (uncanonicalised -
                         rotation-invariant by construction, and finite),
    (state, slot)  -> rank         [slot = the child's identity relative
    (state, rank)  -> child state   to its parent, from address digits]

This script (a) generates the curve to the target level recording every
block's state, (b) builds exact dictionary-backed uuid <-> index
converters and round-trips every cell, (c) extracts the transducer
tables and censuses their FUNCTIONALITY (any conflict disproves the
finite-state claim; none proves it on all tested levels), and (d)
replays the digits of every cell purely from (root-state table + slots +
transducer) and compares with the truth - the symbolic translation
demonstrated end-to-end, no geometry in the loop.

Usage:
    python3 hex_hilbert.py            # to L3 (8748 cells)
    python3 hex_hilbert.py -l 2
"""
import argparse
import time
from collections import defaultdict

from hex_hamiltonian import build_layer_graph
from hex_blocks import canonical_ownership, TurnFrame
from hex_curve import axiom_tour, rule_tables, ALPHABET


def label_digits(uuid, level: int) -> str:
    """The uuid's lineage digit string ('523' etc), via h9_label."""
    from hhg9.h9 import uuid_address as ua
    lab = ua.h9_label(uuid)
    digits = lab.split('.')[0]
    assert len(digits) == level + 1, f'label {lab} at level {level}'
    return digits


def generate_with_states(target: int):
    """hex_curve generation, additionally recording per-block details.

    Returns (tours, layers) where layers[k] holds the level-k+1 data:
    owner array, uuids, and per parent-block: path, state (raw turn
    tuple over the traversal chain).
    """
    n0, adj0 = build_layer_graph(0)
    tours = {0: axiom_tour(adj0)}
    layers = {}
    for k in range(target):
        nc, adj_c, cent_c, uu_c = build_layer_graph(k, with_centroids=True,
                                                    with_uuids=True)
        n, adj, cent, polys, uu = build_layer_graph(k + 1, with_polys=True,
                                                    with_uuids=True)
        owner = canonical_ownership(uu, uu_c, k, adj)
        frame = TurnFrame(adj, polys)
        table, crossing = rule_tables(owner, adj, frame)

        tour, m = tours[k], len(tours[k])
        fine, states, paths, entry_cls, entry_ext = [], {}, {}, {}, {}
        for i, cur in enumerate(tour):
            prev, nxt = tour[i - 1], tour[(i + 1) % m]
            e, x = crossing[(prev, cur)], crossing[(cur, nxt)]
            path = table[cur][(e, x)]
            entry_ext[cur] = e[0]
            chain = [e[0]] + path + [x[1]]
            states[cur] = tuple(frame.turn(chain[j - 1], chain[j],
                                           chain[j + 1])
                                for j in range(1, len(chain) - 1))
            # pose: net-plane direction class (30 deg units) of the entry
            # door as seen from the first path cell - the block's absolute
            # orientation, which the rotation-invariant turn tuple lacks.
            entry_cls[cur] = int(round(frame._dir[(path[0], e[0])]
                                       / 30.0)) % 12
            paths[cur] = path
            fine.extend(path)
        tours[k + 1] = fine
        layers[k + 1] = dict(owner=owner, uuids=uu, coarse_uuids=uu_c,
                             states=states, paths=paths, n=n,
                             entry_cls=entry_cls, entry_ext=entry_ext,
                             frame=frame, adj=adj)
    return tours, layers


def run(target: int):
    t0 = time.time()
    tours, layers = generate_with_states(target)
    print(f'curve generated to L{target} in {time.time() - t0:.1f}s')

    # positions and rank digits, with the structural identity verified:
    # pos_k(cell) == 9 * pos_{k-1}(parent) + rank,  rank in 0..8
    pos = {k: {c: i for i, c in enumerate(t)} for k, t in tours.items()}
    for k in range(1, target + 1):
        own = layers[k]['owner']
        for c, p in pos[k].items():
            r = p - 9 * pos[k - 1][int(own[c])]
            assert 0 <= r < 9, f'rank identity fails at L{k} cell {c}'
    print('rank identity verified: index = (...(slot*9 + r1)*9 + ...) + rL')

    # exact uuid <-> index converters (dictionary-backed) + full round-trip
    uu_pos = {}                      # uuid -> curve index at target level
    uuids = layers[target]['uuids']
    for c, u in enumerate(uuids):
        uu_pos[u] = pos[target][c]
    rev = tours[target]
    assert all(uuids[rev[i]] == u for u, i in uu_pos.items())
    print(f'uuid <-> index round-trip verified for all {len(uu_pos)} '
          f'cells at L{target}')

    # ---- transducer extraction -----------------------------------------
    # T1: (parent state, slot) -> rank; T2: (parent state, rank) -> child
    # state.  Both must be FUNCTIONAL for a finite-state translation.
    # State and slot definitions are pluggable; censused coarse-to-rich:
    #   states: turn tuple alone (rotation-invariant, blind to pose) or
    #           turn tuple + entry-door direction class (pose included);
    #   slots:  (foster?, last digit) or + the foster's lineage-parent
    #           last digit (which neighbour it was re-binned from).
    def state_turns(k, par):
        return layers[k]['states'][par]

    def state_posed(k, par):
        return (layers[k]['states'][par], layers[k]['entry_cls'][par])

    frame6_cache = {}

    def frame6(k, par):
        """The block's digit frame: net-plane direction class from its
        centre cell to each interior ring child, ordered by digit -
        captures orientation AND chirality of the hex9 digit assignment."""
        key = (k, par)
        if key not in frame6_cache:
            members = layers[k]['paths'][par]
            adj_k, fr = layers[k]['adj'], layers[k]['frame']
            mset = set(members)
            # centre = the member most connected within the block (6 for
            # ordinary blocks; 5 when the centre is an octahedron-vertex
            # cell); ties broken by digit string for determinism.
            centre = max(members,
                         key=lambda c: (sum(v in mset for v in adj_k[c]),
                                        label_digits(layers[k]['uuids'][c],
                                                     k)))
            d_par = label_digits(layers[k]['coarse_uuids'][par], k - 1)
            digit = {c: label_digits(layers[k]['uuids'][c], k)
                     for c in members}
            interior = {c for c in members if digit[c][:-1] == d_par}
            raw = sorted(
                (digit[c][-1], int(round(fr._dir[(centre, c)] / 30.0)) % 12)
                for c in adj_k[centre] if c in mset and c in interior)
            # INTRINSIC frame, chart-safe: every subtraction happens
            # within ONE cell's chart (like the turn machinery - absolute
            # snapped classes are not comparable across cells/instances).
            # Ring: directions at the CENTRE's chart, relative to the
            # smallest interior ring digit.  Keeps orientation+chirality.
            ref = raw[0][1]
            ring = tuple((d, (cls - ref) % 12) for d, cls in raw)
            # Entry: at the first path cell's own chart, relative to its
            # smallest-digit in-block neighbour (identified by digit, so
            # the anchor is symbolic).
            p0 = layers[k]['paths'][par][0]
            nb_in = [c for c in adj_k[p0] if c in mset]
            a0 = min(nb_in, key=lambda c: digit[c])
            u_ext = layers[k]['entry_ext'][par]
            entry_rel = (digit[p0][-1] if p0 in interior else
                         (digit[p0][-2], digit[p0][-1]),
                         digit[a0][-1],
                         (int(round(fr._dir[(p0, u_ext)] / 30.0))
                          - int(round(fr._dir[(p0, a0)] / 30.0))) % 12)
            # Fosters are pinned SYMBOLICALLY: by their lineage parent's
            # digit, their own digit, and the digits of the interior ring
            # cells they touch (their corner, relative to the ring whose
            # directions are already in the state).
            fosters = tuple(sorted(
                (digit[c][-2], digit[c][-1],
                 tuple(sorted(digit[v][-1] for v in adj_k[c]
                              if v in interior)))
                for c in members if c not in interior))
            frame6_cache[key] = (entry_rel, ring, fosters)
        return frame6_cache[key]

    def state_full(k, par):
        # k % 2: the hex9 digit frame's relation to its children's frames
        # alternates with level (mode alternation) - conflict dumps show
        # digit-identical child paths with different rings across levels.
        # The parent's own trailing digit carries its region mode (frame
        # orientation is digit-determined in the region scheme), so it is
        # part of the state - and it is pure address data (symbolic).
        d_par = label_digits(layers[k]['coarse_uuids'][par], k - 1)
        return (k % 2, d_par[-2:], layers[k]['states'][par], frame6(k, par))

    def slot_digit(k, c, par):
        d_par = label_digits(layers[k]['coarse_uuids'][par], k - 1)
        d_child = label_digits(layers[k]['uuids'][c], k)
        return (d_child[:-1] != d_par, d_child[-1])

    def slot_digit_rel(k, c, par):
        d_par = label_digits(layers[k]['coarse_uuids'][par], k - 1)
        d_child = label_digits(layers[k]['uuids'][c], k)
        foster = d_child[:-1] != d_par
        rel = d_child[-2] if foster else ''
        return (foster, rel, d_child[-1])

    def census(state_fn, slot_fn):
        T1, T2, n_states, conflicts = {}, {}, set(), 0
        slot_of = {}
        for k in range(1, target + 1):
            own = layers[k]['owner']
            for c in range(layers[k]['n']):
                par = int(own[c])
                S = state_fn(k, par)
                n_states.add(S)
                slot = slot_fn(k, c, par)
                slot_of[(k, c)] = slot
                r = pos[k][c] - 9 * pos[k - 1][par]
                entries = [(T1, (S, slot), r)]
                if k < target:
                    entries.append((T2, (S, r), state_fn(k + 1, c)))
                for tbl, key, val in entries:
                    if key in tbl and tbl[key] != val:
                        conflicts += 1
                    tbl[key] = val
        return T1, T2, n_states, conflicts, slot_of

    chosen = None
    for s_name, state_fn in (('turns', state_turns),
                             ('turns+pose', state_posed),
                             ('turns+pose+frame', state_full)):
        for l_name, slot_fn in (('digit', slot_digit),
                                ('digit+rel', slot_digit_rel)):
            T1, T2, n_states, conflicts, slot_of = census(state_fn, slot_fn)
            print(f'  state={s_name:<10} slot={l_name:<9}: '
                  f'{len(n_states):>3} states, {len(T1):>4} T1 entries; '
                  f'conflicts: {conflicts}')
            if conflicts == 0 and chosen is None:
                chosen = (s_name, l_name, state_fn, T1, T2, slot_of)
    if chosen is None:
        print('  no censused definition is finite-state - needs further '
              'enrichment')
        return
    s_name, l_name, state_fn, T1, T2, slot_of = chosen
    print(f'transducer: state={s_name}, slot={l_name} is FUNCTIONAL')

    # ---- symbolic replay ------------------------------------------------
    # Predict every cell's rank digits using ONLY: the root state table
    # (12 entries), slot labels (from address digits), T1 and T2.
    root_state = {c: state_fn(1, c) for c in tours[0]}
    checked = mismatched = 0
    for c in range(layers[target]['n']):
        chain = [c]
        for k in range(target, 0, -1):
            chain.append(int(layers[k]['owner'][chain[-1]]))
        chain.reverse()              # [c0 (L0), c1, ..., cL]
        S = root_state[chain[0]]
        ok = True
        for k in range(1, target + 1):
            r_true = pos[k][chain[k]] - 9 * pos[k - 1][chain[k - 1]]
            r_pred = T1.get((S, slot_of[(k, chain[k])]))
            if r_pred != r_true:
                ok = False
                break
            if k < target:
                S = T2[(S, r_pred)]
        checked += 1
        mismatched += (not ok)
    print(f'symbolic replay: {checked} cells, {mismatched} mismatches'
          + (' - SYMBOLIC TRANSLATION HOLDS (uuid digits + tables -> curve '
             'digits, no geometry)' if not mismatched else ''))


# ---------------------------------------------------------------------------
# Persistent transducer tables + the microsecond fast path.
# The canonical (proven conflict-free) state: (level parity, parent's two
# trailing digits, traversal turn tuple, chart-safe intrinsic frame).
# ---------------------------------------------------------------------------

def _label_tail(layers, k, par) -> str:
    """The parent label's tail nibble - hex9's canonical (c2, r_mo)
    metadata, the natural mode coordinate for the digit frame."""
    from hhg9.h9 import uuid_address as ua
    lab = ua.h9_label(layers[k]['coarse_uuids'][par])
    return lab.split('.')[1] if '.' in lab else ''


def _canonical_state(layers, k, par, cache, extra=None):
    key = (k, par, extra.__name__ if extra else '')
    if key not in cache:
        members = layers[k]['paths'][par]
        adj_k, fr = layers[k]['adj'], layers[k]['frame']
        mset = set(members)
        centre = max(members,
                     key=lambda c: (sum(v in mset for v in adj_k[c]),
                                    label_digits(layers[k]['uuids'][c], k)))
        d_par = label_digits(layers[k]['coarse_uuids'][par], k - 1)
        digit = {c: label_digits(layers[k]['uuids'][c], k) for c in members}
        interior = {c for c in members if digit[c][:-1] == d_par}
        raw = sorted((digit[c][-1],
                      int(round(fr._dir[(centre, c)] / 30.0)) % 12)
                     for c in adj_k[centre] if c in mset and c in interior)
        ref = raw[0][1]
        ring = tuple((d, (cls - ref) % 12) for d, cls in raw)
        p0 = members[0]
        a0 = min((c for c in adj_k[p0] if c in mset),
                 key=lambda c: digit[c])
        u_ext = layers[k]['entry_ext'][par]
        entry_rel = (digit[p0][-1] if p0 in interior
                     else (digit[p0][-2], digit[p0][-1]),
                     digit[a0][-1],
                     (int(round(fr._dir[(p0, u_ext)] / 30.0))
                      - int(round(fr._dir[(p0, a0)] / 30.0))) % 12)
        fosters = tuple(sorted(
            (digit[c][-2], digit[c][-1],
             tuple(sorted(digit[v][-1] for v in adj_k[c] if v in interior)))
            for c in members if c not in interior))
        ctx = extra(layers, k, par) if extra else d_par[-2:]
        cache[key] = (k % 2, ctx, layers[k]['states'][par],
                      (entry_rel, ring, fosters))
    return cache[key]


def _slot(parent_digits: str, child_digits: str) -> tuple:
    return (child_digits[:-1] != parent_digits, child_digits[-1])


def _ctx_d1(layers, k, par):
    return label_digits(layers[k]['coarse_uuids'][par], k - 1)[-1:]


def _ctx_d2(layers, k, par):
    return label_digits(layers[k]['coarse_uuids'][par], k - 1)[-2:]


def _ctx_d3(layers, k, par):
    return label_digits(layers[k]['coarse_uuids'][par], k - 1)[-3:]


def _ctx_tail(layers, k, par):
    return _label_tail(layers, k, par)


def _ctx_d1_tail(layers, k, par):
    return (_ctx_d1(layers, k, par), _label_tail(layers, k, par))


_rthread_cache = {}


def _region_thread(layers, k, par):
    """Ground-up disambiguation: the parent's region thread, recovered
    root-down by x_adr_to_r_adr - classifier cells whose values already
    incorporate the accumulated mode/orientation cascade (unlike the
    presentation-level hex digits, which need unbounded suffixes)."""
    key = (k, par)
    if key not in _rthread_cache:
        from hhg9.h9.addressing import x_adr_to_r_adr, H9_RA
        import numpy as np
        u = layers[k]['coarse_uuids'][par]
        nib = [(u.int >> (4 * (31 - i))) & 0xF for i in range(32)]
        hx = np.array([nib[:k] + [nib[31]]], dtype=np.uint8)  # body+tail, L=k-1
        oc, r_adr = x_adr_to_r_adr(hx)
        cx = np.asarray(H9_RA.rid2cell)[r_adr[0]]
        _rthread_cache[key] = (int(oc[0]), tuple(int(x) for x in cx))
    return _rthread_cache[key]


def _ctx_rterm(layers, k, par):
    """Terminal classifier cell of the region thread (bounded, <0x60)."""
    oc, cx = _region_thread(layers, k, par)
    return cx[-1]


def _ctx_rterm2(layers, k, par):
    """Last two classifier cells (bounded)."""
    oc, cx = _region_thread(layers, k, par)
    return cx[-2:]


def _ctx_rterm2_mo(layers, k, par):
    """Last two classifier cells + octant mode (bounded)."""
    from hhg9.h9 import H9O
    oc, cx = _region_thread(layers, k, par)
    return (int(H9O.oid_mo[oc]),) + cx[-2:]


def _ctx_rterm_d1(layers, k, par):
    return (_ctx_rterm(layers, k, par), _ctx_d1(layers, k, par))


def _ctx_rterm2_d1(layers, k, par):
    return (_ctx_rterm2(layers, k, par), _ctx_d1(layers, k, par))


def _ctx_rterm3(layers, k, par):
    oc, cx = _region_thread(layers, k, par)
    return cx[-3:]


CTX_VARIANTS = [('rterm+d1', _ctx_rterm_d1), ('rterm2+d1', _ctx_rterm2_d1),
                ('rterm3', _ctx_rterm3), ('rterm2+mo', _ctx_rterm2_mo),
                ('d1+tail', _ctx_d1_tail), ('d2', _ctx_d2), ('d3', _ctx_d3)]


def extract_tables(target: int) -> dict:
    """Build, verify, and return the persistent transducer tables.

    Censuses the frame-context variants coarse-to-rich and keeps the
    first conflict-free one (the context is the digit-frame/mode carrier;
    hex9's label tail is the principled candidate, digit suffixes the
    empirical fallbacks)."""
    tours, layers = generate_with_states(target)
    pos = {k: {c: i for i, c in enumerate(t)} for k, t in tours.items()}
    chosen = None
    for name, extra in CTX_VARIANTS:
        cache = {}
        T1, T2 = {}, {}
        fresh = defaultdict(lambda: [0, 0])      # level -> [new T1, new T2]
        conflicts = 0
        for k in range(1, target + 1):
            own = layers[k]['owner']
            for c in range(layers[k]['n']):
                par = int(own[c])
                S = _canonical_state(layers, k, par, cache, extra)
                slot = _slot(
                    label_digits(layers[k]['coarse_uuids'][par], k - 1),
                    label_digits(layers[k]['uuids'][c], k))
                r = pos[k][c] - 9 * pos[k - 1][par]
                entries = [(T1, (S, slot), r, 0)]
                if k < target:
                    entries.append((T2, (S, r),
                                    _canonical_state(layers, k + 1, c,
                                                     cache, extra), 1))
                for tbl, key, val, which in entries:
                    if key not in tbl:
                        fresh[k][which] += 1
                    elif tbl[key] != val:
                        conflicts += 1
                    tbl[key] = val
        n_states = len({s for s, _ in T1})
        print(f'  ctx={name:<8}: {n_states:>4} states, {len(T1):>5} T1; '
              f'conflicts {conflicts}; new T1/T2 by level: '
              + ' '.join(f'L{k}:{fresh[k][0]}/{fresh[k][1]}'
                         for k in sorted(fresh)))
        if conflicts == 0 and chosen is None:
            axiom_labels = [label_digits(layers[1]['coarse_uuids'][c], 0)
                            for c in tours[0]]
            root_state = {label_digits(layers[1]['coarse_uuids'][c], 0):
                          _canonical_state(layers, 1, c, cache, extra)
                          for c in tours[0]}
            chosen = dict(level=target, ctx=name, axiom=axiom_labels,
                          root_state=root_state, T1=T1, T2=T2)
    assert chosen is not None, 'no context variant is conflict-free'
    return chosen


def learn_states(target: int):
    """Learn the transducer state assignment directly: the coarsest
    partition of ownership-tree blocks under which T1/T2 are functional.

    The censuses (run / extract_tables) test PRESCRIBED state formulas
    (turn tuples, frames, digit suffixes, region-thread suffixes); every
    bounded formula fails with depth - the digit-frame orientation
    accumulates along the address.  But the fast path never computes the
    state from digits: T2 threads it during the walk, so ANY conflict-free
    partition is operationally valid; only the 12 root states are explicit.

    So compute the Nerode-style coarsest congruence over the ownership
    tree itself:  node = block (the 9 level-k children of a level-(k-1)
    cell), output = its slot->rank map, transition = rank -> child block.
    Partition-refine from output rows.  If the class count SATURATES with
    level, a bounded folded accumulator exists and the learned transition
    table IS the fold table (the per-row class multiplicity is the hidden
    phase).  If it grows, no hexagon-level FSM closes - machine evidence
    for the d-cell transport redesign.
    """
    tours, layers = generate_with_states(target)
    pos = {k: {c: i for i, c in enumerate(t)} for k, t in tours.items()}

    out_row, kids = {}, {}
    for k in range(1, target + 1):
        own = layers[k]['owner']
        rows = defaultdict(dict)
        for c in range(layers[k]['n']):
            par = int(own[c])
            slot = _slot(label_digits(layers[k]['coarse_uuids'][par], k - 1),
                         label_digits(layers[k]['uuids'][c], k))
            r = pos[k][c] - 9 * pos[k - 1][par]
            assert slot not in rows[par], 'slot collision within a block'
            rows[par][slot] = r
            if k < target:
                kids.setdefault((k, par), {})[r] = (k + 1, c)
        for par, m in rows.items():
            assert len(m) == 9
            out_row[(k, par)] = tuple(sorted(m.items()))

    # BOUNDED-HORIZON bisimulation: class^0 = output row; class^{h+1}(n) =
    # (row, rank -> class^h(child)).  class^h is only DEFINED for nodes
    # with h fully observed levels below (k <= target - h) - this removes
    # the truncation artifact of naive global refinement, where nodes at
    # different distances from the leaf boundary live in disjoint child-id
    # spaces and can never merge (the earlier version's fake "growth").
    # class^{h+1} refines class^h on the common domain (induction on h),
    # so stabilisation = the first h with zero splits.
    rows_id = {}
    for row in out_row.values():
        rows_id.setdefault(row, len(rows_id))
    print(f'nodes: {len(out_row)} blocks (L1..L{target}); '
          f'distinct T1 rows: {len(rows_id)}')

    def levels_line(assign):
        seen, parts = set(), []
        for k in range(1, target + 1):
            lvl = {assign[n] for n in assign if n[0] == k}
            if lvl:
                parts.append(f'L{k}:{len(lvl)}(+{len(lvl - seen)})')
                seen |= lvl
        return ' '.join(parts)

    cur = {n: rows_id[row] for n, row in out_row.items()}
    h, h_star = 0, None
    while True:
        print(f'  h={h}: {len(set(cur.values()))} classes '
              f'on k<=L{target - h}; {levels_line(cur)}')
        dom = [n for n in out_row if n[0] <= target - (h + 1)]
        if not dom:
            break
        idx, nxt = {}, {}
        for n in dom:
            sig = (rows_id[out_row[n]],
                   tuple(sorted((r, cur[ch]) for r, ch in kids[n].items())))
            nxt[n] = idx.setdefault(sig, len(idx))
        if len(idx) == len({cur[n] for n in dom}):
            h_star = h            # class^{h+1} == class^h where comparable
            cur = nxt
            h += 1
            break
        cur, h = nxt, h + 1
    if h_star is None:
        print(f'  refinement still splitting at the deepest testable '
              f'horizon (h={h}) - need a deeper level to decide')
        return cur, out_row, kids
    print(f'  STABLE at h*={h_star}: class^{h_star + 1} = class^{h_star} '
          f'on k<=L{target - h_star - 1}')
    if h_star == 0:
        # class = row, defined at EVERY node - so tables may be built from
        # every observed parent->child pair, not just the stability domain.
        # The only legitimately open transitions are those out of FRONTIER
        # rows (first seen at the deepest level - their children are
        # unobserved).  The row is intrinsic (path x digit layout, no
        # absolute orientation), so the row vocabulary is finite and
        # closure is a matter of reachable-set enumeration.
        cur = {n: rows_id[out_row[n]] for n in out_row}

    # hidden phase at h*: classes sharing one output row.
    stable_cls = {n: c for n, c in cur.items()}
    row_of = defaultdict(set)
    for n, c in stable_cls.items():
        row_of[rows_id[out_row[n]]].add(c)
    mult = defaultdict(int)
    for cs in row_of.values():
        mult[len(cs)] += 1
    print('  hidden phase (classes per row): '
          + ' '.join(f'{m}x{c}' for m, c in sorted(mult.items())))

    # tables over class^{h*+1}'s domain, then REPLAY over the whole tree:
    # the deep boundary levels never contributed a class, so every check
    # there is out-of-sample.  Walk classes down from the 12 roots via T2
    # and demand T1 reproduce every block's actual slot->rank row.
    T1, T2, c1, c2 = {}, {}, 0, 0
    for n, c in stable_cls.items():
        for slot, r in out_row[n]:
            key = (c, slot)
            if key in T1 and T1[key] != r:
                c1 += 1
            T1[key] = r
        for r, ch in kids.get(n, {}).items():
            if ch in stable_cls:
                key = (c, r)
                if key in T2 and T2[key] != stable_cls[ch]:
                    c2 += 1
                T2[key] = stable_cls[ch]
    states = set(stable_cls.values())
    first = {}
    for n, c in sorted(stable_cls.items()):
        first.setdefault(c, n[0])
    frontier = {c for c, k0 in first.items() if k0 == target}
    holes = sum(1 for c in states for r in range(9)
                if (c, r) not in T2 and c not in frontier)
    print(f'  tables: {len(states)} states ({len(frontier)} frontier), '
          f'{len(T1)} T1, {len(T2)} T2; conflicts {c1}/{c2}; '
          f'T2 closure: {holes} non-frontier (state,rank) keys unobserved'
          + ('  - CLOSED but for the frontier' if holes == 0 else ''))

    # row census for interpretation: population, first level, cone flag
    # (block contains one of the 12 degree-5 map-vertex cells), exemplar.
    census = {c: [0, first[c], 0, None] for c in states}
    for n, c in stable_cls.items():
        k, par = n
        census[c][0] += 1
        if any(len(layers[k]['adj'][m]) == 5
               for m in layers[k]['paths'][par]):
            census[c][2] += 1
        if census[c][3] is None:
            census[c][3] = label_digits(layers[k]['coarse_uuids'][par],
                                        k - 1)
    print('  row census (id: blocks, first L, cone blocks, exemplar):')
    for c in sorted(states, key=lambda c: (first[c], c)):
        n_blk, k0, cone, ex = census[c]
        print(f'    {c:>3}: {n_blk:>6}  L{k0}  cone {cone:>5}  {ex}')

    pred = {(1, c): stable_cls[(1, c)] for c in tours[0]}
    checked = row_bad = t_missing = 0
    work = list(pred)
    while work:
        n = work.pop()
        c = pred[n]
        checked += 1
        for slot, r in out_row[n]:
            if T1.get((c, slot)) != r:
                row_bad += 1
        for r, ch in kids.get(n, {}).items():
            nc = T2.get((c, r))
            if nc is None:
                t_missing += 1
            else:
                pred[ch] = nc
                work.append(ch)
    print(f'  replay from roots over ALL {checked} blocks: '
          f'{row_bad} row mismatches, {t_missing} missing T2 keys'
          + ('  - FSM CLOSES at the tested depth' if not (row_bad
             or t_missing) else ''))

    if h_star == 0:
        import pickle
        from pathlib import Path
        axiom = [label_digits(layers[1]['coarse_uuids'][c], 0)
                 for c in tours[0]]
        roots = {axiom[i]: stable_cls[(1, c)]
                 for i, c in enumerate(tours[0])}
        out = Path(f'output/h9curve_rowtables_L{target}.pkl')
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, 'wb') as f:
            pickle.dump(dict(level=target, axiom=axiom, root_state=roots,
                             rows={c: r for r, c in rows_id.items()},
                             frontier=sorted(frontier), T1=T1, T2=T2), f)
        print(f'  row tables saved: {out}')
    return stable_cls, out_row, kids


def tables_path(level: int, rows: bool = False) -> str:
    """rows=True selects the learned row-state tables (states = T1 rows,
    from learn_states) - same schema as the ctx tables, ~150x smaller,
    and complete for their depth (frontier rows never need T2 within it)."""
    return f'output/h9curve_{"rowtables" if rows else "tables"}_L{level}.pkl'


def build_tables(target: int):
    import pickle
    from pathlib import Path
    tables = extract_tables(target)
    out = Path(tables_path(target))
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'wb') as f:
        pickle.dump(tables, f)
    print(f'tables saved: {out} ({len(tables["T1"])} T1, '
          f'{len(tables["T2"])} T2 entries, '
          f'{len(set(s for s, _ in tables["T1"]))} states)')


def fast_curve_address(uuid_str: str, tables: dict, depth: int = None):
    """Pure-lookup translation: uuid -> curve address, any depth covered
    by the tables' state set.  Geometry-free; per-uuid cost is the
    ancestor-chain extraction plus ~depth dict lookups."""
    import uuid as uuid_mod
    from hhg9.h9 import uuid_address as ua

    u = uuid_mod.UUID(uuid_str)
    native = len(ua.h9_label(u).split('.')[0]) - 1
    depth = native if depth is None else min(depth, native)

    # ITERATED one-generation ancestors, leaf upward.  The curve recurses
    # on the iterated-ownership tree, which differs from the direct deep
    # re-bin (h9_cell_ancestor(u, k)) on the 1/9 hexagon-band cells -
    # machine-verified: 972 of 8748 L3 cells have composed != direct L1
    # ancestors.  Chains must match the construction.
    a = u if depth == native else ua.h9_cell_ancestor([u], depth)[0]
    chain = [a]
    for k in range(depth - 1, -1, -1):
        a = ua.h9_cell_ancestor([a], k)[0]
        chain.append(a)
    chain.reverse()
    labels = [ua.h9_label(c).split('.')[0] for c in chain]

    slot0 = tables['axiom'].index(labels[0])
    S = tables['root_state'][labels[0]]
    ranks = []
    for k in range(1, depth + 1):
        key = (S, _slot(labels[k - 1], labels[k]))
        if key not in tables['T1']:
            break                    # coverage ends: return the exact prefix
        ranks.append(tables['T1'][key])
        if k < depth:
            nxt = tables['T2'].get((S, ranks[-1]))
            if nxt is None:
                break
            S = nxt
    index = slot0
    for r in ranks:
        index = index * 9 + r
    return slot0, ranks, index, native


def batch_bench(tables: dict):
    """Column-mode benchmark: translate every level-L cell uuid in bulk.

    The per-uuid ancestor chain dominates single-call latency; in column
    mode each chain level is ONE vectorised h9_cell_ancestor call over
    the whole column, and the transducer walk is dict lookups.
    """
    import time as _t
    from hhg9.h9 import uuid_address as ua

    depth = tables['level']
    _, _, _, _, uuids = build_layer_graph(depth, with_polys=True,
                                          with_uuids=True)
    n = len(uuids)
    t0 = _t.perf_counter()
    # iterated one-generation ancestors, one vectorised call per level
    levels = [list(uuids)]
    for k in range(depth - 1, -1, -1):
        levels.append(ua.h9_cell_ancestor(levels[-1], k))
    levels.reverse()
    chains = [[ua.h9_label(a).split('.')[0] for a in lev] for lev in levels]
    t_chain = _t.perf_counter() - t0

    t0 = _t.perf_counter()
    axiom_pos = {lab: i for i, lab in enumerate(tables['axiom'])}
    T1, T2, roots = tables['T1'], tables['T2'], tables['root_state']
    out = []
    for i in range(n):
        S = roots[chains[0][i]]
        index = axiom_pos[chains[0][i]]
        for k in range(1, depth + 1):
            r = T1[(S, _slot(chains[k - 1][i], chains[k][i]))]
            index = index * 9 + r
            if k < depth:
                S = T2[(S, r)]
        out.append(index)
    t_walk = _t.perf_counter() - t0
    assert len(set(out)) == n, 'curve indices are not a bijection'
    print(f'batch: {n} uuids at L{depth}; ancestor chains '
          f'{t_chain:.2f}s ({t_chain / n * 1e6:.0f} us/uuid), transducer '
          f'walk {t_walk:.2f}s ({t_walk / n * 1e6:.1f} us/uuid); indices '
          f'verified distinct')


def curve_address(uuid_str: str, target: int):
    """The curve (Hilbert) address of one hex9 uuid, to *target* levels.

    Rank digits nest exactly like uuid digit prefixes (rank identity), so
    for a uuid deeper than *target* this is the exact PREFIX of its full
    curve address - its position among the level-*target* cells.
    """
    import uuid as uuid_mod
    from hhg9.h9 import uuid_address as ua

    u = uuid_mod.UUID(uuid_str)
    digits = ua.h9_label(u).split('.')[0]
    native = len(digits) - 1
    level = min(target, native)
    print(f'uuid {u} = h9 {ua.h9_label(u)} (level {native}); '
          f'curve address to level {level}:')

    tours, layers = generate_with_states(level)
    pos = {k: {c: i for i, c in enumerate(t)} for k, t in tours.items()}
    cell_of = {k: {uu: c for c, uu in enumerate(layers[k]['uuids'])}
               for k in range(1, level + 1)}
    cell_of[0] = {uu: c for c, uu in enumerate(layers[1]['coarse_uuids'])}

    # iterated one-generation ancestors (the curve's tree; direct deep
    # re-bin differs on hexagon-band cells)
    a = u if native == level else ua.h9_cell_ancestor([u], level)[0]
    anc = [a]
    for k in range(level - 1, -1, -1):
        a = ua.h9_cell_ancestor([a], k)[0]
        anc.append(a)
    anc.reverse()
    chain = [cell_of[k][a] for k, a in enumerate(anc)]

    slot = pos[0][chain[0]]
    ranks = [pos[k][chain[k]] - 9 * pos[k - 1][chain[k - 1]]
             for k in range(1, level + 1)]
    index = slot
    for r in ranks:
        index = index * 9 + r
    print(f'  axiom slot {slot}, rank digits {"".join(map(str, ranks))} '
          f'-> curve index {index} of {12 * 9 ** level}'
          + (f'  (prefix: uuid is level {native}, tables built to '
             f'{level})' if native > level else ''))
    return slot, ranks, index


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l', '--level', type=int, default=3,
                    help='target level (default 3)')
    ap.add_argument('-u', '--uuid', type=str, default=None,
                    help='a hex9 uuid: print its curve (Hilbert) address '
                         'instead of running the census')
    ap.add_argument('--build-tables', action='store_true',
                    help='extract + save the transducer tables to -l levels')
    ap.add_argument('--fast', action='store_true',
                    help='with -u: pure-lookup translation via saved tables '
                         '(-l selects which table file)')
    ap.add_argument('--learn', action='store_true',
                    help='learn the coarsest conflict-free state partition '
                         'over the ownership tree (no prescribed formula)')
    ap.add_argument('--rows', action='store_true',
                    help='with --fast/--bench: use the learned row-state '
                         'tables (h9curve_rowtables_*) instead of ctx tables')
    ap.add_argument('--bench', action='store_true',
                    help='column-mode benchmark over all level -l cells '
                         '(requires saved tables)')
    args = ap.parse_args()
    if args.learn:
        learn_states(args.level)
        raise SystemExit(0)
    if args.bench:
        import pickle
        with open(tables_path(args.level, args.rows), 'rb') as f:
            batch_bench(pickle.load(f))
        raise SystemExit(0)
    if args.build_tables:
        build_tables(args.level)
    elif args.uuid and args.fast:
        import pickle
        import time as _t
        with open(tables_path(args.level, args.rows), 'rb') as f:
            tables = pickle.load(f)
        t0 = _t.perf_counter()
        slot, ranks, index, native = fast_curve_address(args.uuid, tables)
        dt = _t.perf_counter() - t0
        t1 = _t.perf_counter()
        for _ in range(100):                     # amortised (warm) timing
            fast_curve_address(args.uuid, tables)
        warm = (_t.perf_counter() - t1) / 100
        print(f'{args.uuid} (level {native})')
        print(f'  curve address: {slot}.' + ''.join(map(str, ranks))
              + f'  = index {index} of {12 * 9 ** len(ranks)}'
              + ('' if len(ranks) == native else
                 f'  (prefix: table coverage ends at depth {len(ranks)})'))
        print(f'  first call {dt * 1e3:.2f} ms; warm {warm * 1e6:.0f} us/uuid')
    elif args.uuid:
        curve_address(args.uuid, args.level)
    else:
        run(args.level)
