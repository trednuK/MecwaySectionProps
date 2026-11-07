# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# section_analysis.py
# Cross-section properties of a beam section (mesher + FEM), run with the
# Python found by section_utils.find_python (CPython 3, numpy + scipy); NOT in
# IronPython.
#
#   python section_analysis.py <in.json> <out.json>
#
# Input (all lengths in metres):
#   {"loops": [[[x, y], ...], ...],   closed loops (last point not repeated),
#                                     even-odd domain
#    "step": {"file", "normal", "offset", "u", "v", "points", "tol",
#             "hint"},                alternative to "loops" (section_step)
#    "fallback_loops": [...],         used when the STEP face is not found
#    "mesh_size": null,               maximum element area in m^2 (null = auto)
#    "n_target": 3000,                about this many tri6 elements (auto size)
#    "n_across": 3.0,                 element rows across a thin wall
#    "nu": 0.0}                       Poisson ratio for the shear functions
# Output: flat keys in SI (see run_analysis), "loops" (the cleaned loops that
# were meshed) and an "aster" block for AFFE_CARA_ELEM POUTRE
# SECTION='GENERALE'. out.json is always written ("success" false + "error" +
# "traceback" on failure).
#
# Other job: {"list_faces": STEP path} gives {"faces": [...], "unplaced": n}:
# the planar faces at their global position with triangles to show them in
# Mecway (see list_faces).

import json
import math
import os
import sys
import time
import traceback

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import section_fem  # noqa: E402
import section_mesh  # noqa: E402


def _loops_from_step(step):
    import section_step   # written separately; imported only when needed
    path = step["file"]
    hits = section_step.find_placed(path, step.get("normal"), step.get("offset"),
                                    step.get("points"), step.get("tol"),
                                    step.get("hint"))
    # 1 degree per chord: ~5e-5 relative area error on circles (3 deg: ~5e-4)
    info = {}
    loops = section_step.placed_loops_2d(path, hits, step.get("u"), step.get("v"),
                                         chord_rel=1e-6, max_angle_deg=1.0, info=info)
    return loops, [i for _, ids in hits for i in ids], info.get("gaps_closed", [])


def display_triangles(face, spacing_parts=10.0):
    """(points 3D, triangles) to show a planar face in Mecway and pick it:
    Delaunay triangles of the boundary points (long edges subdivided) with the
    centroid inside. Only for the eye and the mouse: nothing is computed on
    them, so a triangle missing in a narrow slit does not matter. The node
    order is counter-clockwise about the outward normal."""
    from scipy.spatial import Delaunay
    try:
        from scipy.spatial import QhullError        # scipy 1.8 and newer
    except ImportError:
        from scipy.spatial.qhull import QhullError
    n = np.asarray(face["normal"], dtype=float)
    u = np.cross(n, [1.0, 0.0, 0.0] if abs(n[0]) < 0.9 else [0.0, 1.0, 0.0])
    u /= np.linalg.norm(u)
    v = np.cross(n, u)
    loops = [np.asarray(lp, dtype=float)[:, :] for lp in face["loops"]]
    flat = [np.stack([lp.dot(u), lp.dot(v)], axis=1) for lp in loops]
    every = np.vstack(flat)
    size = float(np.hypot(*(every.max(axis=0) - every.min(axis=0))))
    step = size / spacing_parts
    pts = []
    pa, pb = [], []
    for lp in flat:
        nxt = np.roll(lp, -1, axis=0)
        pa.append(lp)
        pb.append(nxt)
        for a, b in zip(lp, nxt):
            m = max(1, int(math.ceil(float(np.hypot(*(b - a))) / step)))
            pts.extend(a + (b - a) * (k / float(m)) for k in range(m))
    pts = np.unique(np.round(np.array(pts) / (1e-9 * size)), axis=0) * (1e-9 * size)
    try:
        simp = Delaunay(pts, qhull_options="QJ Qbb Qc").simplices
        cen = pts[simp].mean(axis=1)
        simp = simp[section_mesh.points_inside(cen, np.vstack(pa), np.vstack(pb))]
    except (QhullError, ValueError):
        # degenerate input: a fan over the first loop
        pts = flat[0]
        simp = np.array([[0, k, k + 1] for k in range(1, len(pts) - 1)])
    if len(simp):
        X = pts[simp]
        cross = ((X[:, 1, 0] - X[:, 0, 0]) * (X[:, 2, 1] - X[:, 0, 1]) -
                 (X[:, 1, 1] - X[:, 0, 1]) * (X[:, 2, 0] - X[:, 0, 0]))
        simp = simp[cross != 0.0]
        cross = cross[cross != 0.0]
        simp[cross < 0] = simp[cross < 0][:, [0, 2, 1]]
    p3 = (pts[:, 0:1] * u[None, :] + pts[:, 1:2] * v[None, :] +
          float(face["offset"]) * n[None, :])
    return p3, simp


def list_faces(path):
    """The job {"list_faces": path}: the planar faces of a STEP file at their
    global position, each with "points" and "triangles" for Mecway."""
    import section_step
    out = []
    for face in section_step.planar_faces(path):
        pts, tris = display_triangles(face)
        if len(tris):
            out.append({"file": path, "occurrence": face["occurrence"],
                        "face": face["face"], "normal": face["normal"],
                        "offset": face["offset"], "points": pts.tolist(),
                        "triangles": tris.tolist()})
    return {"faces": out, "unplaced": len(section_step.load(path).unplaced)}


def aster_block(res, nodes, elements):
    """Characteristics for AFFE_CARA_ELEM POUTRE SECTION='GENERALE'
    (U4.42.01 par. 9.4.3), in the frame local y = principal axis 1 (angle
    phi from +x), local z = axis 1 rotated +90 deg, origin at the centroid.

    Conventions, checked against MACR_CARA_POUTRE of Code-Aster 17.4 on the
    same tri6 mesh (tests/section_aster_check.py; channel, unequal angle, Z,
    rectangle), after mapping Code-Aster's principal frame (angle ALPHA,
    which may be ours rotated by a multiple of 90 deg) onto ours:
      IY = int z^2 dA = I11, IZ = int y^2 dA = I22;
      AY, AZ = A / shear area for a shear force along y, z (nu = 0 gives
        Code-Aster's values; rectangle 1.2);
      EY, EZ = components of the vector FROM the shear centre TO the centroid
        (Code-Aster: "excentrement du centre de torsion, composante de CG",
        macr_cara_poutre_ops.py: (PCTY, PCTZ) = CG);
      JX = J, JG = warping constant about the shear centre;
      RY, RZ = max |y|, |z| of the nodes;
      RT = J max|tau| / T on the boundary (Code-Aster takes the extreme normal
        flux along GROUP_MA_BORD; equal for smooth sections, mesh dependent at
        re-entrant corners);
      IYR2 = int z (y^2 + z^2) dA, IZR2 = int y (y^2 + z^2) dA, about the
        centroid (the IYR2/IZR2 columns of MACR_CARA_POUTRE with
        TABLE_CARA='OUI', i.e. what AFFE_CARA_ELEM TABLE_CARA reads)."""
    p = math.radians(res["phi_deg"])
    c, s = math.cos(p), math.sin(p)
    G = np.array(res["centroid"])
    rel = nodes - G
    yl = c * rel[:, 0] + s * rel[:, 1]
    zl = -s * rel[:, 0] + c * rel[:, 1]
    w, Ns, B, x, y = section_fem._element_data(nodes, elements, res["centroid"])
    yg = c * x + s * y
    zg = -s * x + c * y
    r2 = yg ** 2 + zg ** 2
    out = {
        "A": res["area"],
        "IY": res["i11_c"],
        "IZ": res["i22_c"],
        "RY": float(np.abs(yl).max()),
        "RZ": float(np.abs(zl).max()),
        "IYR2": float(np.sum(w * zg * r2)),
        "IZR2": float(np.sum(w * yg * r2)),
    }
    if res.get("warping_computed"):
        cg = G - np.array(res["shear_centre"])
        out.update({
            "AY": res["area"] / res["a_s11"],
            "AZ": res["area"] / res["a_s22"],
            "EY": float(c * cg[0] + s * cg[1]),
            "EZ": float(-s * cg[0] + c * cg[1]),
            "JX": res["j"],
            "JG": res["gamma"],
            "RT": res["rt"],
        })
    return out


def run_analysis(data):
    t0 = time.time()
    res = {}
    if data.get("loops"):
        loops = data["loops"]
        if "heal" in data:
            res["heal"] = data["heal"]      # passed through unchanged
    elif data.get("step"):
        import section_step
        try:
            loops, face_ids, gaps = _loops_from_step(data["step"])
            res["face_ids"] = face_ids
            res["gaps_closed"] = gaps
        except section_step.NoFaceError as exc:
            if not data.get("fallback_loops"):
                raise
            # no STEP face under the user's own mesh: the mesh boundary is
            # still right, and the window says that it was used
            loops = data["fallback_loops"]
            res["cad_fallback"] = str(exc)
    else:
        raise ValueError("input needs 'loops' or 'step'")
    nu = float(data.get("nu") or 0.0)
    mesh = section_mesh.mesh_section(
        loops, max_area=data.get("mesh_size") or None,
        n_target=int(data.get("n_target") or 3000),
        n_across=float(data.get("n_across") or 3.0))
    nodes, elements, boundary = mesh["nodes"], mesh["elements"], mesh["boundary"]
    t_mesh = time.time() - t0

    geo = section_fem.geometric_properties(nodes, elements)
    res.update(geo)
    res["perimeter"] = section_fem.outer_perimeter(mesh["loops"])
    n_parts, _ = section_mesh.element_parts(elements)
    res["n_parts"] = int(n_parts)
    res["n_elements"] = int(len(elements))
    res["n_nodes"] = int(len(nodes))
    res["mesh_info"] = mesh["info"]

    try:
        res.update(section_fem.plastic_properties(nodes, elements, geo["phi_deg"]))
        res["plastic_computed"] = True
    except Exception as exc:
        res["plastic_computed"] = False
        res["plastic_note"] = str(exc)

    res["warping_computed"] = False
    res["warping_note"] = ""
    if n_parts > 1:
        res["warping_note"] = ("section consists of {0} separate parts: torsion and shear "
                               "properties are not meaningful".format(n_parts))
    else:
        try:
            wp = section_fem.warping_properties(nodes, elements, geo, nu=nu, boundary=boundary)
            for key in ("_omega", "_psi", "_phi"):
                wp.pop(key, None)
            wp.pop("delta_s", None)
            res.update(wp)
            res["warping_computed"] = True
        except Exception as exc:
            res["warping_note"] = "warping analysis failed: {0}".format(exc)
    res["nu"] = nu
    res["aster"] = aster_block(res, nodes, elements)
    res["loops"] = [np.asarray(l).tolist() for l in mesh["loops"]]
    res["time_mesh_s"] = t_mesh
    res["time_total_s"] = time.time() - t0
    return res


def _jsonable(o):
    if isinstance(o, dict):
        return dict((k, _jsonable(v)) for k, v in o.items())
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return _jsonable(o.tolist())
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return o


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("Usage: python section_analysis.py <in.json> <out.json>")
        return 2
    in_path, out_path = argv
    try:
        with open(in_path, "r") as f:
            data = json.load(f)
        results = list_faces(data["list_faces"]) if data.get("list_faces") \
            else run_analysis(data)
        results["success"] = True
    except Exception as exc:
        results = {"success": False, "error": str(exc),
                   "traceback": traceback.format_exc()}
    with open(out_path, "w") as f:
        json.dump(_jsonable(results), f, indent=1)
    return 0 if results["success"] else 1


if __name__ == "__main__":
    sys.exit(main())
