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
"""
    This is a polycube packing solver.
    It is roughly the same as the polyomino solver, but extended to three dimensions.

    A pentacube is a polycube composed of 5 cubes.
    There are 29 distinct three-dimensional pentacubes (Bouwkamp 1981).
    Of these, the 12 planar pentacubes (corresponding to solid pentominoes), are well known.
    Among the non-planar pentacubes, there are five that have at least one plane of symmetry;
    Each of them is its own mirror image. The remaining 12 pentacubes come in mirror image pairs.

    This will generate obj/mtl 3D 'Wavefront' files of the solution.
"""
import sys
import numpy as np
from ortools.sat.python import cp_model
import open3d as o3d
import copy

class PolycubePuzzleSolver:
    def __init__(self):
        self.maximising = False
        self.status = cp_model.UNKNOWN
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = 800
        self.solver.parameters.num_search_workers = 12
        self.pieces = None
        self.space = None
        self.pos_items = None
        self.presence = {}
        self.result = None

    @staticmethod
    def _translate(fixed, offs: tuple) -> set:
        """
            return the normalised block translated by offset (x,y,z).
        """
        return {tuple((pt[0] + offs[0], pt[1] + offs[1], pt[2] + offs[2])) for pt in fixed}

    def legal(self, fixed, offs: tuple) -> bool:
        for pt in fixed:
            xyz = pt[0] + offs[0], pt[1] + offs[1], pt[2] + offs[2]
            if xyz not in self.space:
                return False
        return True

    def process(self, pieces: dict, problem: dict):
        """
        Given a problem and the pieces we construct a SAT model and then solve it.
        """
        model = cp_model.CpModel()

        """
        Keep pieces for the print function
        Define the space as given in the problem, defaulting to the 6×10 square
        Define available pieces as given in the problem, defaulting to at least one of each piece.
        """
        self.pieces = pieces
        self.space = problem['fill'] if 'fill' in problem else set((x, y, z) for z in range(0, 5) for y in range(0, 5) for x in range(0, 5))
        available = problem['use'] if 'use' in problem else {name: -1 for name, piece in pieces.items()}

        """
        For each fixed piece that's being used...
        See if it can be placed at each point in space, and if so, add it into the model as a potential presence
        of the solution. Also add it's coordinates into a placement dict so that we can test for overlaps later.
        """
        placement = {}
        for name, piece in pieces.items():
            if name in available:
                for offset in self.space:
                    for i, fixed in piece.fixed.items():
                        if self.legal(fixed['pts'], offset):
                            self.presence[tuple((name, i, offset))] = model.NewBoolVar(f"{name}_{i}:{offset}")
                            placement[tuple((name, i, offset))] = self._translate(fixed['pts'], offset)

        """
        Compose free - the entire set of fixed+offset pieces by each 'free' piece (eg, the set of all "K")
        """
        free = {k: [bv for i, bv in self.presence.items() if i[0] == k] for k in available}

        """
        Compose pos_items - this is the set of all points of each possible piece at each x,y,z in the space.
        We will use this for constraint setting and for rendering.
        """
        self.pos_items = {x: set() for x in self.space}
        for fixed, p_bv in self.presence.items():
            pp = placement[fixed]
            for point in pp:
                self.pos_items[point].add(fixed)

        """
        Constraints are:
          1: Limit the count of free pieces as defined by the problem
          2: Exactly 1 piece per space of space
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
        For each point, constrain the sum of pos_items to 1 (1 piece per point) or 0..1 (if gaps are allowed).
        """
        for pt_points in self.pos_items.values():
            items = [self.presence[i] for i in pt_points]
            if problem['gaps']:
                model.Add(sum(items) <= 1)
            else:
                model.Add(sum(items) == 1)

        """
        Can now solve.
        """
        self.status = self.solver.Solve(model)

    def _save_result(self):
        # save each answer-piece as a tuple of it's name, it's fix, and it's offset.
        self.result = set()
        for pt in self.space:
            if pt in self.pos_items:
                for maybe in self.pos_items[pt]:
                    if self.solver.Value(self.presence[maybe]):
                        self.result.add(maybe)

    def show(self) -> bool:
        if self.status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            self._save_result()
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

    def save(self, file_name: str = 'file'):
        from colorsys import hsv_to_rgb
        count = len(self.result)
        mesh_file = '# OBJ File: {file_name}\n# Material Count: {count}\n\n'
        material_file = '# MTL File: {file_name}\n# Mesh Count: {count}\n\n'
        for idx, thing in enumerate(self.result):
            hue = idx/count
            name = thing[0]
            r, g, b = hsv_to_rgb(hue, 1.0, 1.0)
            material_file += f'newmtl {name}_{idx:03x}_Mat\n' \
                     f'Ns 225.000000\n' \
                     f'Ka 1.000000 1.000000 1.000000\n' \
                     f'Kd {r} {g} {b}\n' \
                     f'Ks 0.500000 0.500000 0.500000\n' \
                     f'Ke 0.000000 0.000000 0.000000\n' \
                     f'Ni 1.00000\n' \
                     f'd 1.000000\n' \
                     f'illum 2\n\n'
        m = open(f'{file_name}.mtl', 'w')
        m.write(material_file)
        m.close()

        # although called vertex normals, we are using them on each face which is cubic, so there are six.
        normals = [[0.0000, 1.0000, 0.0000], [0.0000, -1.0000, 0.0000], [1.0000, 0.0000, 0.0000],
                   [0.0000, 0.0000, 1.0000], [0.0000, 0.0000, -1.0000], [-1.0000, 0.0000, 0.0000]]

        mesh_file += f'mtllib {file_name}.mtl\n\nVertex Normals (1-6)\n'
        for x, y, z in normals:
            mesh_file += f"vn  {x} {y} {z}\n"

        # points are referenced globally
        # so we need to add the sum of previous points on each model.
        pto = 1
        for idx, thing in enumerate(self.result):
            name, fix, offset = thing
            mesh_file += f'\n# object {name} {idx:03x}\n'
            mesh_file += f'o {name}_{idx:03x}\n'
            model = copy.deepcopy(self.pieces[name].fixed[fix]['model'])
            model.translate(offset)

            points = list(model.vertices)
            mesh_file += f'\n#object vertices\n'
            for px, py, pz in points:
                mesh_file += f'v {px} {py} {pz}\n'
            mesh_file += f'\n# polygon material\n' \
                         f'usemtl {name}_{idx:03x}_Mat\n\ns off\n'
            faces = list(model.triangles)
            face_normals = list(model.triangle_normals)
            face_count = len(faces)
            mesh_file += f'\n#object has {face_count} triangle faces\n'
            for idx in range(face_count):
                face = faces[idx]
                fn = 1 + normals.index(list(face_normals[idx]))
                mesh_file += 'f '
                for pi in face:
                    mesh_file += f'{pto + pi}//{fn} '
                mesh_file += '\n'
            pto += len(points)
        f = open(f'{file_name}.obj', 'w')
        f.write(mesh_file)
        f.close()

class Shape:

    def __init__(self, points: list, name: str = 'shape'):
        self.name = name
        self.fixed = dict()
        self.fix(points)
        self.model()

    @staticmethod
    def _normalise_pts(d:list):
        # calculate the boundary and the size of each dimension for a given voxel object
        # bring the object to be positive but as close to the origin as possible.
        lx, bx = min(x[0] for x in d), 1 + max(x[0] for x in d)
        ly, by = min(x[1] for x in d), 1 + max(x[1] for x in d)
        lz, bz = min(x[2] for x in d), 1 + max(x[2] for x in d)
        arr = [[[[x, y, z] in d for z in range(lz, bz)] for y in range(ly, by)] for x in range(lx, bx)]
        res = [[x, y, z] for x in range(bx-lx) for y in range(by-ly) for z in range(bz-lz) if arr[x][y][z]]
        return res

    @staticmethod
    def _cube_p(pt, p=0):
        # There are 24 3D rotations constrained to sequences of 90-degree rotations
        a, b, c = pt
        return [
            [+a, +b, +c], [-b, +a, +c], [-a, -b, +c], [+b, -a, +c], [-c, +b, +a], [-b, -c, +a], [+c, -b, +a], [+b, +c, +a],
            [-a, +b, -c], [-b, -a, -c], [+a, -b, -c], [+b, +a, -c], [+c, +b, -a], [-b, +c, -a], [+b, -c, -a], [-c, -b, -a],
            [+a, -c, +b], [+c, +a, +b], [-a, +c, +b], [-c, -a, +b], [-a, -c, -b], [+a, +c, -b], [-c, +a, -b], [+c, -a, -b]
        ][p % 24]

    def fix(self, points: list):
        # Try all 24 3D rotations on a voxel object and eliminate symmetric identities by using a hash of the result.
        rt = dict()
        for f in range(24):
            ff = Shape._normalise_pts([Shape._cube_p(pt, f) for pt in Shape._normalise_pts(points)])
            ff_str = str(ff)
            rt[hash(ff_str)] = ff
        self.fixed = {k: {'pts': v} for k, v in enumerate(rt.values())}

    def model(self):
        # For each fixed rotation of this voxel shape, generate a triangular mesh.
        for key in self.fixed.keys():
            construct = self.fixed[key]
            transforms = construct['pts']  # called transforms here each is the voxel of the solid.
            box = o3d.geometry.TriangleMesh.create_box()
            box.clear()
            for trans in transforms:
                voxel = o3d.geometry.TriangleMesh.create_box()
                if sum(trans) % 2 == 1:
                    voxel.rotate([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], [0.5, 0.5, 0.5])
                voxel.translate(trans)
                box += voxel
            box.remove_duplicated_vertices()
            dupes = set()
            tr_idx = {}
            for idx, t in enumerate(np.asarray(box.triangles)):
                xt = tuple(sorted(list(t)))
                if xt in tr_idx:
                    dupes.add(tr_idx[xt])
                    dupes.add(idx)
                else:
                    tr_idx[xt] = idx
            box.remove_triangles_by_index(list(dupes))
            box.remove_unreferenced_vertices()
            box.compute_triangle_normals()
            construct['model'] = box


def main():

    pentacubes_29 = {
        # 12 'pentomino' - flat pentacubes
        'L': [[1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 3, 0]],  # Q conway alternatives
        'I': [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [4, 0, 0]],  # O
        'P': [[0, 2, 0], [0, 1, 0], [0, 0, 0], [1, 0, 0], [1, 1, 0]],  # P
        'V': [[2, 0, 0], [1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 2, 0]],  # V
        'W': [[2, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 2, 0]],  # W
        'N': [[0, 0, 0], [1, 0, 0], [2, 0, 0], [2, 1, 0], [3, 1, 0]],  # S
        'U': [[1, 0, 0], [0, 0, 0], [0, 1, 0], [0, 2, 0], [1, 2, 0]],  # U
        'Y': [[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0], [1, 1, 0]],  # Y
        'T': [[0, 0, 0], [1, 0, 0], [2, 0, 0], [1, 1, 0], [1, 2, 0]],  # T
        'X': [[1, 0, 0], [1, 1, 0], [0, 1, 0], [1, 2, 0], [2, 1, 0]],  # X
        'F': [[1, 0, 0], [1, 1, 0], [0, 1, 0], [1, 2, 0], [2, 2, 0]],  # R
        'Z': [[0, 0, 0], [1, 0, 0], [1, 1, 0], [1, 2, 0], [2, 2, 0]],  # Z

        # 17 non-flat pentacubes
        'xq':  [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1]],  # Square with a block on it.
        'xc':  [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 0, 1], [0, 1, 1]],  # 13 - (broken)
        'xp':  [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 2]],  # phallus
        'xo':  [[0, 0, 0], [0, 0, 1], [0, 0, 2], [0, 1, 1], [1, 0, 1]],  # 4-legged octopus
        'xe':  [[0, 0, 0], [0, 0, 1], [0, 0, 2], [0, 1, 1], [1, 1, 1]],  # elephant
        'xy':  [[1, 0, 0], [1, 1, 0], [1, 2, 0], [0, 2, 0], [1, 1, 1]],  # Twisted Y pentomino
        'xyy': [[1, 0, 0], [1, 1, 0], [1, 2, 0], [2, 2, 0], [1, 1, 1]],  # ẏ Twisted Y pentomino (mirror)
        'xn':  [[0, 0, 0], [0, 1, 0], [0, 2, 0], [1, 2, 1], [0, 2, 1]],  # Twisted N pentomino
        'xnn': [[0, 0, 0], [0, 1, 0], [0, 2, 0], [1, 2, 1], [1, 2, 0]],  # ṅ Twisted N pentomino (mirror)
        'xu':  [[0, 0, 0], [0, 1, 0], [0, 2, 0], [1, 0, 0], [0, 2, 1]],  # Twisted U pentomino
        'xuu': [[0, 0, 0], [0, 1, 0], [0, 2, 0], [0, 0, 1], [1, 2, 0]],  # ů Twisted U pentomino (mirror)
        'xz':  [[0, 0, 0], [0, 0, 1], [0, 1, 1], [1, 1, 1], [1, 1, 2]],  # Twisted Z pentomino
        'xzz': [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [1, 1, 2]],  # ż Twisted Z pentomino (mirror)
        'xw':  [[0, 0, 0], [1, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 2]],  # Twisted W pentomino
        'xww': [[0, 0, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 0, 2]],  #  ẇ Twisted W pentomino (mirror)
        'xf':  [[0, 0, 0], [0, 1, 1], [0, 0, 1], [1, 0, 1], [1, 0, 2]],  # Folded F pentomino
        'xff': [[0, 0, 0], [1, 0, 1], [0, 0, 1], [0, 1, 1], [0, 1, 2]],  # ḟ Folded F pentomino (mirror)
    }

    finder = PolycubePuzzleSolver()
    x, y, z = 5, 6, 5  # voxel space to use
    # x, y, z = 20, 3, 1  # good puzzle for just the flats

    # cuboid with x taken from top.
    problem_space = set((ix, iy, iz) for iz in range(0, z) for iy in range(0, y) for ix in range(0, x))
    # 5x6x5 cuboid with x taken from top.
    problem_space.remove((2, 5, 2))
    problem_space.remove((1, 5, 2))
    problem_space.remove((3, 5, 2))
    problem_space.remove((2, 5, 1))
    problem_space.remove((2, 5, 3))
    problem_shapes = {name: Shape(shape, name) for name, shape in pentacubes_29.items()}

    puzzle = {
        'gaps': False,
        'fill': problem_space,
        'use': {'I': 1, 'L': 1, 'P': 1, 'V': 1, 'W': 1, 'N': 1,
                'U': 1, 'Y': 1, 'T': 1, 'X': 1, 'F': 1, 'Z': 1,
                'xq': 1, 'xc': 1, 'xp': 1, 'xo': 1, 'xe': 1, 'xy': 1,
                'xyy': 1, 'xn': 1, 'xnn': 1, 'xu': 1, 'xuu': 1, 'xz': 1,
                'xzz': 1, 'xw': 1, 'xww': 1, 'xf': 1, 'xff': 1}
    }
    finder.process(problem_shapes, puzzle)
    if finder.show():
        finder.save(f'{x}x{y}x{z}_solution')


if __name__ == '__main__':
    main()
