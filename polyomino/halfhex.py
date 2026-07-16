# Copyright 2024 Ben Griffin
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

"""Half-hexagon Puzzle Solver
This solves filling a space with a set of defined half-hexagons.

A half-hexagon is defined by a hexagon bisected along it's long diameter,
or three equilateral triangles adjacent to each other. ⬣

The puzzle here is to enumerate the ways in which nine half-hexagons can tile a half-hexagon.

"""

from ortools.sat.python import cp_model


class SolutionPrinter(cp_model.CpSolverSolutionCallback):

    def __init__(self, ground, pos_items, presence):
        cp_model.CpSolverSolutionCallback.__init__(self)
        self.hashes = set()
        self.ground = ground
        self.pos_items = pos_items
        self.presence = presence
        self.solutions = 0
        self.ref = [c for c in self.ground]
        self.ref.sort(key=lambda e: (e[1], e[0]))  # to get string values.

    def on_solution_callback(self):
        p = {}
        for c in self.ground:
            for x in self.pos_items[c]:
                if self.Value(self.presence[x]):
                    p[c] = f'{x[0]}'

        fz = ''.join([p[x] for x in self.ref])
        if fz not in self.hashes:
            self.solutions += 1
            self.hashes.add(fz)
            print(f'{len(self.hashes):02d}:    {fz}')
        return True


class HHSolver:

    def __init__(self):
        self.allow_gaps = False
        self.maximising = False
        self.status = cp_model.UNKNOWN
        self.solver = cp_model.CpSolver()
        self.solver.parameters.enumerate_all_solutions = True
        self.solver.parameters.cp_model_probing_level = 2000
        # self.solver.parameters.num_search_workers = 20
        self.solver.parameters.cp_model_presolve = True
        # self.solver.parameters.log_search_progress = True
        self.solver.parameters.linearization_level = 20000
        self.solver.parameters.max_presolve_iterations = 20000
        self.solver.parameters.cp_model_probing_level = 20000

        self.pieces = None
        self.ground = None
        self.pos_items = None
        self.presence = {}
        self.pieces = None
        self.ground = None
        self.flowers = None

    def process(self, pieces, ground):
        """
        Given a problem and the pieces we construct a SAT model and then solve it.
        """
        model = cp_model.CpModel()
        self.pieces = pieces
        self.ground = ground
        self.find_flowers()

        """
        Also add it's coordinates into a placement dict so that we can test for overlaps later.
        `placement` is a dict keyed by each legally oriented piece and offset showing the spaces covered. 
        We will invert this to hold the items by position.
        """
        placement = {}
        for named_fix in pieces.lib:
            for point in self.ground:
                if pieces.legal(named_fix, self.ground, point):
                    self.presence[tuple((named_fix, *point))] = model.NewBoolVar(f"{named_fix}:{point}")
                    placement[tuple((named_fix, *point))] = pieces.translate(named_fix, point)

        free = {k: [bv for (w, x, y), bv in self.presence.items() if w == k] for k in pieces.names}

        """
        Compose pos_items - at each legal position in the space, identify which placement(s) can cover it.
        So this is the invert of placement.
        We will use this for constraint setting and for rendering.
        """
        self.pos_items = {x: set() for x in self.ground}
        for fixed in self.presence.keys():
            pp = placement[fixed]
            for point in pp:
                self.pos_items[point].add(fixed)

        """
        For each legal position in the space constrain the sum of pos_items to 1 (1 piece per x,y).
        """
        for pt_points in self.pos_items.values():
            items = [self.presence[i] for i in pt_points]
            model.Add(sum(items) == 1)

        for flower in self.flowers:
            pt = {px: [self.presence[p] for i in flower for p in self.pos_items[i] if p[0] == f'{px}'] for px in range(6)}

            u0 = model.new_bool_var('')
            d1 = model.new_bool_var('')
            u2 = model.new_bool_var('')
            d3 = model.new_bool_var('')
            u4 = model.new_bool_var('')
            d5 = model.new_bool_var('')

            model.add_at_least_one(pt[0]).only_enforce_if(u0)  # sets u0 to True when the sum == 0
            model.add_at_least_one(pt[1]).only_enforce_if(d1)  # sets u0 to True when the sum == 0
            model.add_at_least_one(pt[2]).only_enforce_if(u2)  # sets u0 to True when the sum == 0
            model.add_at_least_one(pt[3]).only_enforce_if(d3)  # sets u4 to True when the sum == 0
            model.add_at_least_one(pt[4]).only_enforce_if(u4)  # sets u2 to True when the sum == 0
            model.add_at_least_one(pt[5]).only_enforce_if(d5)  # sets u2 to True when the sum == 0

            model.add_bool_or([u0, u2, u4])  # must have a bit...
            model.add_bool_or([d1, d3, d5])  # of both!

        """
        Can now solve.
        """
        solution_printer = SolutionPrinter(self.ground, self.pos_items, self.presence)
        self.solver.enumerate_all_solutions = True
        self.status = self.solver.Solve(model, solution_callback=solution_printer)

    def find_flowers(self):
        # a flower is made of 6 shared triangles.
        # we only need to consider the even (up-triangles) as sources.
        self.flowers = set()
        for (x, y) in self.ground:
            if y % 2 == 0:
                flower = frozenset({(x, y), (x, y+1), (x, y+2), (x-1, y+1), (x-1, y+2), (x-1, y+3)})
                if flower.issubset(self.ground):
                    self.flowers.add(flower)

    def show(self) -> bool:
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if self.maximising:
                print(f"Solver places {int(self.solver.ObjectiveValue())} pieces in {self.solver.WallTime()}s")
            else:
                print(f"Solved challenge in {self.solver.WallTime()}s")
            return True
        else:
            if self.status == cp_model.INFEASIBLE:
                print(f"Solver says the challenge is infeasible after {self.solver.WallTime()}s.")
            else:
                print(f"Solver ran out of time.")
            return False


class ShapeCollection:

    def __init__(self, points):
        self.lib = points
        self.names = set(points.keys())

    def legal(self, key: tuple, ground: set, offs: tuple) -> bool:
        """
        Given an (x,y) offset, and a 'space' of legal points check to see if this shape can
        be legally placed in it.
        """
        proj = self.translate(key, offs)
        return False if not proj else proj.issubset(ground)

    def translate(self, key: tuple, offs: tuple) -> None | set:
        """
            return the normalised shape translated by offset (x,y).
        """
        pts = self.lib[key]
        for pt in pts:
            if ((pt[1] + offs[1]) % 2) != (pt[1] % 2):
                return None
        return {tuple((pt[0] + offs[0], pt[1] + offs[1])) for pt in pts}


class HHSet(ShapeCollection):
    def __init__(self):
        _half_hex = {
            "0": {(0, 0), (0, 1), (0, 2)},
            "1": {(0, 1), (1, 0), (1, 1)},
            "2": {(0, 1), (1, 0), (0, 2)},
            "3": {(0, 1), (0, 2), (0, 3)},
            "4": {(0, 0), (0, 1), (1, 0)},
            "5": {(1, 1), (1, 2), (0, 3)}
        }
        super().__init__(_half_hex)


def example(space_set):
    shapes = HHSet()
    solver = HHSolver()
    solver.process(shapes, space_set)
    solver.show()


if __name__ == '__main__':
    # hh = set((x, y) for y in range(0, 6) for x in range(0, 6)) - {(3, 5), (4, 3), (4, 4), (4, 5), (5, 1), (5, 2), (5, 3), (5, 4), (5, 5)}
    dollar = set((x, y) for x in range(9) for y in range((8-x) * 2 - 1))
    dollar = dollar - {(0, 14)}
    # print(dollar)
    example(dollar)
