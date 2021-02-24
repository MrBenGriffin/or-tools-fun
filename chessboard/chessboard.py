# Copyright 2020 Ben Griffin; All Rights Reserved.
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
Given a library of pieces and their moves, 
and given a requirement of which pieces to use, and how many,
determine a solution such that no piece can be taken by another.

This is an extension of the N-Queens puzzle
E.g. find a solution for 6 queens, 2 knights, and maximum (2) kings.

"""
import sys
from ortools.sat.python import cp_model

def chessboard(challenge:dict, library:dict, board_size:int):
    model = cp_model.CpModel()

    # A dict for each piece in the problem, bool == presence in square of the board.
    # using bool over int is always better (as ints are converted to bool anyway)
    presence = {p: {
        (x, y): model.NewBoolVar(f"{p}:{x},{y}")
        for x in range(board_size)
        for y in range(board_size)
    } for p in challenge}

    for p, p_moves in presence.items():
        moves = library[p]
        for q, q_moves in presence.items():
            for (x, y), qv in q_moves.items():
                pv = p_moves[x, y]
                if p != q:
                    # No superposition allowed.
                    # If a p is here, then a q cannot be here.
                    model.AddImplication(pv, qv.Not())
                for dx, dy in moves:
                    nx, ny = x + dx, y + dy
                    if (nx, ny) in q_moves:  # This clips illegal positions.
                        model.AddImplication(pv, q_moves[nx, ny].Not())

    maximising = False
    for p,required in challenge.items():
        if required > 0:
            model.Add(sum(presence[p].values()) == required)
        else:
            model.Add(sum(presence[p].values()) >= 0)
            model.Maximize(sum((presence[p]).values()))
            maximising = True
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 60
    solver.parameters.num_search_workers = 12
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        if maximising:
            print(f"Solver places {int(solver.ObjectiveValue())} pieces in {solver.WallTime()}s")
        else:
            print(f"Solved {challenge} in {solver.WallTime()}s")
        colors = ('□■' * (1 + board_size // 2))  # extra for the odd lines.
        board = [[colors[x + y % 2] for x in range(board_size)] for y in range(board_size)]
        for x in range(board_size):
            for y in range(board_size):
                for p in challenge:
                    if solver.Value(presence[p][x,y]):
                        board[x][y] = p

        print()
        for y in board:
            print(' ' + ''.join(y))
        print()
    else:
        if status == cp_model.INFEASIBLE:
            print(f"Solver says the challenge '{challenge}' is infeasible after {solver.WallTime()}s.")
        else:
            print(f"Solver ran out of time.")

def main(board:int):
    # The library is made of a symbol, and the list of it's possible moves as x,y offsets.
    library = {
        '♚': [(0, 1), (0, -1), (-1, 0), (1, 0), (1, 1), (-1, -1), (-1, 1), (1, -1)],
        '♛': [(0, x) for x in range(1, board)] + [(0, -x) for x in range(1, board)] \
             + [(x, 0) for x in range(1, board)] + [(-x, 0) for x in range(1, board)] \
             + [(x, x) for x in range(1, board)] + [(x, -x) for x in range(1, board)] \
             + [(-x, x) for x in range(1, board)] + [(-x, -x) for x in range(1, board)]
        ,
        '♝': [(x, x) for x in range(1, board)] + [(x, -x) for x in range(1, board)] \
             + [(-x, x) for x in range(1, board)] + [(-x, -x) for x in range(1, board)],
        '♞': [(1, 2), (2, 1), (2, -1), (1, -2), (-1, -2), (-2, -1), (-2, 1), (-1, 2)],
        '♜': [(0, x) for x in range(1, board)] + [(0, -x) for x in range(1, board)] \
             + [(x, 0) for x in range(1, board)] + [(-x, 0) for x in range(1, board)],
    }
    # the problem states how many of each piece must be on the board.
    # one piece may be 0, and then the solver will find the maximum for that piece.
    challenge = {'♚': 0, '♛': 6, '♞': 2}   # two kings.
    chessboard(challenge, library, board)


if __name__ == '__main__':
    # By default use an 8x8 board.
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
