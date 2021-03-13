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


class SolutionPrinter(cp_model.CpSolverSolutionCallback):

    def __init__(self, arcs, revs):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.arcs = arcs
        self.revs = revs
        self.solutions = 0

    def on_solution_callback(self):
        # Many thousands of solutions.
        self.solutions += 1
        return True
        result = []
        used = [arc for arc in self.arcs if self.Value(arc[2]) and arc[0] != arc[1]]
        arc = used[0]
        while arc:
            used.remove(arc)
            result.append(self.revs[arc[0]])
            arc = next((link for link in used if link[0] == arc[1]), None)
        if len(set(result)) != len(result):
            print('duplicates found!')
        if used:
            result.append(['unused:', used])
        print(f"{' '.join([str(x) for x in result])}")


class DiGraphSolver:

    def __init__(self, desc):
        self.model = cp_model.CpModel()
        self.status = cp_model.UNKNOWN
        self.timing = None
        self.score = None
        self.masters = None
        # Graph has 3 layers:
        #   1st is the node proper
        #   2nd is the set of node fixes (only one of which is allowed) which are presented as nodes of a digraph
        #   3rd is the list of potential tails for that fix.
        self.graph = desc.graph

        #   for setting up the circuit, we may as well extract the nodal fixes of each domino.
        self.nodal = {node: heads for m in self.graph.values() for node, heads in m.items()}

        # because AddCircuit requires numbers, we create a map of nodes->ints and it's reverse
        self.idx = {k: i for i, k in enumerate(self.nodal)}
        self.rev = {i: k for k, i in self.idx.items()}

        self.nodes = {self.idx[h]: [self.idx[t] for t in tails] for h, tails in self.nodal.items()}

        self.arcs = []
        self.result = []

    def setup(self):
        # Set the master pieces. they should all be used.
        # self.masters = {key: self.model.NewBoolVar(f'{key}') for key in self.pieces}

        # AddCircuit uses a list of directed arcs as tuples: each is (head, tail, boolVariable)
        # where the  boolVar truth value represents if the arc is used or not used.
        # For each head(node), create an arc for each of it's tails.
        self.arcs = [
            (self.idx[h], self.idx[t], self.model.NewBoolVar(f'{h}:{t}')) for h, ts in self.nodal.items() for t in ts
        ]
        self.model.Add(sum([a[2] for a in self.arcs]) == len(self.graph))

        # Lock out the graph from allowing both mirrors. This means that they have to be optionals.
        for m in self.graph.values():
            if len(m) > 1:
                heads = [a for (h, t, a) in self.arcs if self.rev[h] in m]
                self.model.Add(sum(heads) == 1)
                self.arcs += [(self.idx[n], self.idx[n], self.model.NewBoolVar(f'LP {n}')) for n in m]  # optional.

        # Now add the circuit as a constraint.
        self.model.AddCircuit(self.arcs)

    def solve(self) -> bool:
        cp_solver = cp_model.CpSolver()
        solution_printer = SolutionPrinter(self.arcs, self.rev)
        self.status = cp_solver.SearchForAllSolutions(self.model, solution_printer)
        return self.summarise(cp_solver, solution_printer.solutions)

    def summarise(self, cp_solver, solutions: int) -> bool:
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            print(f"Challenge found {solutions} solutions.")
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
        dominoes = set((x, y) for y in range(size + 1) for x in range(y, size + 1))
        # fix the rotations and store against each master
        fixed = {(a, b): {(a, b), (b, a)} for (a, b) in dominoes}
        # for each Domino; for each of it's fix; find those fixes from the Other dominoes which are potential tails.
        self.graph = {
            d: {
                d_fix: [  # connect the other(o) potential dominoes as tails to each fix
                    o_fix for o, o_fixes in fixed.items() if o != d for o_fix in o_fixes if o_fix[0] == d_fix[1]
                ] for d_fix in d_fixes
            } for d, d_fixes in fixed.items()
        }
        everything = True


def solve(problem):
    solver = DiGraphSolver(problem)
    solver.setup()
    solver.solve()


def solve_domino_digraph():
    #  2, 4, 6
    for n in [2, 4, 6, 7, 8, 9, 10, 11, 12]:
        print(f'trying {n}...')
        problem = DominoDigraph(n)
        solve(problem)


if __name__ == '__main__':
    solve_domino_digraph()
