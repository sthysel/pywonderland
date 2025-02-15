from functools import partial
from fractions import Fraction
import numpy as np


def normalize(v):
    """Normalize a vector `v`.
    """
    return np.array(v) / np.sqrt(abs(np.dot(v, v)))


def get_reflections(M, dists=None):
    """Return the (affine) reflection transformations about a list of
       mirrors with normal vectors as row vectors of the matrix `M`.
       The distances of the mirrors to the origin are given by a second
       list `dists`. In spherical and hyperbolic cases these distances
       are all 0 and the reflections are usual linear transformations,
       but in the euclidean case it may be non-zero and the reflections
       may become affine translations. Here the normal of each mirror is
       assumed to be an unit vector in the metric space.
    """
    def reflect(v, normal, dist):
        return v - 2 * (np.dot(v, normal) + dist) * normal

    if dists is None:
        return [partial(reflect, normal=n, dist=0) for n in M]
    else:
        return [partial(reflect, normal=n, dist=d) for n, d in zip(M, dists)]


def make_symmetry_matrix(upper_triangle):
    """Given three or six integers/rationals, fill them into a
       3x3 (or 4x4) symmetric matrix. Always return a numpy 2d array
       of int type.
    """
    if len(upper_triangle) == 3:
        a12, a13, a23 = upper_triangle
        M = [[1, a12, a13],
             [a12, 1, a23],
             [a13, a23, 1]]
    elif len(upper_triangle) == 6:
        a12, a13, a14, a23, a24, a34 = upper_triangle
        M = [[1, a12, a13, a14],
             [a12, 1, a23, a24],
             [a13, a23, 1, a34],
             [a14, a24, a34, 1]]
    else:
        raise ValueError("Three or six inputs are expected.")

    return np.array(M, dtype=np.int)


def get_point_from_distance(M, d):
    """Given the normal vectors of the mirrors stored as row vectors in `M`
       and a tuple of non-negative floats `d`, compute the vector `v` whose
       distance vector to the mirrors is `d` and return its normalized version.
    """
    return normalize(np.linalg.solve(M, d))


def get_coxeter_matrix(coxeter_diagram):
    """Get the Coxeter matrix from a given coxeter_diagram.
       The Coxeter matrix is square and entries are all integers,
       it describes the relations between the generators of the symmetry group.
       Here is the math: suppose two mirrors m_i, m_j form an angle p/q
       where p,q are coprime integers, then the two generator reflections
       about these two mirrors r_i, r_j satisfy (r_ir_j)^p = 1.

       Example:
       >>> coxeter_diagram = (3, 2, Fraction(5, 2))
       >>> get_coxeter_matrix(coxeter_diagram)
       >>> [[1, 3, 2],
            [3, 1, 5],
            [2, 5, 1]]

       Note that in general one cannot recover the Coxeter diagram from
       the Coxeter matrix since a star polytope may have the same Coxeter
       matrix with a convex one.
    """
    upper_triangle = [x.numerator for x in coxeter_diagram]
    return make_symmetry_matrix(upper_triangle)


def get_spherical_or_affine_mirrors(coxeter_diagram):
    """Given three or six integers/rationals that represent
       the angles between the mirrors (a rational p means the
       angle is π/p), return a 3x3 or 4x4 matrix whose rows
       are the normal vectors of the mirrors.
       Here the tiling space determined by `coxeter_diagram` must
       be either spherical or euclidean.
    """
    coxeter_matrix = np.array(make_symmetry_matrix(coxeter_diagram)).astype(np.float)
    C = -np.cos(np.pi / coxeter_matrix)
    M = np.zeros_like(C)

    M[0, 0] = 1
    M[1, 0] = C[0, 1]
    M[1, 1] = np.sqrt(1 - M[1, 0]*M[1, 0])
    M[2, 0] = C[0, 2]
    M[2, 1] = (C[1, 2] - M[1, 0]*M[2, 0]) / M[1, 1]
    M[2, 2] = np.sqrt(abs(1 - M[2, 0]*M[2, 0] - M[2, 1]*M[2, 1]))
    if len(coxeter_matrix) == 4:
        M[3, 0] = C[0, 3]
        M[3, 1] = (C[1, 3] - M[1, 0]*M[3, 0]) / M[1, 1]
        M[3, 2] = (C[2, 3] - M[2, 0]*M[3, 0] - M[2, 1]*M[3, 1]) / M[2, 2]
        M[3, 3] = np.sqrt(abs(1 - M[3, 0]*M[3, 0] - M[3, 1]*M[3, 1] - M[3, 2]*M[3, 2]))
    return M


def get_hyperbolic_mirrors(coxeter_diagram):
    """Get reflection mirrors for the hyperbolic case.
    """
    C = -np.cos(np.pi / make_symmetry_matrix(coxeter_diagram).astype(np.float))
    M = np.zeros_like(C).astype(np.complex)
    M[0, 0] = 1
    M[1, 0] = C[1, 0]
    M[1, 1] = np.sqrt(1 - M[1, 0]*M[1, 0])
    M[2, 0] = C[2, 0]
    M[2, 1] = (C[2, 1] - M[2, 0]*M[1, 0]) / M[1, 1]
    M[2, 2] = np.sqrt(abs(M[2, 0]*M[2, 0] + M[2, 1]*M[2, 1] - 1)) * 1j
    return M


def project_euclidean(v):
    """Project a point in E^n to E^{n-1}.
       It's projected to the plane z=1 (or w=1).
    """
    return np.array(v[:-1]) / v[-1]


def project_spherical(v):
    """Project a point in S^n to S^{n-1}.
       This is the stereographic projection.
    """
    v = normalize(v)
    return np.array(v[:-1]) / (1 + 1e-8 - v[-1])


def project_hyperbolic(v):
    """Project a point in H^n to H^{n-1}.
       It's the projection from the hyperboloid to the disk.
    """
    return np.array([x.real for x in v[:-1]]) / (1 + v[-1].imag)


def get_geometry_type(pqr):
    """Get the geometry type.
    """
    s = sum([Fraction(1, x) if x != -1 else 0 for x in pqr])
    if s > 1:
        return "spherical"
    elif s == 1:
        return "euclidean"
    else:
        return "hyperbolic"


# -------------------------------
# LaTeX formatting functions

def export_latex_array(self, words, symbol=r"s", cols=4):
    """Export a list words to latex array format.
       `cols` is the number of columns of the output latex array.

       Example: words = [(0, 1), (1, 2, 3) ...]
       Return: \begin{array}
               &s_0s_1 & s_1s_2s_3 & ... &\\
               ...
               \end{array}
    """
    def to_latex(word):
        return "".join(symbol + "_{{{}}}".format(i) for i in word)

    latex = ""
    for i, word in enumerate(words):
        if i > 0 and i % cols == 0:
            latex += r"\\" + "\n"
        latex += to_latex(word)
        if i % cols != cols - 1:
            latex += "&"

    return r"\begin{{array}}\n{{{}}}{}\n\end{{array}}".format("l" * cols, latex)


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


def get_circle(x0, y0, x1, y1):
    """
    compute the geodesic circle that passes through (x0,y0) and (x1,y1)
    """

    # return None if they are close enough or on the same diameter
    t = 2 * (x0 * y1 - x1 * y0)
    if abs(t) < 1e-4:
        return x1, y1, None

    r0 = 1 + x0 * x0 + y0 * y0
    r1 = 1 + x1 * x1 + y1 * y1
    cx = (y1 * r0 - y0 * r1) / t
    cy = (x0 * r1 - x1 * r0) / t
    r = np.sqrt(max(cx * cx + cy * cy - 1, 1e-6))
    return cx, cy, r


def hex_to_rgb(value):
    """Hex value to (r, g, b) triple.
    """
    return [((value >> (8 * k)) & 255) / 255.0 for k in (2, 1, 0)]
