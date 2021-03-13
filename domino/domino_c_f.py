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
    An or-tools example implementing/demonstrating the AddCircuit constraint
    Find path from 'start' to 'stop' through a directed graph (digraph) of nodes and arcs in a given number of steps.
    steps can be a specific number, 'min', or 'max'

    The problem codes the digraph as a dict of nodes : a list of the arcs from that node.
    For instance.
    a: ['o', 'd', 'b', 'y']  # node 'a' has 4 outgoing arcs:  a->o, a->d, a->b, a->y

    This example:
    (1) Generates a problem with 61 nodes, all but the 'stop' node having 4 outgoing arcs.
    (2) Prints the problem digraph
    (3) Solves the minimum and maximum paths.
    (4) Solves (or fails) for seeking path-lengths from minimum to maximum steps long printing the result.
"""
from ortools.sat.python import cp_model


class SolutionCallback(cp_model.CpSolverSolutionCallback):
    def __init__(self, graph, space, place):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.solver = None
        self.graph = graph
        self.space = space
        self.place = place
        self.solutions = 0
        self.show_circuit = False
        self.show_space = True

    def val(self, variable):
        if self.solver:
            return self.solver.Value(variable)
        else:
            return self.Value(variable)

    def on_solution_callback(self, solver=None):
        self.solver = solver
        # Many thousands of solutions.
        self.solutions += 1
        if self.show_circuit:
            result = []
            used = [
                (h, t) for fs in self.graph.values()
                for h, hd in fs['fixes'].items()
                for t, tv in hd['tail_vars'] if self.val(tv)
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
            self.draw()

    def draw(self):
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
        x1 = min(self.space, key=lambda a: a[0])[0]
        y1 = min(self.space, key=lambda a: a[1])[1]
        x2 = max(self.space, key=lambda a: a[0])[0]
        y2 = max(self.space, key=lambda a: a[1])[1]
        mt = ('~', ' ')

        """
        Compose grid dict, based upon solver values
        """
        grid = {}
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                grid[x - x1, y - y1] = mt
                for dd in self.graph.values():
                    for (a, b) in dd['fixes']:
                        if self.val(self.place[(x, y, a, b)]):
                            grid[x - x1, y - y1] = (a, b)

        """
        Draw grid using box drawing characters
        """
        x_dim = x2 + 1 - x1
        y_dim = y2 + 1 - y1
        for y in range(y_dim + 1):
            line = ""
            # So, we are drawing the interstices here, looking from the top left of each cell.
            for x in range(x_dim + 1):
                nwa, nwb = grid[x - 1, y - 1] if 0 <= y - 1 < y_dim and 0 <= x - 1 < x_dim else mt
                nea, neb = grid[x - 0, y - 1] if 0 <= y - 1 < y_dim and 0 <= x - 0 < x_dim else mt
                swa, swb = grid[x - 1, y - 0] if 0 <= y - 0 < y_dim and 0 <= x - 1 < x_dim else mt
                sea, seb = grid[x - 0, y - 0] if 0 <= y - 0 < y_dim and 0 <= x - 0 < x_dim else mt
                w = not((nwa == swa and nwb == swb) or (nwa == swb and nwb == swa))  # is there a western interstice?
                e = not((nea == sea and neb == seb) or (nea == seb and neb == sea))  # is there a western interstice?
                n = not((nwa == nea and nwb == neb) or (nwa == neb and nwb == nea))  # is there a western interstice?
                s = not((sea == swa and seb == swb) or (sea == swb and seb == swa))  # is there a western interstice?
                # eyes = [((nwa, nwb), (nea, neb), (swa, swb), (sea, seb)), (w, e, n, s)]
                line += box(w, e, n, s) + 3 * box(e, e, False, False)
            print(line)
            #  now to do y-intermediate.
            if y < y_dim:
                line = ""
                for x in range(x_dim):
                    ca, cb = grid[x, y]
                    wa, wb = grid[x - 1, y] if 0 <= x - 1 < x_dim else mt
                    cw = not((ca == wa and cb == wb) or (ca == wb and cb == wa))
                    line += f'{box(False, False, cw, cw)} {cb} '
                print(f'{line}║')


class DiGraphSolver:

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
        # nodes = {node: heads['tails'] for m in self.graph.values() for node, heads in m.items()}
        nodes = [node for dom, fixes in self.graph.items() for node in fixes['fixes']]

        # Because AddCircuit requires numbers, we create a map of nodes->ints
        idx = {k: i for i, k in enumerate(nodes)}

        # Because AddCircuit requires a Hamiltonian Circuit, one needs to add loops to optional nodes.
        # Here, that is where there are multiple fixes for a domino.
        arcs = []
        loops = []
        for fs in self.graph.values():
            d_arcs = []
            for h, hd in fs['fixes'].items():
                hd['tail_vars'] = [(t, self.model.NewBoolVar(f'arc {h}:{t}')) for t in hd['tails']]
                d_arcs += [(idx[h], idx[t], var) for t, var in hd['tail_vars']]
                if len(fs['fixes']) > 1:
                    loops.append((idx[h], idx[h], self.model.NewBoolVar(f'Loop {h}')))
            self.model.Add(sum([a[2] for a in d_arcs]) == 1)
            arcs += d_arcs

        # Ensure that every domino is used.
        self.model.Add(sum([a[2] for a in arcs]) == len(self.graph))

        # Now add the circuit as a constraint.
        self.model.AddCircuit(arcs + loops)

    def set_placements(self):
        """
            A domino has 2 numbers, and is represented [A:B]
            Each domino has 1 or 2 fixes (flips) [0:0] =1: [0:0], ([0:1] = 2: [0:1],[1:0])
            So for each pt in space, it belongs to 1 fix of 1 domino.
            Each domino therefore has 2 spaces, and each space is either A or B, and they are orthogonally adjacent.
            As A and B are arbitrary, let's say that the circuit of the domino goes from A to B
            Each placement is therefore a boolean of [X,Y,A,B] or [X,Y,B,A]
            If there are numbers on the grid, that limits which variables can go on it, but that's all.
            All placements are represented by X*Y*Fixes*2 boolVars.
        """
        # Set up the variables
        for dd in self.graph.values():                                   # for each domino directory..
            for (a, b), hd in dd['fixes'].items():                       # for each fix..
                self.fixes[a, b] = self.model.NewBoolVar(f'fix {a, b}')  # store a fix variable.
                for (x, y) in self.space:
                    self.place[x, y, a, b] = self.model.NewBoolVar(f'fix {a,b} at {x,y}')  # the 'b' of this fix at x,y

        # Basic sums equivalences.
        for dd in self.graph.values():                                   # for each domino directory..
            dom_group = []                                               # group all the vars for domino
            for (a, b), hd in dd['fixes'].items():                       # for each fix..
                for arc in [v[1] for v in hd['tail_vars']]:              # for (ab)->(tail) each tail (from b)
                    self.model.AddImplication(arc, self.fixes[a, b])     # if the arc is true, the fix is true.
                fix_group = []                                           # group xy vars over fix
                for (x, y) in self.space:
                    fix_group.append(self.place[x, y, a, b])             # add to the fix_group.
                    self.model.AddImplication(self.place[x, y, a, b], self.fixes[a, b])  # fix(a,b) at x,y => fixes(a,b)
                self.model.Add(sum(fix_group) == 3 - len(dd['fixes']))   # 2 fixes?, 1 of each; 1 fix?, we need 2.
                dom_group += fix_group                                   # append the fix group for to the domino group.
            self.model.Add(sum(dom_group) == 2)                          # 2 ends to each domino.
        self.model.Add(sum(self.place.values()) == len(self.space))      # space is filled.
        for (x, y) in self.space:                                        # one half-domino at each point in space.
            all_at_xy = [self.place[k] for k in self.place if k[0] == x and k[1] == y]
            self.model.Add(sum(all_at_xy) == 1)

        # connect half-dominoes together
        for dd in self.graph.values():                                   # half-dominoes are adjacent to each other.
            for (a, b), hd in dd['fixes'].items():                       # Likewise tails are adjacent to their heads.
                for (x, y) in self.space:                                # adj = legal and orthogonally adjacent to x, y
                    adj = [ij for ij in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)] if ij in self.space]
                    h_list = [self.place[x, y, a, b].Not()]               # domino's 'A' is next to the B.
                    for (i, j) in adj:                                    # for each point adjacent to B...
                        ij_half = self.place[i, j, b, a]                  # the 'A' half of the domino
                        h_list.append(ij_half)                            # is added to the half-list.
                    self.model.AddBoolOr(h_list)  # one of the possible points around xy is the A, OR xy is not B.

        # connect domino tails to their heads. ** There's something wrong going on around here!! **
        for dd in self.graph.values():                                   # half-dominoes are adjacent to each other.
            for (a, b), hd in dd['fixes'].items():                       # Likewise tails are adjacent to their heads.
                for (x, y) in self.space:
                    adj = [ij for ij in [(x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)] if ij in self.space]
                    t_list = []                                           # the active tail is also next to B
                    for (i, j) in adj:                                    # for each point adjacent to B...
                        for ((p, q), tail) in hd['tail_vars']:            # for each tail at ij of the ab fix at x,y
                            self.model.AddBoolAnd([self.fixes[a, b], self.fixes[p, q]]).OnlyEnforceIf(tail)
                            self.model.AddImplication(self.place[i, j, p, q], self.fixes[p, q])  # the tail at x,y implies the tail
                            t_list.append(self.place[i, j, p, q])         # add the potentials tails to the tails list.
                    self.model.AddBoolOr(t_list).OnlyEnforceIf(self.place[x, y, a, b])

    def setup(self):
        # Set the master pieces. they should all be used.
        # placements uses circuit values.
        self.set_circuit()
        self.set_placements()

    def solve(self) -> bool:
        cp_solver = cp_model.CpSolver()
        cp_solver.parameters.num_search_workers = 12
        # cp_solver.parameters.cp_model_presolve = False
        # cp_solver.parameters.log_search_progress = True
        # cp_solver.parameters.linearization_level = 0
        # cp_solver.parameters.max_presolve_iterations = 1000
        # cp_solver.parameters.cp_model_probing_level = 1000
        solution_callback = SolutionCallback(self.graph, self.space, self.place)
        self.status = cp_solver.Solve(self.model)
        return self.summarise(cp_solver, solution_callback)
        # self.status = cp_solver.SearchForAllSolutions(self.model, solution_printer)

    def summarise(self, cp_solver, callback) -> bool:
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            callback.on_solution_callback(cp_solver)
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
        # everything = True


class Space:
    def __init__(self, size):
        spaces = [(size+1, size+2)]  # for 6 dominoes this will be 8,7
        for sx, sy in spaces:
            self.space = {(x, y): None for y in range(sy) for x in range(sx)}


def solve(graph, space):
    solver = DiGraphSolver(graph, space)
    solver.setup()
    solver.solve()


def solve_domino_digraph(scale):
    graph = DominoDigraph(scale).graph
    space = Space(scale).space
    solve(graph, space)


if __name__ == '__main__':
    solve_domino_digraph(4)
