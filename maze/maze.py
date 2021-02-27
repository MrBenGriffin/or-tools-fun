import timeit

from ortools.sat.python import cp_model
from enum import IntFlag
import random

class Com(IntFlag):
    # These values are strongly tied the order of items in Wall.concrete.
    W = 0x0001
    E = 0x0002
    N = 0x0004
    S = 0x0008

class Wall:
    concrete = [' ', '╸', '╺', '━', '╹', '┛', '┗', '┻', '╻', '┓', '┏', '┳', '┃', '┫', '┣', '╋']

    def __init__(self, n_s: bool, dim):
        self.dim = dim
        self.blocked = False
        self.door = False
        self.route = False
        self.cells = {com: None for com in Com}
        self.n_s = n_s   # dividing NS => True, dividing EW => False

    def make_door(self, cell_dir):
        other = self.cells[cell_dir]
        if not self.blocked and other:
            other.mined = True
            self.door = True
            return other
        else:
            return None

    def set_cell(self, cell, com_from):
        # the other cell is saying '(self) is what i see in the north'
        # therefore the other is in the south of (self).
        opposite = {Com.W: Com.E, Com.E: Com.W, Com.N: Com.S, Com.S: Com.N}
        self.cells[opposite[com_from]] = cell

    def is_edge(self):  # If on the edge, then one of my wall cells will be None.
        if self.n_s:
            return (self.cells[Com.N] is None) or (self.cells[Com.S] is None)
        else:
            return (self.cells[Com.W] is None) or (self.cells[Com.E] is None)

    def can_be_dug(self, com_to):
        cell = self.cells[com_to]
        return not self.blocked and cell and not cell.mined

    def __str__(self):
        if self.door:
            return ' ' if not self.route else '.'
        return str(Wall.concrete[Com.E | Com.W]) if self.n_s else str(Wall.concrete[Com.N | Com.S])

class Cell:
    last = None
    last_mined = None

    def __init__(self, walls):
        self.visited = False
        self.is_entry = False
        self.is_goal = False
        self.mined = False
        self.walls = walls
        for com, wall in self.walls.items():
            wall.set_cell(self,com)

    def exits(self):
        return [k for k, v in self.walls.items() if v and v.door]

    def neighbours(self):
        faces = {Com.N: (0, 1), Com.E: (1, 0), Com.S: (0, -1), Com.W: (-1, 0)}
        return [faces[face] for face in Com if self.walls[face] and self.walls[face].door]

    def route_to(self, offs):
        routes = {(0, 1): Com.N, (1, 0): Com.E,(0, -1): Com.S, (-1, 0): Com.W}
        self.walls[routes[offs]].route = True

    def walls_that_can_be_dug(self):
        return [compass for compass, wall in self.walls.items() if wall.can_be_dug(compass)]

    def make_door_in(self, com):
        cell = self.walls[com].make_door(com)
        if cell:
            Cell.last_mined = cell
        return cell

    def visit(self, face: Com, move: bool = False):
        # Returns a 3-tuple: what is ahead, the current room, if current room is the goal.
        self.visited = True
        destination = self.walls[face].cells[face] if move and self.walls[face].door else self
        return destination.walls[face].door, destination, destination.is_goal

    def __str__(self):
        return "." if self.visited else "*" if self.is_goal else "o" if self.is_entry else " "

class Maze:
    def __init__(self, x, y):
        self.mined = False
        self.floor = None
        self.x = x
        self.y = y

        self.ns_walls = { (i,j): Wall(True,  (i, j)) for j in range(y + 1) for i in range(x) }
        self.ew_walls = { (i,j): Wall(False, (i, j)) for j in range(y) for i in range(x + 1) }
        self.cells = { (i,j): Cell(self._cell_walls(i, j)) for i in range(x) for j in range(y)}

    def mine(self, bod):
        while not bod.finished():
            bod.run()
            self.mined = True

    def _cell_walls(self, x, y):
        return {
            Com.N: self.ns_walls[x, y + 1] if (x, y + 1) in self.ns_walls else None,
            Com.S: self.ns_walls[x,     y] if (x,     y) in self.ns_walls else None,
            Com.E: self.ew_walls[x + 1, y] if (x + 1, y) in self.ew_walls else None,
            Com.W: self.ew_walls[x,     y] if (x,     y) in self.ew_walls else None
        }

    def _corners(self, x, y) -> str:
        found = {
            Com.N: self.ew_walls[x, y - 1] if (x, y - 1) in self.ew_walls else None,
            Com.S: self.ew_walls[x,     y] if (x,     y) in self.ew_walls else None,
            Com.E: self.ns_walls[x,     y] if (x,     y) in self.ns_walls else None,
            Com.W: self.ns_walls[x - 1, y] if (x - 1, y) in self.ns_walls else None
        }
        value = sum([com for com, wall in found.items() if wall and not wall.door])
        return str(Wall.concrete[value])

    def __str__(self):  # __str__ method here is just for easy visualisation purposes.
        line = ''
        for j in range(self.y + 1):  # reversed: print goes from top to bottom..
            line_ns = ""
            line_ew = ""
            for i in range(self.x + 1):
                line_ns += str(self._corners(i, j))
                if (i, j) in self.ns_walls:
                    line_ns += str(self.ns_walls[i, j])
                if (i, j) in self.ew_walls:
                    line_ew += str(self.ew_walls[i, j])
                if (i, j) in self.cells:
                    line_ew += str(self.cells[i, j])
            line += line_ns + "\n" + line_ew + "\n"
        return line

class Miner:
    def __init__(self, start):
        self.track = [start]
        self.is_miner = True
        self.sequence = 0
        self.forward = 0

    def dig(self, the_maze):
        if not self.track:
            if not the_maze.mined:
                the_maze.mined = True
        else:
            self.sequence += 1
            the_wall = None
            while self.track and the_wall is None:
                if self.sequence & 15 != 0:  # cheaper than % 16
                    this_cell = self.track[-1]
                    walls_to_dig = this_cell.walls_that_can_be_dug()
                    if walls_to_dig:
                        the_wall = self.mine(walls_to_dig, this_cell)
                    else:
                        self.forward = 0
                        self.track.pop()
                else:
                    self.forward = 0
                    cell_index = random.randrange(len(self.track))
                    this_cell = self.track[cell_index]
                    walls_to_dig = this_cell.walls_that_can_be_dug()
                    if walls_to_dig:
                        the_wall = self.mine(walls_to_dig, this_cell)
                    else:
                        del self.track[cell_index]

    def mine(self, walls_to_dig, this_cell):
        the_wall = random.choice(walls_to_dig)
        next_cell = this_cell.make_door_in(the_wall)
        if next_cell:
            self.track.append(next_cell)
            self.forward += 1
        else:
            the_wall = None
        return the_wall

def solve(maze: Maze, start, goal):
    # The solver has restricted access to the maze:
    # 1: It can get the name and index of each cell.
    # 2: It can be given the directions (as x,y tuples) of available cell-neighbours.
    # 3: It can mark a given doorway in a cell as being on the route to a goal.
    model = cp_model.CpModel()
    i_to_n = {idx: pos for idx, pos in enumerate(maze.cells)}
    n_to_i = {pos: idx for idx, pos in enumerate(maze.cells)}
    doors = {}
    for head, (nx, ny) in i_to_n.items():
        # neighbours are given as dx/dy because a cell doesn't hold it's own coordinate.
        for (dx, dy) in maze.cells[nx, ny].neighbours():
            tail = n_to_i[nx + dx, ny + dy]
            doors[(nx, ny), (dx, dy)] = (head, tail, model.NewBoolVar(f'{head}:{tail}'))
    loops = [(head, head, model.NewBoolVar(f'{head}')) for head in i_to_n if head not in {n_to_i[start], n_to_i[goal]}]
    tie = [(n_to_i[goal], n_to_i[start], model.NewBoolVar(f'loop'))]
    model.AddCircuit(list(doors.values()) + loops + tie)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1
    solver.parameters.num_search_workers = 12
    if summarise(solver, solver.Solve(model)):
        for (cell, offset), (h, t, door) in doors.items():
            if solver.Value(door):
                maze.cells[cell].route_to(offset)
        print(str(the_maze))
        print(f'Route was found in {solver.WallTime()}s')

def summarise(solver: cp_model.CpSolver, status) -> bool:
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return True
    else:
        if status == cp_model.INFEASIBLE:
            print(f"Challenge is infeasible after {solver.WallTime()}s.")
        else:
            print(f"Solver ran out of time.")
        return False

class Crawler:
    def __init__(self, start: Cell):
        self.cw = {Com.E: Com.S, Com.S: Com.W, Com.W: Com.N, Com.N: Com.E}
        self.ccw = {Com.E: Com.N, Com.S: Com.E, Com.W: Com.S, Com.N: Com.W}
        self.cell = start      # don't know much about this.
        self.facing = Com.E         # start..
        self.arrived = False

    def solve(self):
        while not self.arrived:
            if self.cw[self.facing] in self.cell.exits():
                self.facing = self.cw[self.facing]
                can_move, self.cell, self.arrived = self.cell.visit(self.facing, True)
            else:
                self.facing = self.ccw[self.facing]


if __name__ == '__main__':
    # Set up a maze, and set an entrypoint and a goal.
    maze_size = (40, 40)
    the_maze = Maze(*maze_size)
    # set an entry point and a goal.
    start = (0, 0)
    goal = maze_size[0]-1, maze_size[1]-1
    # mark start and goal on the maze.
    the_maze.cells[start].is_entry = True
    the_maze.cells[goal].is_goal = True
    # Now create it using a miner (who can start anywhere)
    the_miner = Miner(the_maze.cells[start])
    while not the_maze.mined:
        the_miner.dig(the_maze)
    # The maze is now dug and can be printed (if you want to solve it yourself.)
    # print(str(the_maze))
    # Or just give it to CpSolver ;-D
    solve(the_maze, start, goal)
    # and a simple state-based wall_edge crawler?
    crawler = Crawler(the_maze.cells[start])
    print(f'Simple crawler took {timeit.Timer("crawler.solve()", setup="from __main__ import crawler").timeit()}')

