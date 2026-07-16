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
hex_locality: curve-quality metrics vs baselines.

Compares, on the SAME full-sphere hex9 layer:
  * the hex9 curve order (closed row-table walk), vs
  * the uuid/lineage order (labels as base-9 numbers - the grid's own
    Morton/Z-order analogue);
and calibrates against the classical square-grid pair (Hilbert vs
Morton, 2^k x 2^k torus-free grid) at comparable cell count.

Metrics:
  * adjacent-pair index gap |di - dj| over every grid edge (cyclic for
    the closed curve; same formula applied to all orders for fairness):
    the fraction that are 1, median / 95th / max;
  * range-query clustering: for random spherical caps (resp. planar
    disks) holding ~m cells, the number of CONTIGUOUS index runs needed
    to cover the query - the number a database pays per query.

Usage:  python3 hex_locality.py [-l 4] [--caps 300]
"""
import argparse
import time

import numpy as np

from hex_hamiltonian import build_layer_graph
from hex_deep_sample import translate, TABLES


def gap_stats(order, edges, n, cyclic):
    idx = np.asarray(order)
    g = np.abs(idx[edges[:, 0]] - idx[edges[:, 1]])
    if cyclic:
        g = np.minimum(g, n - g)
    return (float(np.mean(g == 1)), int(np.median(g)),
            int(np.percentile(g, 95)), int(g.max()))


def runs(sorted_idx, n, cyclic):
    if len(sorted_idx) == 0:
        return 0
    r = 1 + int(np.sum(np.diff(sorted_idx) > 1))
    if cyclic and r > 1 and (sorted_idx[0] + n - sorted_idx[-1]) == 1:
        r -= 1
    return r


def cap_runs(order, xyz, n, m_target, n_caps, rng, cyclic):
    idx = np.asarray(order)
    f = m_target / n
    cos_t = 1.0 - 2.0 * f
    total, cells = 0, 0
    for _ in range(n_caps):
        c = rng.normal(size=3)
        c /= np.linalg.norm(c)
        sel = np.sort(idx[xyz @ c > cos_t])
        total += runs(sel, n, cyclic)
        cells += len(sel)
    return total / n_caps, cells / n_caps


def disk_runs(order2d, side, m_target, n_disks, rng):
    xs, ys = np.meshgrid(np.arange(side), np.arange(side), indexing='ij')
    xs, ys = xs.ravel(), ys.ravel()
    idx = order2d.ravel()
    r = (m_target / np.pi) ** 0.5
    total, cells = 0, 0
    for _ in range(n_disks):
        cx, cy = rng.uniform(r, side - r, 2)
        sel = np.sort(idx[(xs - cx) ** 2 + (ys - cy) ** 2 < r * r])
        total += runs(sel, None, False)
        cells += len(sel)
    return total / n_disks, cells / n_disks


def hilbert_d(side, x, y):
    """Classic xy -> d on a side x side grid (side = power of 2)."""
    d = np.zeros_like(x, dtype=np.int64)
    x, y = x.copy(), y.copy()
    s = side // 2
    while s > 0:
        rx = ((x & s) > 0).astype(np.int64)
        ry = ((y & s) > 0).astype(np.int64)
        d += s * s * ((3 * rx) ^ ry)
        # rotate quadrant
        flip = ry == 0
        swap_flip = flip & (rx == 1)
        x2 = np.where(swap_flip, s - 1 - x, x)
        y2 = np.where(swap_flip, s - 1 - y, y)
        x, y = np.where(flip, y2, x2), np.where(flip, x2, y2)
        s //= 2
    return d


def morton_d(side, x, y):
    d = np.zeros_like(x, dtype=np.int64)
    for b in range(side.bit_length()):
        d |= ((x >> b) & 1) << (2 * b + 1)
        d |= ((y >> b) & 1) << (2 * b)
    return d


def main(level: int, n_caps: int):
    import pickle
    rng = np.random.default_rng(42)
    with open(TABLES, 'rb') as f:
        tables = pickle.load(f)
    axiom_pos = {lab: i for i, lab in enumerate(tables['axiom'])}

    t0 = time.time()
    n, adj, cent, uuids = build_layer_graph(level, with_centroids=True,
                                            with_uuids=True)
    curve = translate(list(uuids), level, tables, axiom_pos)
    from hhg9.h9 import uuid_address as ua
    labels = [ua.h9_label(u).split('.')[0] for u in uuids]
    morton = np.argsort(np.argsort(labels))       # lineage / uuid order
    print(f'hex9 L{level}: {n} cells prepared in {time.time() - t0:.0f}s')

    edges = np.array([(a, b) for a, nbrs in adj.items()
                      for b in nbrs if a < b])
    xyz = cent / np.linalg.norm(cent, axis=1, keepdims=True)

    side = 256                                     # 65,536 cells, comparable
    gx, gy = np.meshgrid(np.arange(side), np.arange(side), indexing='ij')
    hil = hilbert_d(side, gx.ravel(), gy.ravel())
    mor = morton_d(side, gx.ravel(), gy.ravel())
    ge = []                                        # square-grid 4-adjacency
    flat = np.arange(side * side).reshape(side, side)
    ge.append(np.column_stack([flat[:-1].ravel(), flat[1:].ravel()]))
    ge.append(np.column_stack([flat[:, :-1].ravel(), flat[:, 1:].ravel()]))
    ge = np.vstack(ge)

    print('\nadjacent-pair index gaps (frac==1, median, p95, max):')
    for name, order, ed, nn, cyc in (
            ('hex9 curve   ', curve, edges, n, True),
            ('hex9 uuid    ', morton, edges, n, False),
            ('square Hilbert', hil, ge, side * side, False),
            ('square Morton ', mor, ge, side * side, False)):
        fr, med, p95, mx = gap_stats(order, ed, nn, cyc)
        print(f'  {name}: {fr:5.1%}  {med:>8}  {p95:>10}  {mx:>12}')

    print(f'\nrange-query clustering (avg contiguous runs per query, '
          f'{n_caps} random queries):')
    print(f'  {"~cells/query":>14} {"hex9 curve":>11} {"hex9 uuid":>10} '
          f'{"sq Hilbert":>11} {"sq Morton":>10}')
    for m in (50, 500, 5000):
        rc, mc = cap_runs(curve, xyz, n, m, n_caps, rng, True)
        ru, _ = cap_runs(morton, xyz, n, m, n_caps, rng, False)
        rh, mh = disk_runs(hil.reshape(side, side), side, m, n_caps, rng)
        rm, _ = disk_runs(mor.reshape(side, side), side, m, n_caps, rng)
        print(f'  {mc:>10.0f}     {rc:>11.1f} {ru:>10.1f} '
              f'{rh:>11.1f} {rm:>10.1f}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l', '--level', type=int, default=4)
    ap.add_argument('--caps', type=int, default=300)
    args = ap.parse_args()
    main(args.level, args.caps)
