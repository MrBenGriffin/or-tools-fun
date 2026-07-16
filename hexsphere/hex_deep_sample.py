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
hex_deep_sample: deep empirical sample of the closed 36-state transducer.

Greenwich-seam windows (ex0263's patch, widened 3x linear) at layers
16..21 - ~120k addresses, dominated by L22 (~1.4 cm cells).  For every
cell of every layer the curve address is computed by PURE TABLE WALK
(h9curve_rowtables_L5c.pkl: 12 root rows + total T1/T2 over 36 states),
i.e. depths 4x beyond anything the tables were built or tested on, on
the prime-meridian octant seam (fold hinges, foster-rich lineages; the
cone points are far away - they were exercised by the hexsphere runs).

Verified per layer:
  * the walk never misses a table key (T1/T2 totality at depth),
  * curve indices are distinct over the sample (bijectivity),
  * cells with CONSECUTIVE curve indices are edge-adjacent on the sphere
    (local Hamiltonicity, geometric check via the c_oct vertex merge -
    exact across the seam),
and each layer is plotted flat (lon/lat): cells outlined, tour segments
between consecutive-index cells coloured along the curve (viridis).

Coarse layers (window inside one cell) use a context window of a few
cell pitches so every panel shows curve structure; the address count
there is small.  Curve indices exceed uint64 beyond ~L18 (12*9^22 ~
1.2e22): Python bigints here, the packing story is separate.

Usage:  python3 hex_deep_sample.py [-l0 5] [-l1 22]
"""
import argparse
import pickle
import time
from collections import defaultdict
import numpy as np
from hhg9.h9 import uuid_address as ua

TABLES = 'output/h9curve_rowtables_L5c.pkl'
CENTRE = (51.48, 0.0)                     # Greenwich Park, on the seam
BASE_HALF = (3.0e-7, 4.5e-7)              # (lat, lon) half-spans, ex0263 x3
PITCH22 = 2.0e-9                          # L22 flat-to-flat ~0.22 mm, in deg lat


def window_for(level: int):
    """Clip window per layer: the base patch, or a few cell pitches."""
    pitch = PITCH22 * 3.0 ** (22 - level)
    h_lat = max(BASE_HALF[0], 2.5 * pitch)
    h_lon = max(BASE_HALF[1], 2.5 * pitch / 0.6227)   # cos(51.48 deg)
    lat, lon = CENTRE
    return np.array([[lat - h_lat, lon - h_lon], [lat - h_lat, lon + h_lon],
                     [lat + h_lat, lon + h_lon], [lat + h_lat, lon - h_lon]])


def translate(uuids, level, tables, axiom_pos):
    """Pure-table curve indices for a column of level-*level* uuids.

    Iterated one-generation ancestor chains (the curve's tree - direct
    deep re-bin differs on hexagon-band cells), then the transducer walk.
    Raises KeyError if the tables are incomplete at any step - that IS
    the totality test.
    """
    levels = [list(uuids)]
    # This is a naive approach and will be replaced in hex9
    for k in range(level - 1, -1, -1):
        levels.append(ua.h9_cell_ancestor(levels[-1], k))
    levels.reverse()
    labels = [[ua.h9_label(a).split('.')[0] for a in lev] for lev in levels]
    T1, T2, roots = tables['T1'], tables['T2'], tables['root_state']
    out = []
    for i in range(len(uuids)):
        S = roots[labels[0][i]]
        index = axiom_pos[labels[0][i]]
        for k in range(1, level + 1):
            d_par, d = labels[k - 1][i], labels[k][i]
            r = T1[(S, (d[:-1] != d_par, d[-1]))]
            index = index * 9 + r
            if k < level:
                S = T2[(S, r)]
        out.append(index)
    return out


def merged_faces(mesh, faces, reg):
    """Face array with pool vertices merged on the folded octahedron
    (c_oct), so seam-straddling neighbours share vertex ids exactly."""
    from scipy.spatial import cKDTree
    xyz = reg.project(mesh.pts.copy(), ['b_oct', 'c_oct']).coords
    canon = np.arange(len(xyz))

    def find(i):
        while canon[i] != i:
            canon[i] = canon[canon[i]]
            i = canon[i]
        return i

    for i, j in cKDTree(xyz).query_pairs(1e-9):
        ri, rj = find(i), find(j)
        if ri != rj:
            canon[max(ri, rj)] = min(ri, rj)
    return np.vectorize(find)(faces)


def base9(x: int, width: int) -> str:
    s = ''
    while x:
        s = str(x % 9) + s
        x //= 9
    return s.rjust(width, '0')


def check_and_plot(level, faces_m, lonlat_polys, idx, name,
                   max_labels=2500):
    """Adjacency check on consecutive indices + the flat curve plot."""
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.collections import PolyCollection, LineCollection

    n = len(idx)
    order = sorted(range(n), key=lambda i: idx[i])
    edge_of = defaultdict(set)                 # cell -> set of edge keys
    for f in range(n):
        vs = faces_m[f]
        for e in range(6):
            a, b = int(vs[e]), int(vs[(e + 1) % 6])
            edge_of[f].add((a, b) if a < b else (b, a))

    segs, cols, runs, bad = [], [], 1, 0
    cent = lonlat_polys.mean(axis=1)           # (n, 2) lon-lat
    for j in range(1, n):
        a, b = order[j - 1], order[j]
        if idx[b] == idx[a] + 1:
            if not (edge_of[a] & edge_of[b]):
                bad += 1
            segs.append([cent[a], cent[b]])
            ca, cb = idx[j - 1], idx[j]
            cab = ((ca + cb) / 2) # // 9
            cols.append(ca % 10)  # final digit
        else:
            runs += 1
    assert len(set(idx)) == n, f'L{level}: curve indices not distinct'

    # curve-address suffixes: the layer's shared prefix goes in the
    # title, each cell shows only its distinguishing suffix - so a
    # parent's suffix at layer L reappears extended by one rank digit
    # on its nine children at L+1.
    import os.path
    span = 9 ** level
    addr = [f'{i // span}.{base9(i % span, level)}' for i in idx]
    prefix = os.path.commonprefix(addr)
    labelled = n <= max_labels
    suf_len = max(len(a) - len(prefix) for a in addr) if n > 1 else 1

    # FIXED canvas and extent (the base window) for EVERY layer, with a
    # transparent background - so the per-layer PNGs overlay pixel-
    # perfect: coarse layers contribute their big cell outlines, the
    # labelled mid layers their suffix grids, L22 the fine curve.
    # Canvas is sized for the finest labelled grid (L21: ~120 cells
    # across the window needs real pixels per cell).
    pad = 1.08
    ex_w = 2 * BASE_HALF[1] * pad
    ex_h = 2 * BASE_HALF[0] * pad
    aspect = 1.0 / 0.6227                       # lat/lon at 51.48N
    w_in = 30.0
    fig = plt.figure(figsize=(w_in, w_in * ex_h * aspect / ex_w), dpi=250)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(CENTRE[1] - ex_w / 2, CENTRE[1] + ex_w / 2)
    ax.set_ylim(CENTRE[0] - ex_h / 2, CENTRE[0] + ex_h / 2)
    ax.set_axis_off()
    scale = w_in / 10.0
    ax.add_collection(PolyCollection(
        lonlat_polys, facecolors='none', edgecolors='#88888860',
        linewidths=(0.3 if n < 2000 else 0.08) * scale))
    if segs:
        lc = LineCollection(segs, cmap='plasma', array=np.array(cols),
                            linewidths=(2.4 if n < 2000 else 0.7) * scale)
        ax.add_collection(lc)
    ax.axvline(0.0, color='#cc0000', lw=0.4 * scale, ls='--', alpha=0.5)
    if labelled:
        # font sized to the cell pitch on this fixed canvas
        pitch_lon = PITCH22 * 3.0 ** (22 - level) / 0.6227
        cell_pts = w_in * 72.0 * pitch_lon / ex_w
        fs = max(1.5, min(11.0, 0.85 * cell_pts / (0.62 * suf_len)))
        x0, x1 = ax.get_xlim()
        y0, y1 = ax.get_ylim()
        for i in range(n):
            if x0 <= cent[i][0] <= x1 and y0 <= cent[i][1] <= y1:
                ax.annotate(addr[i][len(prefix):], cent[i], ha='center',
                            va='center', fontsize=fs, color='#222222')
    ax.text(0.004, 0.998, f'L{level}: {n} cells, {runs} runs, '
            f'prefix {prefix or "(none)"}, '
            f'bits <= {max(idx).bit_length()}',
            transform=ax.transAxes, va='top', fontsize=9, color='#333333')
    fig.savefig(f'output/{name}.png', transparent=True)
    plt.close(fig)
    return runs, bad, prefix


def main(l0: int, l1: int, args_max_labels: int = 12000):
    from hhg9 import Registrar
    from hhg9.h9.grid import HexMesh

    with open(TABLES, 'rb') as f:
        tables = pickle.load(f)
    assert not tables['frontier'], 'tables are not the closed set'
    axiom_pos = {lab: i for i, lab in enumerate(tables['axiom'])}
    print(f'tables: {len(tables["rows"])} states, T2 total '
          f'({len(tables["T2"])} entries), closed')

    reg = Registrar()
    g_gcd, b_oct = reg.domain('g_gcd'), reg.domain('b_oct')

    grand = 0
    t_all = time.time()
    for level in range(l0, l1 + 1):
        t0 = time.time()
        win = window_for(level)
        mesh = HexMesh.create_clipped([level], win, reg)
        uuids = list(mesh.addr(level))
        faces = mesh[level]
        n = len(uuids)
        assert n == len(faces) and n > 0, f'L{level}: {n} uuids/{len(faces)}'
        note = (' (context window)'
                if 2.5 * PITCH22 * 3.0 ** (22 - level) > BASE_HALF[0] else '')

        idx = translate(uuids, level, tables, axiom_pos)
        lonlat = reg.project(mesh.pts.copy(), [b_oct, g_gcd]).coords
        polys = lonlat[faces][:, :, ::-1]              # (n, 6, 2) lon-lat
        faces_m = merged_faces(mesh, faces, reg)
        runs, bad, prefix = check_and_plot(level, faces_m, polys, idx,
                                           f'deep_sample_L{level}',
                                           max_labels=args_max_labels)
        grand += n
        print(f'L{level:>2}: {n:>6} cells{note}, {runs:>4} runs, '
              f'consecutive-index adjacency violations: {bad}, '
              f'prefix {prefix or "(none)":<26} '
              f'bits {max(idx).bit_length():>2} '
              f'({time.time() - t0:.1f}s)')
        assert bad == 0, f'L{level}: {bad} adjacency violations'
    print(f'TOTAL {grand} addresses translated + verified in '
          f'{time.time() - t_all:.0f}s - table walk never missed a key, '
          f'indices bijective per layer, every consecutive-index pair '
          f'edge-adjacent (local Hamiltonicity at depth)')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument('-l0', type=int, default=16)
    ap.add_argument('-l1', type=int, default=21)
    ap.add_argument('-m', '--max-labels', type=int, default=12000,
                    help='annotate suffixes when a layer has <= this '
                         'many cells (default 12000: L21 in, L22 out)')
    args = ap.parse_args()
    main(args.l0, args.l1, args.max_labels)
