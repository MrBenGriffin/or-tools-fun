Copyright ©2026 Ben Griffin; Apache 2.0.  Requires `hhg9` (hex9), and
`ortools` for the solver stages (the generator and translator do not
solve anything — ortools is only imported transitively).

# hexsphere — a space-filling curve for the hex9 DGGS

Hamiltonian tours on the global hex9 layers, distilled into a proven
five-pattern substitution grammar, a deterministic curve generator, and
a **36-state transducer** that translates hex9 uuids to curve addresses
by pure table lookup at arbitrary depth.  The curve is a **Moore-type
(closed) sphere-filling loop** with the full Hilbert property package —
substitution self-similarity, prefix-nesting indices, consecutive cells
always adjacent — and **measured Hilbert-grade locality**: range-query
clustering within ~4% of the classical square-grid Hilbert curve, 3–6×
better than the grid's own hierarchy order.  Everything below is
machine-verified; each script re-verifies its own claims when run.

## The result in one paragraph

A global hex9 layer L has 12·9^L hexagons (no pentagons; at the six
octahedron vertices two cells meet twice — 12 cells with 5 distinct
neighbours).  Every layer is Hamiltonian; L0 has exactly 1280 undirected
cycles.  Tours that respect the canonical 9-cell ownership blocks admit
a minimum **five-pattern** alphabet (one per hexagonal transit class:
adjacent ×2, 1-away ×2, opposite), which is *door-functional* (a block's
entry/exit arcs force its internal path) and *turn-closed* (the alphabet
provides exactly the transit turns its own digits consume) — so the
curve refines deterministically to any depth from any L0 axiom tour.
Translating between hex9 uuids (lineage addresses) and curve positions
(ownership-tree ranks) is a finite-state process whose state is simply
**the block's slot→rank map** ("the T1 row"): 36 reachable states, total
transition tables, closed under reachability from the 12 roots.  The
tables fit in ~10 KB.

## Files, in the order the results were built (and should be read)

Stage 1 — counting (CP-SAT, exhaustive where feasible):

| file | what it does |
|---|---|
| `hex_hamiltonian.py` | builds the layer adjacency graph from the HexMesh shared-vertex mesh (`build_layer_graph`, used by everything); counts Hamiltonian circuits (L0 = 1280 exact) |
| `hex_symmetric.py` | symmetry-invariant cycle counts (antipodal 20, c2-vertex 44, c3-face 2, mirror-z 0 at L0); establishes which isometries are grid automorphisms |
| `hex_quotient.py` | voltage-graph quotients — the same invariant counts 16–1200× faster, with machine-verified witness lifts |

Stage 2 — structure (blocks, patterns, grammar):

| file | what it does |
|---|---|
| `hex_blocks.py` | canonical 9-cell ownership (`canonical_ownership`, via `h9_cell_ancestor` — pure address space), block-recursive tours, `TurnFrame` (exact 30°-unit turn classes in each cell's net chart) |
| `hex_patterns.py` | per-block config enumeration (every block: 66 Ham paths); pattern minimisation — 3 patterns suffice per level pair (proven optimal) |
| `hex_grammar.py` | the door rule and two-level closure: level-local triples fail closure (turn-budget obstruction), minimum **self-similar** alphabet = 5 (proven); crossing handshake verified at all ordinary block pairs |
| `hex_view.py` | planar octahedral-net and 3D plots |

Stage 3 — the deterministic curve and the translator:

| file | what it does |
|---|---|
| `hex_curve.py` | the generator: axiom L0 tour + door tables + canonical-edge convention → Hamiltonian tour of any layer, no solver, re-verifying every proven property live (L3 in ~21 s) |
| `hex_hilbert.py` | the curve address (slot + base-9 ranks, same shape as the uuid); exact converters and round-trip; the **state learner** (`--learn`: coarsest conflict-free partition via bounded-horizon bisimulation — this is where "state = T1 row" was discovered); persists row tables; fast path (`--fast`, `--bench`, `--rows`) |
| `hex_frontier.py` | targeted closure: the two frontier row-chains (octahedron-vertex lineages) resolved by *local* L6 refinement — global L6 graph, but configs/turn-frames only for the ~264 involved blocks.  Produces the closed tables |
| `hex_deep_sample.py` | deep empirical verification: Greenwich prime-meridian windows, layers 16–21 (any 5–22), every cell translated by pure table walk; checks totality, bijectivity, and that consecutive curve indices are edge-adjacent (seam-exact via c_oct vertex merge); overlayable transparent panels with curve-address suffix labels |
| `hex_locality.py` | curve-quality metrics: adjacent-pair index gaps + range-query clustering (contiguous runs per random cap), vs the uuid/lineage order on the same grid and vs square-grid Hilbert/Morton — see "Locality, measured" below |
| `hex_inverse.py` | symbolic inverse (index → label) — attempted, refuted by its own census; kept as the record of the negative result (see Open items) |

## The artifact

`output/h9curve_rowtables_L5c.pkl` — the closed translator:

```
level       5                      # build depth (tables are depth-unbounded)
axiom       [12 L0 labels]         # the axiom tour, lexicographically-first L0 cycle
root_state  {L0 label: state}      # 12 root states
rows        {state: slot→rank row} # the 36 states, by their defining rows
frontier    []                     # empty = closed
T1          {(state, slot): rank}  # slot = (foster?, last lineage digit)
T2          {(state, rank): state} # total: 36 × 9, closed under reachability
```

Forward walk (see `hex_hilbert.fast_curve_address` / `hex_deep_sample.translate`):
build the **iterated one-generation ownership chain** (`h9_cell_ancestor`
per level — NOT a truncation of the uuid's digits: fosters diverge), then

```
S = root_state[label(a0)]; index = axiom.index(label(a0))
for each level k:  r = T1[(S, slot_k)];  index = index*9 + r;  S = T2[(S, r)]
```

Measured: ~1.3 µs/uuid for the walk, ~50 µs/uuid for the (naive) ancestor chains
(batched); indices verified bijective over 708,588 cells at L5 and over
every Greenwich window to L21 (67-bit indices - exceed uint64 beyond ~L18).

## Why the state is small — and why prescribed states failed

A block's row is the composition of two *individually simple, chained*
feeds:

* **cell → rank**: the parent's doors force the child path
  (door-functionality), and doors propagate by the crossing handshake —
  a chain rule down the ownership tree;
* **digit → cell**: the hex9 digit layout, fixed by grandparent-mode /
  parent (`_m_c2_hx_v2025` in hhg9), identical at every depth.

The transducer state is their *correlation* — how the digit frame sits
relative to the traversal frame when the curve arrives.  Every attempt
to express that correlation as a bounded function of the address alone
(digit suffixes, region-thread suffixes, label tails) failed with depth:
the door-side half lives in the curve's history, not the address.  The
moment the state was allowed to be the observable itself — the row —
the machine-learned coarsest congruence collapsed to horizon zero, no
hidden phase.  Threaded coordinates close where reconstructed ones
fail; only the 12 root states are ever computed from scratch.

The row is intrinsic (path × digit layout — absolute orientation
cancels), so the state space is finite a priori; 36 is its reachable
size.  Discovery decayed geometrically per level (6, +17, +7, +4, +2, 0)
with the tail confined to two octahedron-vertex lineage chains that fold
back at L5 — verified by the targeted L6 refinement, and the closed
system verified reachable-exactly-36 with no dangling transitions.

## Locality, measured

`hex_locality.py`, full-sphere L4 (78,732 cells), against the
uuid/lineage order on the same grid (the natural Morton/Z-order
analogue) and the classical square-grid pair at 256×256 (65,536 cells):

| avg contiguous runs per query | ~50 cells | ~500 | ~5000 |
|---|---|---|---|
| **hex9 curve** | **8.5** | **27.2** | **83.0** |
| hex9 uuid (lineage order) | 25.8 | 122.1 | 506.9 |
| square Hilbert | 8.0 | 25.2 | 80.1 |
| square Morton | 12.0 | 40.4 | 132.1 |

Runs per query is what a database pays for a spatial range scan.  The
hex9 curve matches square-grid Hilbert within ~4% at every query size
(both scale as √cells ≈ query perimeter, the theoretical Hilbert
behaviour), and beats its own grid's hierarchy order 3–6× — a larger
win than Hilbert-over-Morton on the square (~1.6×).

Adjacent-pair index gaps: 33.3% of hex9 edges are index-consecutive —
*exactly* the hexagonal ceiling (a path can make only 2 of 6 neighbours
consecutive), just as square Hilbert sits at its 2-of-4 = 50% ceiling.
Both curves are optimal on this axis; the ceilings differ by grid.  The
maximum cyclic gap is exactly N/2 — the closed loop's index-antipode,
as a Moore-type cycle requires.

Precision for the paper: this is Moore-type (every level a Hamiltonian
cycle — a closed loop, the natural form on a boundary-less sphere), and
it is "a" curve, not "the" curve: the construction is seeded by a fixed
axiom tour (lexicographically-first of the 1280 L0 cycles) plus the
canonical-edge convention; the grammar, tables, and 36 states are the
invariant part.

## Adapting this to other DGGRS

Nothing in the *method* is hex9-specific.  What it needs from a grid:

1. **A hierarchy with bounded block shapes.**  Cells at level k+1
   grouped into blocks of aperture size under level-k cells, with only
   finitely many block shapes up to congruence (hex9: one shape, 66
   internal Ham paths, everywhere).  Rep-tile / substitution refinements
   qualify; so do "coalesced" hierarchies like hex9's, where the
   grouping (ownership) differs from the addressing (lineage) — you
   then need the ownership map to be address-computable (hex9's
   `h9_cell_ancestor`; for H3-like non-nesting grids, a canonical
   roll-up plays this role).
2. **Exact turn classes.**  Turns must snap to a finite angular lattice
   in each cell's own chart.  Quantise at the finest class the
   *exceptional cells* produce — hex9's cone points need 30° where
   ordinary cells need 60°; an aperture-7 grid's per-level rotation
   changes the lattice; icosahedral grids' pentagons are the analogous
   exception.  A too-coarse snap silently merges pattern classes and
   yields false minima.
3. **A crossing handshake.**  For refinement to be deterministic, the
   fine arc realising a coarse tour step must be agreed by both blocks.
   Verify it; where the grid has doubled or degenerate adjacencies
   (hex9's six octahedron vertices), fix a convention (we take the
   lexicographically smallest arc).

Then the pipeline transfers directly:

* **Find the alphabet** (CP-SAT): enumerate block configs, minimise the
  number of pattern classes subject to a valid tour; then demand
  *self-similarity* — the alphabet must provide, as door transits, the
  turn classes its own patterns consume.  Expect the minimum to equal
  the number of ordered transit classes of your cell shape (hexagon: 5).
* **Learn the transducer — do not design it.**  Nodes = blocks, output
  = the slot→rank row, transitions = rank → child block.  Run
  bounded-horizon bisimulation (`hex_hilbert.learn_states`) and let the
  machine find the coarsest conflict-free state.  If your ownership
  grouping is intrinsic, expect the state to be the output row itself.
  Do NOT prescribe states from turn tuples, frames, or address
  suffixes: if the grid has any per-level rotation or mode alternation,
  bounded address contexts will appear to "almost work" and fail one
  level deeper, indefinitely.
* **Close the reachable set.**  Per-level state discovery should decay
  geometrically; the stragglers cluster around the exceptional cells.
  Close the tail with *targeted local refinement* (one level deeper,
  only around the frontier blocks — `hex_frontier.py` pattern; the
  global mesh at depth is cheap, it's per-cell Python geometry and
  config enumeration that must be kept local).
* **Verify deep.**  Translate a real-world windowed sample far beyond
  build depth on the grid's worst terrain (seams, exceptional cells)
  and check totality, bijectivity, and consecutive-index adjacency
  (`hex_deep_sample.py` pattern).

Comparative note: S2's Hilbert machinery is a hand-built 4-state
automaton available because the quad tree is a strict rep-tile with no
grouping/addressing split.  The contribution here is that the same
*kind* of object — small, total, closed transition tables — can be
**machine-learned and machine-closed** for grids where no one could
plausibly hand-design it (hexagonal, coalesced hierarchy, fosters,
cone points), with the state discovered rather than prescribed.  The 36
states are hex9's answer; other grids will get a different (finite)
number, and the learner tells you what it is.

## Open items

* **Symbolic inverse** (`hex_inverse.py`, open — attempted and gated
  out): index → label without geometry, by threading a ring-patch of
  labels down the walk with per-(state, rank) reconstruction recipes.
  The census REFUTED functionality at every ring depth tried (2–4):
  a cell's neighbourhood arrangement is not a function of its own
  state — ring cells' lineage parents sit where the NEIGHBOURING
  blocks' states put them.  A working inverse needs the joint
  PATCH-STATE (centre + neighbour states, adjacency-constrained) —
  finite, learnable with the same bounded-horizon machinery as the row
  automaton, but a second learning problem left for later.  A database
  that stores both columns does not need it.
* **Abstract closure proof**: enumerate the product automaton (digit
  layout classes × 30 door contexts) symbolically from the axiom —
  would replace "closed at all tested depths" with "closed, proven".
* **Row interpretation**: name the 36 states in product terms (layout
  class × door class) — the paper narrative writes itself from there.
