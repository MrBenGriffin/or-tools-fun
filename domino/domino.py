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

"""Domino Puzzle Solver
This solves filling a space with a set of dominoes.
"""
from ortools.sat.python import cp_model


class DominoPuzzleSolver:
    def __init__(self):
        self.allow_gaps = False
        self.maximising = False
        self.status = cp_model.UNKNOWN
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = 6000
        self.solver.parameters.num_search_workers = 6
        self.solver.parameters.cp_model_presolve = False
        self.solver.parameters.linearization_level = 0
        self.solver.parameters.cp_model_probing_level = 0

        self.pieces = None
        self.ground = None
        self.pos_items = None
        self.presence = {}
        self.placement = {}

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
        Define the space as given in the problem, defaulting to 7×8 rectangle
        Define available pieces as given in the problem, defaulting to at least one of each piece.
        """
        self.pieces = pieces
        self.ground = problem['fill'] if 'fill' in problem else set((x, y) for y in range(7) for x in range(8))
        available = problem['use'] if 'use' in problem else {k: 1 for k in pieces.names}

        """
        For each lib piece that's being used (by default that's 112 = 4*28 - each of the 28 shapes rotated)..
        See if it can be placed at each point in space, and if so, add it into the model as a potential presence
        of the solution. Also add it's coordinates into a placement dict so that we can test for overlaps later. 
        """
        for (name, rot), piece in pieces.lib.items():
            if name in available:
                for point in self.ground:
                    if piece.legal(self.ground, point):
                        self.presence[(name, rot, point)] = model.NewBoolVar(f"{name, rot, point}")
                        self.placement[(name, rot, point)] = Domino(name, rot, point)

        """
        Compose pos_items - this is the set of all points of each domino at each x,y in the space.
        We may use this for constraint setting and for rendering.
        """
        self.pos_items = {x: set() for x in self.ground}
        for fix, p_bv in self.presence.items():
            domino = self.placement[fix]
            for point in domino.pos:
                self.pos_items[point].add(fix)

        for k in self.pos_items:
            self.pos_items[k] = list(self.pos_items[k])
        """
        Now do the domino bit - match numbers
        """
        offsets = [(0, 1), (0, -1), (1, 0), (-1, 0)]
        for (x, y) in self.ground:
            legals = [(x+dx, y+dy) for dx, dy in offsets if (x+dx, y+dy) in self.ground]
            for fix in self.pos_items[(x, y)]:
                fbv = self.presence[fix]
                main = self.placement[fix]
                # m_up = main.rotation in [0, 180]
                value = main.value_at((x, y))
                connections = []
                for pos in legals:
                    for fxo in self.pos_items[pos]:
                        other = self.placement[fxo]
                        # o_up = other.rotation in [0, 180]
                        # this constraint prevents 0-0 counting as an internal path.
                        if other != main and other.value_at(pos) == value:
                            connections.append(self.presence[fxo])
                model.Add(sum(connections) == 1).OnlyEnforceIf(fbv)

        """
        Constraints are: 
          1: Limit the count of free pieces as defined by the problem
          2: Exactly piece per space of space 
        Compose free - the entire set of lib+offset pieces by each 'free' piece (eg, the set of all "K")
        This will have a set of eg 28 dominoes, with each of the variables in it representing each position.
        so that will be 194 for a 7*8 grid.
        """
        free = {k: [bv for (name, pos, offset), bv in self.presence.items() if name == k] for k in available}
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
            nw, sw, ne, se = '~', '~', '~', '~'
            for x in range(x_dim + 1):
                nw = grid[(x - 1, y - 1)] if 0 <= y - 1 < y_dim and 0 <= x - 1 < x_dim else '~'
                ne = grid[(x - 0, y - 1)] if 0 <= y - 1 < y_dim and 0 <= x - 0 < x_dim else '~'
                sw = grid[(x - 1, y - 0)] if 0 <= y - 0 < y_dim and 0 <= x - 1 < x_dim else '~'
                se = grid[(x - 0, y - 0)] if 0 <= y - 0 < y_dim and 0 <= x - 0 < x_dim else '~'
                line += self.box(nw != sw, ne != se, nw != ne, sw != se) + 3 * self.box(ne != se, ne != se, False, False)
            print(line)
            #  now to do y-intermediate.
            if y < y_dim:
                line = ""
                for x in range(x_dim):
                    p = grid[(x, y)]
                    domino = self.placement[p]
                    value = str(domino.value_at((x, y)))
                    w = grid[(x - 1, y)] if 0 <= x - 1 < x_dim else '~'
                    line += f'{self.box(False, False, p != w, p != w)} {value} '
                print(f'{line}║')


class Domino:
    """
     A domino is two adjacent squares, with a value in each square.
     While subject to rotations, each number is fixed to an end.
    """
    rot_map = {
        0: [(0, 0), (1, 0)],
        90: [(0, 0), (0, 1)],
        180: [(0, 0), (1, 0)],
        270: [(0, 0), (0, 1)]
    }

    def __init__(self, values: tuple, rotation=0, offset=(0, 0)):
        self.l, self.r = values
        self.x, self.y = offset
        self.rotation = None
        self.pts = None
        self.pos = None
        self.a, self.b = None, None
        self.setup(rotation)

    # def pos(self) -> list:
    #     return [(x + self.x, y + self.y) for (x, y) in self.pts]

    def setup(self, theta: int):
        self.rotation = theta
        self.pts = Domino.rot_map[self.rotation]
        self.pos = [(x + self.x, y + self.y) for (x, y) in self.pts]
        self.a, self.b = (self.l, self.r) if theta in [0, 90] else (self.r, self.l)

    def value_at(self, pos: tuple) -> [None, int]:
        for i, pt in enumerate(self.pos):
            if pt == pos:
                return self.a if i == 0 else self.b
        return None

    def legal(self, ground: set, offs: tuple) -> bool:
        """
        Given an (x,y) offset, and a 'space' of legal points check to see if a domino can
        be legally placed in it.
        """
        ox, oy = offs
        for (x, y) in self.pts:
            if (x + ox, y + oy) not in ground:
                return False
        return True


class DominoCollection:
    """
     A domino is two adjacent squares, with a value in each square.
    """

    def __init__(self, values):
        self.lib = {(value, rot): Domino(value, rot) for value in values for rot in [0, 90, 180, 270]}
        self.names = values


class Domino6Set(DominoCollection):
    def __init__(self):
        dominoes = set((x, y) for y in range(7) for x in range(y, 7))
        super().__init__(dominoes)


class Domino5Set(DominoCollection):
    def __init__(self):
        dominoes = set((x, y) for y in range(6) for x in range(y, 6))
        super().__init__(dominoes)


def example():
    spaces = [(8, 7)]  # should be 8,7
    space = set()
    for sx, sy in spaces:
        space = set((x, y) for y in range(sy) for x in range(sx))
    shapes = Domino6Set()
    solver = DominoPuzzleSolver()
    challenge = {
        'gaps': False,
        'fill': space
    }
    solver.process(shapes, challenge)
    if solver.show():
        solver.draw()


if __name__ == '__main__':
    example()
