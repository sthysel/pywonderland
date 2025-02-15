# -*- coding: utf-8 -*-
"""
Some helper functions for building the geometry and exporting to POV-Ray.
"""
import sys
import numpy as np


def normalize(v):
    """Normalize a vector `v`.
    """
    return np.array(v) / np.linalg.norm(v)


def reflection_matrix(v):
    """Return the reflection transformation about a plane with normal vector `v`.
       see "https://en.wikipedia.org/wiki/Householder_transformation".
    """
    n = len(v)
    v = np.array(v)[np.newaxis]
    return np.eye(n) - 2 * np.dot(v.T, v)


def get_init_point(M, d):
    """Given the normal vectors of the mirrors stored as row vectors in `M`
       and a tuple of non-negative floats `d`, compute the vector `v` whose
       distance vector to the mirrors is `d` and return its normalized version.
    """
    return normalize(np.linalg.solve(M, d))


def proj3d(v):
    """Stereographic projection of a 4d vector with pole at (0, 0, 0, 1).
    """
    v = normalize(v)
    x, y, z, w = v
    return np.array([x, y, z]) / (1 + 1e-8 - w)  # avoid divide by zero


def get_face_normal(face):
    """Get the normal vector (point outward) of a face.
    """
    p1, p2, p3 = face[:3]
    normal = normalize(np.cross(p2 - p1, p3 - p1))
    if np.dot(p1, normal) < 0:
        normal = -normal
    return normal


def get_sphere_info(points):
    """
    Given a list of 4d points that lie on the same face of a polytope,
    compute the 3d sphere that passes through their projected points.
    The returned tuple contains:
      1. a boolean value indicates whether this face is flat.
      2. the center of this face.
      3. the radius of this "bubble" face (it's None if this face is flat)
      4. a float measures the size of this face.

    see "http://www.ambrsoft.com/TrigoCalc/Sphere/Spher3D_.htm"
    """
    rib = np.sum(points, axis=0)
    rib3d = proj3d(rib)
    pts3d = np.asarray([proj3d(p) for p in points])
    face_size = np.linalg.norm(pts3d[0] - rib3d)

    M = np.ones((4, 4), dtype=np.float)
    M[:3, :3] = pts3d[:3]
    M[3, :3] = rib3d
    b = [-sum(x*x) for x in M[:, :3]]
    # if this is a plane
    if abs(np.linalg.det(M)) < 1e-4:
        center = rib3d
        return True, center, None, face_size

    T = np.linalg.solve(M, b)
    D, E, F, G = T
    center = -0.5 * T[:3]
    radius = 0.5 * np.sqrt(D*D + E*E + F*F - 4*G)
    return False, center, radius, face_size


def check_duplicate_face(f, l):
    """Check if a face `f` is already in the list `l`.
       We need this function here because when some rotation r fixes a
       face f = (v1, v2, ..., v_k), r maps f as an ordered tuple to
       (v_k, v_1, ..., v_{k-1}) or (v_2, ..., v_k, v_1) where they all
       represent the same face.
    """
    for _ in range(len(f)):
        if f in l or f[::-1] in l:
            return True
        f = f[-1:] + f[:-1]
    return False


def has_edge(e, f):
    """Check if an edge `e` is in a face `f`.

       Example:
       >>> e = (0, 1)
       >>> f = (1, 2, 3, 0)
       >>> has_edge(e, f)
       >>> True  # because 0, 1 are adjacent in f (first and last)
    """
    for pair in zip(f, f[1:] + (f[0],)):
        if e == pair or e == pair[::-1]:
            return True
    return False


def has_common_edge(f1, f2):
    """Check if two faces `f1` and `f2` have an edge in common.
    """
    for e1 in zip(f1, f1[1:] + (f1[0],)):
        if has_edge(e1, f2):
            return True
    return False


def find_face_by_edge(e, face_list):
    """Find the pair of faces in `face_list` that has `e` as a common edge.
    """
    result = []
    for i, face in enumerate(face_list):
        if has_edge(e, face):
            result.append(i)
        if len(result) == 2:
            return tuple(result)
    return None


def make_symmetry_matrix(upper_triangle):
    """Given three or six integers/rationals, fill them into a
       3x3 (or 4x4) symmetric matrix.
    """
    if len(upper_triangle) == 3:
        a12, a13, a23 = upper_triangle
        return [[1, a12, a13],
                [a12, 1, a23],
                [a13, a23, 1]]
    elif len(upper_triangle) == 6:
        a12, a13, a14, a23, a24, a34 = upper_triangle
        return [[1, a12, a13, a14],
                [a12, 1, a23, a24],
                [a13, a23, 1, a34],
                [a14, a24, a34, 1]]
    else:
        raise ValueError("Three or six inputs are expected.")


def get_coxeter_matrix(coxeter_diagram):
    """Get the Coxeter matrix from a given coxeter_diagram.
       The Coxeter matrix is square and entries are all integers,
       it describes the relations between the generators of the symmetry group.
       Here is the math: suppose two mirrors m_i, m_j form an angle p/q
       where p,q are coprime integers, then the two generator reflections
       about these two mirrors r_i, r_j satisfy (r_ir_j)^p = 1.

       Example:
       >>> coxeter_diagram = (3, 2, Fraction(5, 2))  # Fraction(5, 2) means symbol 5/2
       >>> get_coxeter_matrix(coxeter_diagram)
       >>> [[1, 3, 2],
            [3, 1, 5],
            [2, 5, 1]]

       Note that in general one cannot recover the Coxeter diagram from the Coxeter matrix,
       since a star polytope may have the same Coxeter matrix with a convex one.
    """
    upper_triangle = [x.numerator for x in coxeter_diagram]
    return make_symmetry_matrix(upper_triangle)


def get_mirrors(coxeter_diagram):
    """Given three or six integers/rationals that represent
       the angles between the mirrors (a rational p means the
       angle is π/p), return a 3x3 or 4x4 matrix whose rows
       are the normal vectors of the mirrors.
    """
    # error handling function when the input coxeter matrix is invalid.
    def err_handler(err_type, flag):
        print("Invalid input Coxeter diagram. This diagram does not give a finite \
symmetry group of an uniform polytope. See \
https://en.wikipedia.org/wiki/Coxeter_group#Symmetry_groups_of_regular_polytopes \
for a complete list of valid Coxeter diagrams.")
        sys.exit(1)

    np.seterrcall(err_handler)
    np.seterr(all="call")

    coxeter_matrix = np.array(make_symmetry_matrix(coxeter_diagram)).astype(np.float)
    C = -np.cos(np.pi / coxeter_matrix)
    M = np.zeros_like(C)

    M[0, 0] = 1
    M[1, 0] = C[0, 1]
    M[1, 1] = np.sqrt(1 - M[1, 0]*M[1, 0])
    M[2, 0] = C[0, 2]
    M[2, 1] = (C[1, 2] - M[1, 0]*M[2, 0]) / M[1, 1]
    M[2, 2] = np.sqrt(1 - M[2, 0]*M[2, 0] - M[2, 1]*M[2, 1])
    if len(coxeter_matrix) == 4:
        M[3, 0] = C[0, 3]
        M[3, 1] = (C[1, 3] - M[1, 0]*M[3, 0]) / M[1, 1]
        M[3, 2] = (C[2, 3] - M[2, 0]*M[3, 0] - M[2, 1]*M[3, 1]) / M[2, 2]
        M[3, 3] = np.sqrt(1 - M[3, 0]*M[3, 0] - M[3, 1]*M[3, 1] - M[3, 2]*M[3, 2])
    return M


#---------------------
# now the POV-Ray part


def pov_vector(v):
    """Convert a vector to POV-Ray format. e.g. (x, y, z) --> <x, y, z>.
    """
    return "<{}>".format(", ".join(str(x) for x in v))


def pov_vector_list(vectors):
    """Convert a list of vectors to POV-Ray format, e.g.
       [(x, y, z), (a, b, c), ...] --> <x, y, z>, <a, b, c>, ...
    """
    return ", ".join([pov_vector(v) for v in vectors])


def pov_array(arr):
    """Convert an array to POV-Ray format, e.g.
       (0, 1, 2, 3) --> array[4] {0, 1, 2, 3}
    """
    return "array[{}] {{{}}}".format(len(arr), ", ".join(str(x) for x in arr))


def pov_2d_array(array_list):
    """Convert a mxn 2d array to POV-Ray format, e.g.
       [(1, 2), (3, 4), (5, 6)] --> arrar[3][2] {{1, 2}, {3, 4}, {5, 6}}.
    """
    return "array[{}][{}] {{{}}}".format(
        len(array_list),
        len(array_list[0]),
        ", ".join("{{{}}}".format(", ".join(str(x) for x in arr)) for arr in array_list))


def export_face(ind, face):
    """Export the information of a face to a POV-Ray macro.
    """
    isplane, center, radius, face_size = get_sphere_info(face)
    if isplane:
        macro = "FlatFace({}, {}, array[{}]{{{}}}, {}, {})\n"
        return macro.format(ind, len(face), len(face), pov_vector_list(face),
                            pov_vector(center), face_size)
    else:
        macro = "BubbleFace({}, {}, array[{}]{{{}}}, {}, {}, {})\n"
        return macro.format(ind, len(face), len(face), pov_vector_list(face),
                            pov_vector(center), radius, face_size)
