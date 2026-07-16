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
Witness-tour visualiser for the hexsphere solvers.

Default rendering (plot_tour) is a PLANAR OCTAHEDRAL NET in the
'diamonds_native' arrangement of hex9's nets.py: four longitude columns
(WP | WA | EA | EP, i.e. 180-270 | 270-360 | 0-90 | 90-180), each a
diamond of the north face (apex up) hinged to its south face (apex down)
along their shared equatorial edge.  Cells are drawn WHOLE in the column
of their centroid: a cell straddling a fold has its off-face vertices
isometrically unfolded into the home face's plane (rotation about the
shared edge - NOT the linear extension of the face map, which would
foreshorten the overhang by cos 109.47deg).  Overhangs across the net's
cut edges land in blank space, the classic net look.

Tour edges between cells drawn far apart (their adjacency crosses a net
cut) are shown as numbered stubs: each stub runs from the cell centroid
to the shared cell-edge as drawn in that cell's own copy, and the two
stubs of a crossing carry the same number.

plot_tour3d keeps the previous two-hemisphere 3D view.

Colour notes: the palette is colour-vision-deficiency-safe - a blue tour
line with a gold start marker and a red second-cell marker (the pair
shows tour direction); optional per-cell fill colours (e.g. ownership
blocks in hex_blocks.py) use blue/yellow/purple/grey tones separated by
luminance rather than hue alone.
"""
from pathlib import Path

import numpy as np

TOUR = '#004488'      # Tol high-contrast blue
START = '#DDAA33'     # Tol gold
SECOND = '#BB5566'    # Tol red (direction: START -> SECOND)
FACE = '#F7F7F5'
EDGE = (0.35, 0.35, 0.35, 1.0)

# Qualitative fills for cell groupings (ownership blocks): CVD-safe tones,
# neighbours distinguished by luminance and blue/yellow/purple axes.
BLOCKS = ['#77AADD', '#EEDD88', '#CC99BB', '#DDDDDD', '#99DDFF', '#AAAA00',
          '#BBBBEE', '#FFFFCC', '#7788CC', '#DDCC77', '#BB99DD', '#F0F0F0']

VIEWS = [(20, -60), (-20, 120)]   # (elev, azim) - opposite hemispheres

# diamonds_native column order (west to east from the antimeridian):
# (sx, sy) sign pair of the equatorial corners -> column index and name.
COLUMNS = [((-1, -1), 'WP'), ((+1, -1), 'WA'), ((+1, +1), 'EA'), ((-1, +1), 'EP')]
H = np.sqrt(3) / 2                # equilateral triangle height, side 1


def _face_corners_2d(sx: int, sy: int, sz: int) -> dict[int, np.ndarray]:
    """2D net positions of a face's three corners, keyed by axis (0,1,2).

    The face of orthant (sx, sy, sz) has corners (sx,0,0), (0,sy,0),
    (0,0,sz).  Its column's base runs left->right in increasing longitude;
    the pole corner is the apex (up for north, down for south).
    """
    col = next(i for i, (sig, _) in enumerate(COLUMNS) if sig == (sx, sy))
    lon = {(+1, +1): (0, 1), (-1, +1): (1, 0), (-1, -1): (0, 1), (+1, -1): (1, 0)}
    # axis 0 (x-corner) and axis 1 (y-corner): which is the left corner?
    # EA: x at lon 0 (left), y at lon 90 (right); EP: y left, -x right;
    # WP: -x left, -y right; WA: -y left, x right.
    x_left = (sx, sy) in ((+1, +1), (-1, -1))
    left, right = np.array([col, 0.]), np.array([col + 1., 0.])
    return {0: left if x_left else right,
            1: right if x_left else left,
            2: np.array([col + 0.5, sz * H])}


def _reflect(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Reflect point p across the line through a and b."""
    d = (b - a) / np.linalg.norm(b - a)
    v = p - a
    return a + 2 * (v @ d) * d - v


def net_positions(polys: np.ndarray):
    """Unfold cell polygons (N, 6, 3) on |x|+|y|+|z|=1 into the planar net.

    Returns (net_polys (N, 6, 2), net_cent (N, 2)).  Home face per cell is
    the orthant of its centroid (zeros resolved to +); vertices on a
    neighbouring face (exactly one negative barycentric weight) are
    unfolded isometrically across the shared edge.
    """
    n = len(polys)
    cent = polys.mean(axis=1)
    out = np.empty((n, 6, 2))
    for c in range(n):
        s = np.where(cent[c] >= 0, 1, -1).astype(int)
        corn = _face_corners_2d(*s)
        for vi in range(6):
            w = polys[c, vi] * s                     # barycentric in home face
            neg = np.flatnonzero(w < -1e-12)
            assert len(neg) <= 1, f'cell {c} vertex spans >2 faces'
            if len(neg) == 0:
                cg, wg = corn, w
            else:
                j = int(neg[0])                      # unfold across edge opp. j
                k1, k2 = [a for a in range(3) if a != j]
                cg = dict(corn)
                cg[j] = _reflect(corn[j], corn[k1], corn[k2])
                sg = s.copy()
                sg[j] = -sg[j]
                wg = polys[c, vi] * sg               # barycentric in neighbour
            out[c, vi] = wg[0] * cg[0] + wg[1] * cg[1] + wg[2] * cg[2]
    return out, out.mean(axis=1)


def plot_tour(polys: np.ndarray, tour: list[int], title: str, out_path,
              cell_groups: list[int] | None = None):
    """Save a planar-net figure of *tour* over the cell *polys* (N, 6, 3).

    cell_groups: optional per-cell integer labels (e.g. owning parent);
    cells are filled from the BLOCKS palette by label modulo its length.
    Tour edges crossing net cuts are drawn as numbered stub pairs.
    """
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from matplotlib.collections import PolyCollection, LineCollection

    poly2, cent2 = net_positions(polys)
    if cell_groups is None:
        fills = np.full(len(polys), FACE, dtype=object)
    else:
        fills = np.array([BLOCKS[g % len(BLOCKS)] for g in cell_groups],
                         dtype=object)

    order = list(tour) + [tour[0]]
    pairs = list(zip(order[:-1], order[1:]))

    def shared_edge_2d(a: int, b: int, of: int) -> np.ndarray:
        """Midpoint, in cell *of*'s drawn copy, of the a|b shared edge."""
        other = polys[b] if of == a else polys[a]
        own = polys[a] if of == a else polys[b]
        hits = [vi for vi in range(6)
                if np.any(np.all(np.isclose(own[vi], other, atol=1e-12), axis=1))]
        assert len(hits) >= 2, f'cells {a},{b} share <2 vertices'
        return poly2[of, hits].mean(axis=0)

    # An edge is net-contiguous iff the shared cell-edge is drawn at the
    # same place in both cells' copies (exact, no distance threshold) -
    # otherwise the adjacency crosses a net cut and gets numbered stubs.
    pitch = np.median(np.abs(poly2[:, 0] - poly2[:, 3]).sum(axis=1))
    near = [np.linalg.norm(shared_edge_2d(a, b, a) - shared_edge_2d(a, b, b))
            < 0.05 * pitch for a, b in pairs]

    fig, ax = plt.subplots(figsize=(16, 8.5), dpi=200)
    ax.set_aspect('equal')
    ax.set_axis_off()
    ax.set_title(title, fontsize=13)
    ax.add_collection(PolyCollection(list(poly2), ec=EDGE, facecolors=fills,
                                     linewidth=0.4, zorder=1))
    segs = [np.stack([cent2[a], cent2[b]])
            for (a, b), ok in zip(pairs, near) if ok]
    ax.add_collection(LineCollection(segs, colors=TOUR, linewidth=1.8, zorder=4))

    n_cross = sum(1 for ok in near if not ok)
    label = n_cross <= 60          # beyond that the numbers are just noise
    crossing = 0
    for (a, b), ok in zip(pairs, near):
        if ok:
            continue
        crossing += 1
        for cell in (a, b):
            tip = shared_edge_2d(a, b, cell)
            ax.plot(*np.stack([cent2[cell], tip]).T, color=TOUR,
                    linewidth=1.8, zorder=4)
            if label:
                lab = tip + (tip - cent2[cell]) * 0.9
                ax.annotate(str(crossing), lab, color=TOUR, fontsize=7,
                            ha='center', va='center', zorder=6)
    for cell, colour, size in ((tour[0], START, 50), (tour[1], SECOND, 25)):
        ax.scatter(*cent2[cell], color=colour, s=size, zorder=5)

    # face outlines + names, lightly
    for (sx, sy), cname in COLUMNS:
        for sz in (1, -1):
            corn = _face_corners_2d(sx, sy, sz)
            tri = np.stack([corn[0], corn[1], corn[2], corn[0]])
            ax.plot(*tri.T, color='#999999', linewidth=0.7, zorder=2)
            mid = (corn[0] + corn[1] + corn[2]) / 3
            ax.annotate(('N' if sz > 0 else 'S') + cname, mid,
                        color='#999999', fontsize=9, ha='center',
                        va='center', zorder=2)
    if crossing:
        note = ('matching numbered stubs' if label
                else 'stubs unnumbered at this density')
        ax.annotate(f'{crossing} tour edges cross net cuts ({note})',
                    (0.5, -0.06), xycoords='axes fraction', ha='center',
                    fontsize=9, color='#555555')
    ax.autoscale_view()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    print(f'  plot saved: {out_path}')


def plot_tour3d(polys: np.ndarray, tour: list[int], title: str, out_path,
                cell_groups: list[int] | None = None):
    """Save a two-panel 3D figure of *tour* over the cell *polys* (N, 6, 3).

    cell_groups: optional per-cell integer labels (e.g. owning parent);
    cells are filled from the BLOCKS palette by label modulo its length.
    """
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

    cent = polys.mean(axis=1)
    order = list(tour) + [tour[0]]
    # Lift tour slightly off the surface so it never z-fights the faces.
    lifted = cent * 1.02
    segs = np.stack([lifted[order[:-1]], lifted[order[1:]]], axis=1)

    if cell_groups is None:
        fills = np.full(len(polys), FACE, dtype=object)
    else:
        fills = np.array([BLOCKS[g % len(BLOCKS)] for g in cell_groups],
                         dtype=object)

    fig = plt.figure(figsize=(14, 7.4), dpi=200)
    fig.suptitle(title, fontsize=13)
    fig.subplots_adjust(left=0.0, right=1.0, top=0.98, bottom=0.02, wspace=0.02)
    for k, (elev, azim) in enumerate(VIEWS):
        ax = fig.add_subplot(1, 2, k + 1, projection='3d')
        ax.view_init(elev=elev, azim=azim)
        ax.set_proj_type('ortho')
        # Each panel only draws its front hemisphere, so painter's order
        # (faces, then tour, then markers) is correct - disable matplotlib's
        # per-collection depth sort, which would bury the tour under the
        # face collection.
        ax.computed_zorder = False
        az, el = np.deg2rad(azim), np.deg2rad(elev)
        axis = np.array([np.cos(el) * np.cos(az),
                         np.cos(el) * np.sin(az), np.sin(el)])
        fmask = cent @ axis >= 0                       # front-facing cells
        smask = segs.mean(axis=1) @ axis >= 0          # front-facing segments
        ax.add_collection(Poly3DCollection(list(polys[fmask]), ec=EDGE,
                                           facecolors=fills[fmask],
                                           linewidth=0.4, zorder=1))
        ax.add_collection(Line3DCollection(list(segs[smask]), colors=TOUR,
                                           linewidth=2.0, zorder=4))
        for cell, colour, size in ((tour[0], START, 60), (tour[1], SECOND, 30)):
            if cent[cell] @ axis >= 0:
                ax.scatter(*lifted[cell], color=colour, s=size, zorder=6)
        ax.set_xlim(-1, 1); ax.set_ylim(-1, 1); ax.set_zlim(-1, 1)
        ax.set_aspect('equal', adjustable='box')
        ax.set_axis_off()
        ax.set_title(f'view {elev}/{azim}', fontsize=9)
    fig.text(0.5, 0.02, 'gold = start, red = second cell (direction)',
             ha='center', fontsize=9)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, facecolor='white', bbox_inches='tight')
    plt.close(fig)
    print(f'  plot saved: {out_path}')
