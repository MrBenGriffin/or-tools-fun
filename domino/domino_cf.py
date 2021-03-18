# Copyright 2021 Ben Griffin; All Rights Reserved.
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
    An or-tools example implementing/demonstrating the AddCircuit constraint with space fitting.
    We want to take a standard set of dominoes, link them as one would in a typical domino game, and fit them within
    an enclosed space.  Because we are fitting them closely, we will run doubles (eg, [3:3]) end to end, just as other
    dominoes. There are no 'spinners' in this model - we are looking for a chain (or circuit) that goes through every
    domino once.

    A domino has 2 numbers, and it could be represented [a:b].. The numbers may be the same, in which it's called a
    'double'.

    Each domino has 1 (doubles) or 2 (non-double) fixes (flips) [0:0]=[0:0], ([0:1]=[0:1],[1:0]).
    The word 'fix' here is used as it comes out of the idea of rotational symmetry.

    While it is true that a circuit can be run either clockwise or anti-clockwise, in each case their is only one fix
    used for each domino (eg. if we see [3:4][4:2]  we won't find [4:3] or [2:4] in the same circuit, as they are the
    same domino just rotated, or flipped, around). Likewise the fix of a domino is relevant to the chain (so, in the
    previous example, it doesn't work if the [3:4] is flipped to [4:3] because [4:3][4:2] isn't a valid connection).

    Given that there are one of each domino, (eg for 6-dominoes there are 28), and if each domino covers 1 square of a
    grid, we can see that we need a grid of 28*2 = 56 squares to accommodate all 6-dominoes, and this will leave no
    spaces.

    So for each square of the grid, it will be covered by one half of a domino. One of the neighbouring squares will
    be covered by the other half of that domino.

    When we look at a chain of dominoes, we normally use the terms 'head' and 'tail' in the direction of the circuit.
    For instance, with the part circuit [3:4]->[4:0]->[0:1]. Each 'join' is an arc of a graph. For instance, for the join
    between [3:4] and [4:0], the [3:4] is at the 'head' of the arc, and the [4:0] is at the 'tail'.
    What MAKES the tail available as a possible tail in a chain is the fact that it's number is the same.
    So, it's useful to represent the role of each number of the fix of each domino as 'a' and 'b'.

    [3:4]->[4:0]->[0:1]
    [a:b]->[a:b]->[a:b]

    Of course, the same three dominoes could be in another sequence where they are reversed, so the 'a' and 'b' is
    linked to the current circuit and the current fix being used.

    But importantly, for the 'b' of each fix in a circuit, BOTH the 'a' of the same fix, and the 'a' of the next fix
    in the circuit will be orthogonally adjacent to the 'b'.

    Each domino therefore covers two squares, and each space is either A or B, and they are orthogonally adjacent.

        ╔═══════╦═══════╦═══╗       This shows a filled group of 4-dominoes in a 5x6 grid.
    5   ║ 0 > 2 – 2 > 2 – 2 ║       The y-axis values and the x-axis values are added, as well as the chain
        ╠═|═════╬═══════╣ v ║       indicated by a – or a | between dominoes. Also, each domino is marked with
    4   ║ 0 < 0 – 0 < 3 ║ 4 ║       a 'v', '^', '>' or '<' representing the direction of the circuit such that
        ╠═══════╬═════|═╬═|═╣       the following domino is at the tail of the arc, headed by the current domino.
    3   ║ 1 > 3 – 3 > 3 ║ 4 ║
        ╠═|═════╬═══╦═══╣ v ║
    2   ║ 1 < 1 – 1 ║ 4 – 4 ║
        ╠═══════╣ ^ ║ v ╠═══╣
    1   ║ 4 > 0 – 0 ║ 1 – 1 ║
        ╠═|═════╬═══╩═══╣ v ║       In this case the circuit is going clockwise, and the [3:4] LOOKS like it's [4:3].
    0   ║ 4 < 3 – 3 < 2 – 2 ║  <--- We can see that both the 3 of the [3:4] and the 4 of the adjacent tailed [4:0]
        ╚═══════╩═══════╩═══╝       are adjacent to the 4 of the [3:4].
          0   1   2   3   4

    Being a square grid, it's easy enough for us to give an identity of each square in the grid, using [x,y] following
    normal cartesian coordinates.  We also know that each square of the grid is only going to be covered by an 'a'
    of a fix, or the 'b' of a fix.  We can represent that in two ways = one with the number of the fix, and a bool
    'is_a' suggesting whether or not it's the 'a'. But we can also represent it as [p,q] with the final value being
    the head-connector, and the prior value being the 'a', (which together represent one of the possible fixes).

    Therefore we can define our set of booleans to be modelled, run along the dimensions [x,y,p,q].
    This answers the question 'is the square at [x,y] covered by the (p,q or q,p) fix with the q resting on x,y?
    It doesn't represent the fix! If we look at the [4:3] in the grid above, the boolean [0,0,3,4] is True, and the
    boolean [1,0,4,3] is True. The actual fix being used by the circuit is dealt with by the AddCircuit constraint.

    AddCircuit uses a list of directed arcs as tuples: each is (head, tail, boolVariable) where the  boolVar truth value
    represents if the arc is used or not used. For each head(node), create an arc for each of it's tails.
    I have kept these booleans separate from the grid variables - this may make the model more complex than is
    strictly necessary, because we will have to tie both of these sets of variables together with 'glue'.

"""
from ortools.sat.python import cp_model


class SolutionManager(cp_model.CpSolverSolutionCallback):

    @staticmethod
    def box_draw(grid: dict):
        """
        General 2D grid drawing using box drawing characters
        grid x,y coordinates start at 0.
        grid is a dict[x,y] of a tuple of index, and identity tuple.
        eg grid[3,2] = (1,(3,4,5)) means that the point at 3,2 is the '4' value of the 3,4,5 shape
        """
        def box(*walls) -> str:
            """
            :param walls: tuple of 4 bool: W,E,N,S
            :return: related box drawing character.
            """
            idx = 0
            for i, wall in enumerate(walls):
                idx |= 1 << i if wall else 0
            return (' ', '╸', '╺', '═', '╹', '╝', '╚', '╩', '╻', '╗', '╔', '╦', '║', '╣', '╠', '╬')[idx & 0x0F]

        """
        Derive grid size, based upon the min/max x,y values set in the space
        """
        x1 = min([xy[0] for xy in grid])
        y1 = min([xy[1] for xy in grid])
        x2 = max([xy[0] for xy in grid]) + 1
        y2 = max([xy[1] for xy in grid]) + 1
        mt = (0, (' ',))

        for y in range(y1, y2 + 1):
            line = ''
            for x in range(x1, x2 + 1):
                nwi, nw_o = grid[x - 1, y - 1] if (x - 1, y - 1) in grid else mt
                nei, ne_o = grid[x - 0, y - 1] if (x - 0, y - 1) in grid else mt
                swi, sw_o = grid[x - 1, y - 0] if (x - 1, y - 0) in grid else mt
                sei, se_o = grid[x - 0, y - 0] if (x - 0, y - 0) in grid else mt
                n, e, w, s = nw_o != ne_o, ne_o != se_o, nw_o != sw_o, se_o != sw_o
                line += box(w, e, n, s) + 3 * box(e, e, False, False)
            print(line)
            if y < y2:
                line = ""
                for x in range(x1, x2):
                    i, obj = grid[x, y]
                    x, oth = grid[x - 1, y] if (x - 1, y) in grid else mt
                    cw = obj != oth
                    line += f'{box(False, False, cw, cw)} {obj[i]} '
                print(f'{line}║')

    def __init__(self, place):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.solver = None
        self.place = place
        self.solutions = 0
        self.show_fixes = False
        self.show_circuit = False
        self.show_space = True

    def val(self, variable):
        if self.solver:
            return self.solver.Value(variable)
        else:
            return self.Value(variable)

    def on_solution_callback(self, solver=None):
        self.solver = solver
        self.solutions += 1
        if self.show_fixes:
            used = [fs for fs, var in self.fixes.items() if self.val(var)]
            print(f"{' '.join([str(x) for x in used])}")

        if self.show_circuit:
            result = []
            used = [
                (h, t) for fs in self.graph.values()
                for h, hd in fs['fixes'].items()
                for t, tv in hd['tail_vars'].items() if self.val(tv)
            ]
            arc = used[0]
            while arc:
                used.remove(arc)
                result.append(arc[0])
                arc = next((link for link in used if link[0] == arc[1]), None)
            if len(set(result)) != len(result):
                print('duplicates found!')
            if used:
                result.append(['unused:', used])
            print(f"{' '.join([str(x) for x in result])}")
        if self.show_space:
            self.box_draw(self.set_grid())

    def set_grid(self):
        """
        [x,y]: index of, and tuple of shape identity (represented as a tuple of numbers)
        eg, [0,0]: 0,(4,1)  => the 4 of the 4,1 domino is at [0,0]
        """
        return {(x, y): (i, (a, b)) for (x, y, a, b, i), var in self.place.items() if self.val(var)}


class DominoBraneSolver:

    def __init__(self, graph, space):
        self.model = cp_model.CpModel()
        self.status = cp_model.UNKNOWN

        """
         Graph has 3 layers:
           1st is the node proper
           2nd is the set of node fixes (only one of which is allowed) which are presented as nodes of a digraph
           3rd is the list of potential tails for that fix.
        """
        self.graph = graph
        self.space = space
        self.place = dict()
        self.fixes = dict()

    def set_circuit(self):
        # AddCircuit uses a list of directed arcs as tuples: each is (head, tail, boolVariable)
        # where the  boolVar truth value represents if the arc is used or not used.
        # For each head(node), create an arc for each of it's tails.

        # For setting up the circuit, fixes of each domino as a distinct node.
        # 'nodes' includes every possible fix there is.
        self.fixes = {node: self.model.NewBoolVar(f'fix {node}') for dom, fixes in self.graph.items() for node in fixes['fixes']}

        # Because AddCircuit requires numbers, we create a map of nodes->ints
        idx = {k: i for i, k in enumerate(self.fixes)}

        # Because AddCircuit requires a Hamiltonian Circuit, one needs to add loops to optional nodes.
        # Here, that is where there are multiple fixes for a domino.
        arcs = []
        loops = []
        for fs in self.graph.values():
            d_arcs = []
            for h, hd in fs['fixes'].items():
                hd['tail_vars'] = dict()
                for t in hd['tails']:
                    arc = self.model.NewBoolVar(f'arc {h}:{t}')
                    self.model.AddImplication(arc, self.fixes[h])
                    self.model.AddImplication(arc, self.fixes[t])
                    self.model.AddImplication(self.fixes[h].Not(), arc.Not())      # !head => ! arc
                    self.model.AddImplication(self.fixes[t].Not(), arc.Not())      # !tail => ! arc
                    hd['tail_vars'][t] = arc
                    d_arcs.append((idx[h], idx[t], arc))
                if len(fs['fixes']) > 1:
                    loops.append((idx[h], idx[h], self.model.NewBoolVar(f'Loop {h}')))
            self.model.Add(sum([a[2] for a in d_arcs]) == 1)
            arcs += d_arcs

        # Ensure that every domino is used.
        self.model.Add(sum([a[2] for a in arcs]) == len(self.graph))

        # Now add the circuit as a constraint.
        self.model.AddCircuit(arcs + loops)

    def set_placements(self):
        # Set up the variables
        fixes_to_be_placed = len(self.space) // 2
        self.model.Add(sum(self.fixes.values()) == fixes_to_be_placed)          # This acts as a 'hint' - speed.

        for (a, b), fix in self.fixes.items():                                   # for each domino directory..
            for (x, y) in self.space:
                if self.space[x, y] is None:
                    self.place[x, y, a, b, 1] = self.model.NewBoolVar(f'H {a, b} at {x, y}')  # 'b' of the a,b fix at x,y
                    self.place[x, y, a, b, 0] = self.model.NewBoolVar(f'T {a, b} at {x, y}')  # 'b' of the a,b fix at x,y
                else:
                    if self.space[x, y] == b:
                        self.place[x, y, a, b, 1] = self.model.NewBoolVar(f'H {a, b} at {x, y}')  # 'b' of the a,b fix at x,y
                    if self.space[x, y] == a:
                        self.place[x, y, a, b, 0] = self.model.NewBoolVar(f'T {a, b} at {x, y}')  # 'b' of the a,b fix at x,y

        # Connect fixes to space.
        for (a, b), fix in self.fixes.items():
            self.model.Add(sum([self.place[x, y, a, b, 1] for x, y in self.space if (x, y, a, b, 1) in self.place]) == sum([self.fixes[a, b]]))
            self.model.Add(sum([self.place[x, y, a, b, 0] for x, y in self.space if (x, y, a, b, 0) in self.place]) == sum([self.fixes[a, b]]))

        # Each square will either be the head (1) or a tail (0) of a fix.
        for (x, y) in self.space:
            self.model.Add(sum([self.place[x, y, a, b, f] for a, b in self.fixes for f in [0, 1] if (x, y, a, b, f) in self.place]) == 1)  # 1 half at each square.
            for (a, b) in self.fixes:
                if (x, y, a, b, 1) in self.place:
                    adj = [ij for ij in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)] if ij in self.space]
                    halves = [self.place[i, j, a, b, 0] for (i, j) in adj if (i, j, a, b, 0) in self.place]
                    self.model.AddBoolOr(halves).OnlyEnforceIf(self.place[x, y, a, b, 1])

        # Connect domino tails to their heads.
        for dd in self.graph.values():  # for each domino directory..
            for (a, b), hd in dd['fixes'].items():            # for the head.ab of each fix
                for (c, d), arc in hd['tail_vars'].items():   # for the tail.uv of each tail
                    for (x, y) in self.space:
                        if (x, y, a, b, 1) in self.place:
                            adj = [ij for ij in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)] if ij in self.space]
                            tails = [self.place[i, j, c, d, 0] for (i, j) in adj if (i, j, c, d, 0) in self.place]
                            self.model.AddBoolOr(tails).OnlyEnforceIf(self.place[x, y, a, b, 1]).OnlyEnforceIf(arc)

        # Reduce ambiguity -- (8 seconds instead of 1.5).
        for (x, y) in self.space:
            for (a, b) in self.fixes:
                if (x, y, a, b, 1) in self.place:
                    adj = [ij for ij in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)] if ij in self.space]
                    vals = [self.place[i, j, u, v, f] for f in [0, 1] for (i, j) in adj for (u, v) in self.fixes if u == b and (i, j, u, v, f) in self.place]
                    if a == b:
                        self.model.Add(sum(vals) == 2).OnlyEnforceIf(self.place[x, y, a, b, 1])
                    else:
                        self.model.Add(sum(vals) == 1).OnlyEnforceIf(self.place[x, y, a, b, 1])

    def setup(self):
        self.set_circuit()
        self.set_placements()

    def solve(self, find_all: bool = False) -> bool:
        cp_solver = cp_model.CpSolver()
        if not find_all:
            cp_solver.parameters.num_search_workers = 12
        solution_manager = SolutionManager(self.place)
        if find_all:
            self.status = cp_solver.SearchForAllSolutions(self.model, solution_manager)
        else:
            self.status = cp_solver.Solve(self.model)
            solution_manager.on_solution_callback(cp_solver)
        return self.summarise(cp_solver)

    def summarise(self, cp_solver) -> bool:
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"Solved after {cp_solver.WallTime()}s.")
            return True
        else:
            if self.status == cp_model.INFEASIBLE:
                print(f"Challenge is infeasible after {cp_solver.WallTime()}s.")
            else:
                print(f"Solver ran out of time.")
            return False


class DominoDigraph:
    """
        28 Dominoes - 0:0 to 6:6
        56 Nodes = 1 for each end of each Domino as a head.
        Each end can be a head or a tail.
        Each end, as a tail, is only a head to the domino's own head.
        Each head only points to the tails (not heads) of other dominoes.
        It's own 3 or any other 1 <-[1:3]->It's own 1 or to any other 3.
        The loop is closed, no dominoes are optional.
    """
    def __init__(self, size: int):
        # the primary objects
        dominoes = set((x, y) for y in range(size+1) for x in range(y, size+1))
        # fix the rotations and store against each master
        fixed = {(a, b): {(a, b), (b, a)} for (a, b) in dominoes}
        # for each Domino; for each of it's fix; find those fixes from the Other dominoes which are potential tails.
        self.graph = {
            d: {
                'fixes': {
                    d_fix: {   # connect the other(o) potential dominoes as tails to each fix
                        'tails': [
                            o_fix for o, o_fixes in fixed.items() if o != d for o_fix in o_fixes if o_fix[0] == d_fix[1]
                        ]
                    } for d_fix in d_fixes
                }
             } for d, d_fixes in fixed.items()
        }


class Space:
    def __init__(self, size):
        spaces = [(size+1, size+2)]  # for 6 dominoes this will be 8,7
        for sx, sy in spaces:
            self.space = {(x, y): None for y in range(sy) for x in range(sx)}


def solve(graph, space, find_all=False):
    solver = DominoBraneSolver(graph, space)
    solver.setup()
    solver.solve(find_all)


def solve_domino_digraph(scale):
    graph = DominoDigraph(scale).graph
    n = None

    # The following all have unique answers.
    db6_0001 = [                # PUZZLE                        SOLUTION
                                # ╔═══╦═══╦═══╦═══╦═══╦═══╦═══╗ ╔═══════╦═══════╦═══════╦═══╗
        [0, n, n, 0, n, n, 0],  # ║ 0 ║   ║   ║ 0 ║   ║   ║ 0 ║ ║ 0   1 ║ 5   0 ║ 0   0 ║ 0 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ╠═══╦═══╬═══════╬═══════╣   ║
        [n, 1, n, 1, n, 1, n],  # ║   ║ 1 ║   ║ 1 ║   ║ 1 ║   ║ ║ 0 ║ 1 ║ 5   1 ║ 1   1 ║ 4 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ║   ║   ╠═══════╬═══╦═══╬═══╣
        [3, n, 2, 2, 2, n, 4],  # ║ 3 ║   ║ 2 ║ 2 ║ 2 ║   ║ 4 ║ ║ 3 ║ 2 ║ 2   2 ║ 2 ║ 1 ║ 4 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ╠═══╬═══╬═══════╣   ║   ║   ║
        [n, 6, n, 3, n, 3, n],  # ║   ║ 6 ║   ║ 3 ║   ║ 3 ║   ║ ║ 3 ║ 6 ║ 6   3 ║ 4 ║ 3 ║ 5 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ║   ║   ╠═══╦═══╬═══╩═══╬═══╣
        [3, n, 4, 3, 4, n, 5],  # ║ 3 ║   ║ 4 ║ 3 ║ 4 ║   ║ 5 ║ ║ 3 ║ 4 ║ 4 ║ 3 ║ 4   3 ║ 5 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ╠═══╩═══╣   ║   ╠═══════╣   ║
        [n, 5, n, 2, n, 5, n],  # ║   ║ 5 ║   ║ 2 ║   ║ 5 ║   ║ ║ 3   5 ║ 4 ║ 2 ║ 2   5 ║ 5 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ╠═══════╬═══╩═══╬═══════╬═══╣
        [6, n, n, 1, n, n, 6],  # ║ 6 ║   ║   ║ 1 ║   ║   ║ 6 ║ ║ 6   5 ║ 4   1 ║ 1   6 ║ 6 ║
                                # ╠═══╬═══╬═══╬═══╬═══╬═══╬═══╣ ╠═══════╬═══════╬═══════╣   ║
        [n, 6, n, 0, n, 2, n]   # ║   ║ 6 ║   ║ 0 ║   ║ 2 ║   ║ ║ 6   6 ║ 6   0 ║ 0   2 ║ 2 ║
                                # ╚═══╩═══╩═══╩═══╩═══╩═══╩═══╝ ╚═══════╩═══════╩═══════╩═══╝
    ]

    db4_0001 = [
        [n, n, 0, n, n],
        [n, 1, n, 1, n],
        [n, n, 2, n, n],
        [n, 3, n, 3, n],
        [2, n, 4, n, 4],
        [n, 0, n, 0, n]
    ]
    db4_demo = [
        [n, 4, n, 4, n],
        [n, 3, n, 3, n],
        [n, n, 2, n, n],
        [n, 1, n, 1, n],
        [n, 0, n, 0, n],
        [n, 3, n, 4, n]
    ]

    space = Space(scale).space
    for (x, y) in space:
        space[x, y] = db4_demo[y][x]
    solve(graph, space, False)  # True=Find every match. False=find first match.


if __name__ == '__main__':
    solve_domino_digraph(4)    # db6_0001 currently takes 80 seconds to find all, about 18secs to find first fit.
