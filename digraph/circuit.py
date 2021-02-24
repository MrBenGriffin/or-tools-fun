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

class DiGraphSolver:

    def __init__(self, desc):
        self.model  = cp_model.CpModel()
        self.status = cp_model.UNKNOWN
        self.timing = None

        # AddCircuit needs a numeric index for each node.
        # Here's two lazy key->index / index->key lookups.
        self.keys = {k: i for i, k in enumerate(desc.nodes.keys()) }
        self.revs = {i: k for k, i in self.keys.items() }

        # Determine the objective of the problem
        self.min_maxing = desc.steps in ['min', 'max']
        self.find_max   = desc.steps == 'max'
        self.step_count = desc.steps if not self.min_maxing else None

        # Determine the start and stop nodes
        self.start = self.keys[desc.start]
        self.stop = self.keys[desc.stop]

        # Store the nodes dict in it's indexed form.
        self.nodes = {self.keys[head]: [self.keys[t] for t in tails] for head,tails in desc.nodes.items()}

        self.arcs = []
        self.vars = []
        self.result = []

    def setup(self):
        # AddCircuit uses a list of directed arcs as tuples: each is (head, tail, boolVariable)
        # where the  boolVar truth value represents if the arc is used or not used.
        # List comprehension: for each head(node), create an arc for each of it's tails.
        self.arcs = [
            (head,tail, self.model.NewBoolVar(f'{head}:{tail}')) for head, tails in self.nodes.items() for tail in tails
        ]

        # vars is a list of all the arcs defined in the problem.
        self.vars = [arc[2] for arc in self.arcs]

        # Add self loops for all *optional* nodes (because AddCircuit requires a Hamiltonian Circuit)
        # for this example, that's everywhere except for 'start' and 'stop'
        # We just use the keys of self.revs (the index values).
        loops = [(n, n, self.model.NewBoolVar(f'{n}:{n}')) for n in self.revs if n not in [self.start, self.stop]]
        self.arcs += loops

        # connect the stop variable to the start variable as a dummy arc to complete the hamiltonian circuit.
        # Because start and stop are not self-closing (non-optional), we don't need to set truth values.
        loop = (self.stop, self.start, self.model.NewBoolVar(f'loop'))
        self.arcs.append(loop)

        # Now add the circuit as a constraint.
        self.model.AddCircuit(self.arcs)

        # Now set the objective.
        if self.min_maxing:
            if self.find_max:
                 self.model.Maximize(sum(self.vars))  # look for the longest network.
            else:
                self.model.Minimize(sum(self.vars))   # look for the shortest network.
        else:
            self.model.Add(sum(self.vars) == self.step_count)

    def solve(self) -> bool:
        cp_solver = cp_model.CpSolver()
        cp_solver.parameters.max_time_in_seconds = 1
        cp_solver.parameters.num_search_workers = 12
        self.status = cp_solver.Solve(self.model)
        return self.summarise(cp_solver)

    def summarise(self, cp_solver) -> bool:
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self.store(cp_solver)
            return True
        else:
            if self.status == cp_model.INFEASIBLE:
                print(f"Challenge for {self.step_count} arc{'s ' if self.step_count > 1 else ' '}is infeasible after {cp_solver.WallTime()}s.")
            else:
                print(f"Solver ran out of time.")
            return False

    def store(self, cp_solver):
        self.timing = cp_solver.WallTime()
        used = [arc for arc in self.arcs if cp_solver.Value(arc[2])]
        arc = None, self.start
        while True:
            arc = next((link for link in used if link[0] == arc[1]), None)
            self.result.append(self.revs[arc[0]])
            if arc[1] == self.start:
                break
        self.step_count = len(self.result) - 1

    def show(self):
        print(f"{'-'.join(self.result)}")

class RandomDigraph:
    """
        define a problem.
        51 nodes, labelled 'a' ... 'Z'
        start at 'a', stop at 'Z'
        Each node other than 'Z' has a 4 outgoing arcs (random but not going to 'a')
    """
    def __init__(self):
        from random import sample  #
        names = 'abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        arcs = 4
        self.steps = 1
        self.start = 'a'
        self.stop = 'Z'
        but_first = set(names) ^ set(self.start)
        self.nodes = {v: sample(but_first - set(v), arcs) for v in names}
        self.nodes[self.stop] = []

    def print_nodes(self):
        for key, value in self.nodes.items():
            print(f'{key}: {value}')

def solve_with_steps(problem, steps, show) -> int:
    problem.steps = steps
    solver = DiGraphSolver(problem)
    solver.setup()
    if solver.solve() and show:
        solver.show()
    return solver.step_count

def solve_az_paths_of_a_random_digraph():
    problem = RandomDigraph()
    problem.print_nodes()
    print()
    min_steps = solve_with_steps(problem, 'min', True)
    max_steps = solve_with_steps(problem, 'max', False)
    for p in range(min_steps+1, max_steps+1):
        solve_with_steps(problem, p, True)


if __name__ == '__main__':
    solve_az_paths_of_a_random_digraph()
