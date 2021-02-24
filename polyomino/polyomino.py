# Copyright 2021 Ben Griffin
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

"""Polyomino Puzzle Solver
This solves filling a space with a set of defined polyominoes.

    A polyomino is a plane geometric figure formed by joining one or more equal squares edge to edge.
    It is a polyform whose cells are squares. It may be regarded as a finite subset of the regular square tiling.

This example includes a pentomino class.

A standard pentomino puzzle is to tile a rectangular box with the pentominoes, i.e. cover it without overlap and
without gaps. Each of the 12 pentominoes has an area of 5 unit squares, so the box must have an area of 60 units.
Possible sizes that use just one of each pentomino are 6×10, 5×12, 4×15 and 3×20.
The 6×10 case, first solved in 1960, has exactly 2339 solutions.
The 5×12 box has 1010 solutions, the 4×15 box has 368 solutions, and the 3×20 box has just 2 solutions
The 8×8 rectangle with a 2×2 hole in the center has 65 solutions.

This program allows any grid (with arbitrary holes) and allows a variety of shapes to be used to fill it.
e.g. 10x12 grid, with 8 x 'U' pentominoes and 1 or more 'F'.
If successful, it returns a box drawing of the result, e.g. for a 3x20 grid with 1 of each pentomino:
    ╔═══╦═╦═════╦═══════╦═╦═════╦═══╦═╦═════╗
    ║ ╔═╝ ╚═╗   ║ ╔═══╦═╝ ╚═╗ ╔═╝ ╔═╣ ╚═══╗ ║
    ║ ╚═╗ ╔═╩═══╩═╩═╗ ╚═══╗ ║ ║ ╔═╝ ╚═══╗ ║ ║
    ╚═══╩═╩═════════╩═════╩═╩═╩═╩═══════╩═╩═╝
"""
from ortools.sat.python import cp_model


class SolvePolyominoPuzzle:
    def __init__(self):
        self.allow_gaps = False
        self.maximising = False
        self.status = cp_model.UNKNOWN
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = 10
        self.solver.parameters.num_search_workers = 12
        self.pieces = None
        self.ground = None
        self.pos_items = None
        self.presence = {}

    def process(self, pieces, problem: dict):
        """
        Given a problem and the pieces we construct a SAT model and then solve it.
        """
        model = cp_model.CpModel()

        """
        If gaps is true, a solution may include gaps.
        """
        self.allow_gaps = 'gaps' in problem and problem['gaps']

        """
        Keep pieces for the print function
        Define the space as given in the problem, defaulting to the 6×10 square
        Define available pieces as given in the problem, defaulting to at least one of each piece.
        """
        self.pieces = pieces
        self.ground = problem['fill'] if 'fill' in problem else set((x, y) for y in range(0, 6) for x in range(0, 10))
        available = problem['use'] if 'use' in problem else {k: -1 for k in pieces.names}

        """
        For each lib piece that's being used (by default that's 63 - each of the 12 shapes flipped/rotated)..
        See if it can be placed at each point in space, and if so, add it into the model as a potential presence
        of the solution. Also add it's coordinates into a placement dict so that we can test for overlaps later. 
        """
        placement = {}
        for named_fix in pieces.lib:
            if named_fix[0] in available:
                for point in self.ground:
                    if pieces.legal(named_fix, self.ground, point):
                        self.presence[tuple((*named_fix, point))] = model.NewBoolVar(f"{named_fix}:{point}")
                        placement[tuple((*named_fix, point))] = pieces.translate(named_fix, point)

        """
        Compose free - the entire set of lib+offset pieces by each 'free' piece (eg, the set of all "K")
        """
        free = {k: [bv for i, bv in self.presence.items() if i[0] == k] for k in available}

        """
        Compose pos_items - this is the set of all 5 points of each possible piece at each x,y in the space.
        We will use this for constraint setting and for rendering.
        """
        self.pos_items = {x: set() for x in self.ground}
        for fixed, p_bv in self.presence.items():
            pp = placement[fixed]
            for point in pp:
                self.pos_items[point].add(fixed)

        """
        Constraints are: 
          1: Limit the count of free pieces as defined by the problem
          2: Exactly piece per space of space 
        
        The problem allows to solve with specific numbers of pieces, or to maximise certain pieces.
        For maximising, we use 0 or a -ve number (the -ve will be the minimum for that piece)
        eg. ['F': -2, 'I': 0, 'L': 2, 'N': 2] = Use exactly 2L and 2N maximising F,I with 2+ F and 0+ I.
        """
        to_maximise = []
        for k, allowed in available.items():
            if allowed > 0:
                model.Add(sum(free[k]) == allowed)
            else:
                model.Add(sum(free[k]) >= -allowed)  # if we want at least 1, use -1
                to_maximise += free[k]

        if to_maximise:
            model.Maximize(sum(to_maximise))
            self.maximising = True

        """
        For each xy, constrain the sum of pos_items to 1 (1 piece per x,y).
        """
        for pt_points in self.pos_items.values():
            items = [self.presence[i] for i in pt_points]
            if self.allow_gaps:
                model.Add(sum(items) <= 1)
            else:
                model.Add(sum(items) == 1)

        """
        Can now solve.
        """
        self.status = self.solver.Solve(model)

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

    @staticmethod
    def box(*walls) -> str:
        """
        :param walls: tuple of 4 bool: W,E,N,S
        :return: related box drawing character.
        """
        value = 0
        for i, wall in enumerate(walls):
            value |= 1 << i if wall else 0
        return (' ', '╸', '╺', '═', '╹', '╝', '╚', '╩', '╻', '╗', '╔', '╦', '║', '╣', '╠', '╬')[value & 0x0F]

    def draw(self):
        """
        Derive grid size, based upon the min/max x,y values set in the space
        """
        x1 = min(self.ground, key=lambda a: a[0])[0]
        y1 = min(self.ground, key=lambda a: a[1])[1]
        x2 = max(self.ground, key=lambda a: a[0])[0]
        y2 = max(self.ground, key=lambda a: a[1])[1]

        """
        Compose grid dict, based upon solver values
        """
        grid = {}
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                grid[(x - x1, y - y1)] = None
                if (x, y) in self.pos_items:
                    for maybe in self.pos_items[x, y]:
                        if self.solver.Value(self.presence[maybe]):
                            grid[(x - x1, y - y1)] = maybe

        """
        Draw grid using box drawing characters
        """
        x_dim = x2 + 1 - x1
        y_dim = y2 + 1 - y1
        for y in range(y_dim + 1):
            line = ""
            for x in range(x_dim + 1):
                nw = grid[(x - 1, y - 1)] if 0 <= y - 1 < y_dim and 0 <= x - 1 < x_dim else '~'
                ne = grid[(x - 0, y - 1)] if 0 <= y - 1 < y_dim and 0 <= x - 0 < x_dim else '~'
                sw = grid[(x - 1, y - 0)] if 0 <= y - 0 < y_dim and 0 <= x - 1 < x_dim else '~'
                se = grid[(x - 0, y - 0)] if 0 <= y - 0 < y_dim and 0 <= x - 0 < x_dim else '~'
                line += self.box(nw != sw, ne != se, nw != ne, sw != se) + self.box(ne != se, ne != se, False, False)
            print(line)

class ShapeCollection:
    """
     A set of shapes of solid squares
    """
    def __init__(self, points):
        self.lib = {}
        self.names = set(points.keys())
        self.fix(points)

    @staticmethod
    def _normalise_pts_(d: list):
        # calculate the boundary and the size of each dimension for a shape
        lx, bx = min(x[0] for x in d), 1 + max(x[0] for x in d)
        ly, by = min(x[1] for x in d), 1 + max(x[1] for x in d)
        grid = [[[x, y] in d for y in range(ly, by)] for x in range(lx, bx)]
        res = [[x, y] for x in range(bx-lx) for y in range(by-ly) if grid[x][y]]
        return res

    def legal(self, key: tuple, ground: set, offs: tuple) -> bool:
        """
        Given an (x,y) offset, and a 'space' of legal points check to see if this pentomino can
        be legally placed in it.
        """
        point_set = self.lib[key]
        for pt in point_set:
            xy = pt[0] + offs[0], pt[1] + offs[1]
            if xy not in ground:
                return False
        return True

    def translate(self, key: tuple, offs: tuple) -> set:
        """
            return the normalised pentomino translated by offset (x,y).
        """
        return {tuple((pt[0] + offs[0], pt[1] + offs[1])) for pt in self.lib[key]}

    @staticmethod
    def _square_p(pts, p=0):
        # symmetry group: 8 2D rotations constrained by sequences of 90-degree rotations and reflections
        return [[[+a, +b], [-b, +a], [-a, -b], [+b, -a], [+b, +a], [-a, +b], [-b, -a], [+a, -b]][p % 8] for a, b in pts]

    def fix(self, points: dict):
        for k, pts in points.items():
            # Try all 8 2D rotations on a shape and eliminate symmetric identities by using a hash of the result.
            restrict = dict()
            base = ShapeCollection._normalise_pts_(pts)
            for f in range(8):
                fix = ShapeCollection._normalise_pts_(ShapeCollection._square_p(base, f))
                fix_str = str(fix)
                restrict[hash(fix_str)] = fix
            for i, fix in enumerate(restrict.values()):
                self.lib[(k, i)] = fix


class PentominoSet(ShapeCollection):
    """
     A pentomino is a polyomino with exactly 5 squares
     When rotations and reflections are not considered to be distinct shapes, there are 12 'free' pentominoes.
     When reflections are considered distinct, there are 18 one-sided pentominoes (there are 6 'chiral' pentominoes).
     When rotations are also considered distinct, there are 63 'lib' pentominoes.
     Each pentomino has a name that loosely represents it's shape.

     Here each pentomino is defined on a 5x5 grid, centred at 2,2, with co-ordinates 0..4 in x and y
     the transform/translate methods both move the centre to 0,0 as required.
    """
    def __init__(self):
        pentominoes = {
            "F": [[2, 1], [1, 2], [2, 2], [2, 3], [3, 3]],
            "I": [[2, 0], [2, 1], [2, 2], [2, 3], [2, 4]],
            "L": [[2, 1], [3, 1], [2, 2], [2, 3], [2, 4]],
            "N": [[1, 1], [1, 2], [2, 2], [2, 3], [2, 4]],
            "P": [[2, 1], [3, 2], [2, 2], [3, 3], [2, 3]],
            "T": [[2, 1], [2, 2], [1, 3], [2, 3], [3, 3]],
            "U": [[1, 2], [2, 2], [3, 2], [1, 3], [3, 3]],
            "V": [[1, 1], [2, 1], [3, 1], [3, 2], [3, 3]],
            "W": [[1, 1], [2, 1], [2, 2], [3, 2], [3, 3]],
            "X": [[2, 1], [1, 2], [2, 2], [3, 2], [2, 3]],
            "Y": [[2, 0], [2, 1], [2, 2], [3, 2], [2, 3]],
            "Z": [[1, 1], [2, 1], [2, 2], [2, 3], [3, 3]]
        }
        super().__init__(pentominoes)


def example(space_set):
    shapes = PentominoSet()
    solver = SolvePolyominoPuzzle()
    challenge = {
        'gaps': False,
        'fill': space_set,
        'use': {'F': 1, 'I': 1, 'L': 1, 'N': 1, 'P': 1, 'T': 1, 'U': 1, 'V': 1, 'W': 1, 'X': 1, 'Y': 1, 'Z': 1}
    }
    solver.process(shapes, challenge)
    if solver.show():
        solver.draw()


if __name__ == '__main__':
    # commonly used spaces in pentomino problems.
    spaces = [(12, 5), (10, 6), (15, 4), (20, 3)]
    special = set((x, y) for y in range(0, 8) for x in range(0, 8)) - {(3, 3), (3, 4), (4, 3), (4, 4)}
    for sx, sy in spaces:
        space = set((x, y) for y in range(sy) for x in range(sx))
        example(space)
    example(special)


