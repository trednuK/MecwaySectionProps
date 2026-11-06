# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# section_mecway.py
# Responsibility: the Mecway side of MecwaySectionProps (all mw calls).
#   prepare(mw, mode, ...)        the way into a calculation: selection, or
#                                 temporary faces when the model has no mesh
#   build_temp_faces, discard_temp_mesh, remove_stale_faces
#                                 temporary faces of a STEP without a mesh
#   read_selection(mw)            selected faces -> nodes and coordinates
#   section_input(faces, mode)    plane, 2D frame, boundary loops (mesh) or
#                                 the STEP request (CAD) for the analysis
#   start_analysis(job)           section_analysis.py in a Python with numpy
#                                 and scipy (section_utils.find_python)
#   create_general_section(...)   Mecway material with a general section
#   shape_lines(material, res)    the simplified outline as ** SECTIE-VORM
#                                 lines
#   store_aster_line(...)         #ASTER-SECTIE and SECTIE-VORM lines as an
#                                 extra custom model definition (import of a
#                                 small .liml)
#
# Coordinates: Mecway's API and the .liml use metres; everything here is SI.
# The 2D frame of the section is as AreaPropsForAlibre: the face seen from
# outside, y = global Y projected onto the plane (-Z or +Z when the face is
# normal to Y), x = y cross n, so x, y, n are right-handed. The 2D origin is
# the projection of the global origin: x = P.u, y = P.v, offset = P.n.
#
# Compatible with IronPython 2.7.9 (Mecway); the geometry functions also
# run in CPython (tests/test_section_mecway.py, with a fake mw).

import io
import json
import math
import os
import re

import section_utils as su
from section_utils import log, tr

# Material properties of a Mecway general section (the attribute names of
# <geometric type="UniformGeneralSection"> in the .liml; mw API reference:
# "the same as the property's attribute name").
GENERAL_SECTION = "UniformGeneralSection"
# Relative deviation from one plane (of the size of the selection) that is
# straightened: the faces are projected onto the best-fitting plane and the
# deviation is reported (a mesh or CAD model that is not exactly flat, Mecway
# GUI test of 24 Oct 2026: 0.0002 mm). A larger deviation is a curved
# selection: error.
PLANE_TOL = 0.01
# Accuracy of the analysis: (key, about this many tri6 elements, element rows
# across a thin wall (section_mesh n_across)). "normal" is the default.
ACCURACY = (("coarse", 1000, 2.0), ("normal", 3000, 3.0),
            ("fine", 10000, 4.0), ("very_fine", 30000, 6.0))
# Component of the temporary faces of a STEP without a mesh. A name of its own:
# one that is left behind (Mecway or the script stopped) is removed at the next
# start of the window.
TEMP_COMPONENT = "SectionProps_tijdelijk"
# Vector exists only in the main script, which sets this.
Vector = None
# Tag of the custom model definition the #ASTER-SECTIE lines go into (CCX >
# Custom model definition; CCX reads '**' lines as comments).
# MecwayAsterBridge reads every custom text field, every occurrence
# (bridge_custom.CUSTOM_TAGS there).
CUSTOM_TAG = "ccxmodeldefinition"
LINE_PREFIX = u"** ASTER-SECTIE "
# Order of the keys in the #ASTER-SECTIE line (MecwayAsterBridge checks
# A, IY, IZ, JX against the material).
ASTER_KEYS = ("A", "IY", "IZ", "JX", "AY", "AZ", "EY", "EZ", "RY", "RZ",
              "RT", "JG", "IYR2", "IZR2")
# Outline of the section for MecwayAsterBridge, which draws it on the beams
# (Mecway has no shape for a general section). Lines of their own: a line
# starting with LINE_PREFIX that the bridge cannot read is an error there.
SHAPE_PREFIX = u"** SECTIE-VORM "
SHAPE_LINE = 120        # characters per line, unless the material name is long
SHAPE_TOL = 0.002       # simplification, relative to the size of the section
# Every creation adds these lines to the model; the API cannot remove them.
SHAPE_POINTS = 40       # at most per loop
SHAPE_TOTAL = 120       # at most over all loops


# ==========================================
# SMALL VECTOR HELPERS
# ==========================================
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, f):
    return (a[0] * f, a[1] * f, a[2] * f)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _norm(a):
    n = math.sqrt(_dot(a, a))
    if n == 0.0:
        return (0.0, 0.0, 0.0)
    return (a[0] / n, a[1] / n, a[2] / n)


def _dist(a, b):
    d = _sub(a, b)
    return math.sqrt(_dot(d, d))


def axis_name(vec):
    """'X', '-X', ... for a global axis direction, else '(x; y; z)'."""
    for i, name in enumerate("XYZ"):
        if abs(vec[i]) > 0.9999:
            return name if vec[i] > 0 else u"−" + name
    return u"({0}; {1}; {2})".format("%.3f" % vec[0], "%.3f" % vec[1],
                                     "%.3f" % vec[2])


# ==========================================
# READING THE SELECTION (mw)
# ==========================================
def read_selection(mw, face_ids=None):
    """
    The faces (default: the selected ones) as [{"eid", "face", "nodes",
    "coords", "centre"}] (coords per node in metres; centre = centroid of the
    element, for the outward normal). Faces only: in element or node
    selection mode mw.selected_faces() is empty, and so it is for a surface
    selected in Mecway's Geometry view.
    """
    faces = []
    centres = {}
    for fid in (mw.selected_faces() if face_ids is None else face_ids):
        eid = int(fid.element_id)
        nodes = [int(n) for n in mw.face_nodes(fid)]
        coords = []
        for n in nodes:
            p = mw.node(n)
            coords.append((float(p.x), float(p.y), float(p.z)))
        if eid not in centres:
            pts = [mw.node(n) for n in mw.nodes(eid)]
            centres[eid] = (sum(p.x for p in pts) / len(pts),
                            sum(p.y for p in pts) / len(pts),
                            sum(p.z for p in pts) / len(pts))
        faces.append({"eid": eid, "face": int(fid.face_number),
                      "nodes": nodes, "coords": coords,
                      "centre": centres[eid]})
    return faces


def components_info(mw):
    """[(component, material or None, is_line)] for the start of the
    window: is_line when its first element is a line2/line3 (a beam)."""
    out = []
    for comp in mw.components():
        mat = None
        try:
            mat = mw.material(comp)
        except Exception:
            pass
        is_line = False
        try:
            eids = list(mw.component_elements(comp))
            if eids:
                is_line = mw.element_shape(eids[0]) in ("line2", "line3")
        except Exception:
            pass
        out.append((comp, mat, is_line))
    return out


# ==========================================
# GEOMETRY OF THE SELECTION
# ==========================================
def _face_corners(nodes, coords):
    """
    (corner indices, {edge index: midside index}) of one face. 3/4 nodes:
    linear. 6/8 nodes: quadratic; the order of the midside nodes is found
    from the geometry (alternating corner/mid or corners first): the
    hypothesis whose midside nodes lie closest to the edge midpoints wins.
    """
    n = len(nodes)
    if n in (3, 4):
        return list(range(n)), {}
    if n not in (6, 8):
        raise ValueError(tr("Vlak met {0} knopen wordt niet ondersteund.",
                            "Face with {0} nodes is not supported.").format(n))
    k = n // 2

    def error(corners, mids):
        e = 0.0
        for i in range(k):
            a = coords[corners[i]]
            b = coords[corners[(i + 1) % k]]
            m = _mul(_add(a, b), 0.5)
            e += _dist(coords[mids[i]], m) / max(_dist(a, b), 1e-300)
        return e
    grouped = (list(range(k)), list(range(k, n)))
    alternating = (list(range(0, n, 2)), list(range(1, n, 2)))
    best = min((grouped, alternating), key=lambda h: error(*h))
    return best[0], dict(enumerate(best[1]))


def no_faces_text():
    """Text for an empty selection (mw.selected_faces() gives nothing for
    a surface selected in the Geometry view, Mecway 35)."""
    return tr("Geen mesh-vlakken geselecteerd (een selectie in de Geometry-"
              "weergave is voor scripts onzichtbaar). Toon de mesh, kies "
              "Select faces (f) en klik op een vlak.",
              "No mesh faces selected (a selection in the Geometry view is "
              "invisible to scripts). Show the mesh, choose Select faces (f) "
              "and click a face.")


def plane_axes(n_out):
    """(u, v) in-plane axes as AreaPropsForAlibre: the face seen from
    outside, v = global Y projected (or -Z/+Z for a face normal to Y),
    u = v x n."""
    if abs(n_out[1]) > 0.999:
        up = (0.0, 0.0, -1.0 if n_out[1] > 0 else 1.0)
    else:
        up = (0.0, 1.0, 0.0)
    d = _dot(up, n_out)
    v = _norm(_sub(up, _mul(n_out, d)))
    u = _norm(_cross(v, n_out))
    return u, v


def selection_plane(faces):
    """
    {"normal", "offset", "u", "v", "size", "deviation"} of the selected
    faces: the best-fitting plane (area-weighted normal, mean offset) and
    the largest distance of a node from it. Everything downstream projects
    onto this plane (x = P.u, y = P.v), so a small deviation is straightened;
    ValueError when it is larger than PLANE_TOL of the size. The normal
    points out of the elements (from the element centroid to the face), or
    follows the node order for shell faces.
    """
    if not faces:
        raise ValueError(no_faces_text())
    total = (0.0, 0.0, 0.0)
    points = []
    for f in faces:
        corners, _ = _face_corners(f["nodes"], f["coords"])
        pts = [f["coords"][i] for i in corners]
        # Newell's method: area-weighted normal of the polygon
        nrm = (0.0, 0.0, 0.0)
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            nrm = _add(nrm, ((a[1] - b[1]) * (a[2] + b[2]),
                             (a[2] - b[2]) * (a[0] + b[0]),
                             (a[0] - b[0]) * (a[1] + b[1])))
        centre = _mul(reduce(_add, pts), 1.0 / len(pts))
        outward = _sub(centre, f["centre"])
        if _dot(nrm, outward) < 0.0 and _dot(outward, outward) > 0.0:
            nrm = _mul(nrm, -1.0)
        total = _add(total, nrm)
        points.extend(f["coords"])
    normal = _norm(total)
    if normal == (0.0, 0.0, 0.0):
        raise ValueError(tr("De geselecteerde vlakken hebben geen "
                            "oppervlak.",
                            "The selected faces have no area."))
    size = max(_dist(points[0], p) for p in points) or 1.0
    offsets = [_dot(p, normal) for p in points]
    offset = sum(offsets) / len(offsets)
    worst = max(abs(o - offset) for o in offsets)
    if worst > PLANE_TOL * size:
        raise ValueError(tr("De geselecteerde vlakken liggen niet in één "
                            "vlak (afwijking {0} mm). Selecteer alleen "
                            "vlakken van één vlakke doorsnede.",
                            "The selected faces do not lie in one plane "
                            "(deviation {0} mm). Select only faces of one "
                            "flat cross-section.").format(
                                "%.4g" % (worst * 1e3)))
    u, v = plane_axes(normal)
    return {"normal": normal, "offset": offset, "u": u, "v": v,
            "size": size, "deviation": worst}


# Repair of a boundary whose faces do not quite fit together (an imported
# mesh with duplicate nodes, a non-conformal joint, a face left out),
# relative to the size of the selection. A real slit is bounded by closed
# edges, so only such defects leave free boundary ends; every repair is
# reported (heal in the job, notes in the window).
WELD_TOL = 1e-4       # nodes this close are one node (a mesh never has
                      # nodes this close: 10 000 elements across)
TJOINT_TOL = 1e-4     # a node this close to another face's edge splits it
GAP_TOL = 0.02        # free boundary ends this close are joined by a line


def _weld(coord, tol):
    """{node: canonical node}: nodes within tol of an earlier node map to
    it (grid hashing, cells of size tol)."""
    cells, canon = {}, {}
    for n in sorted(coord):
        x, y = coord[n]
        kx, ky = int(math.floor(x / tol)), int(math.floor(y / tol))
        found = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for m in cells.get((kx + dx, ky + dy), ()):
                    if math.hypot(coord[m][0] - x, coord[m][1] - y) <= tol:
                        found = m
                        break
                if found is not None:
                    break
            if found is not None:
                break
        if found is None:
            cells.setdefault((kx, ky), []).append(n)
            canon[n] = n
        else:
            canon[n] = found
    return canon


def _project_on_polyline(p, pts):
    """(distance, segment index, point) of p to the polyline pts."""
    best = (float("inf"), 0, pts[0])
    for i in range(len(pts) - 1):
        (ax, ay), (bx, by) = pts[i], pts[i + 1]
        dx, dy = bx - ax, by - ay
        ll = dx * dx + dy * dy
        t = 0.0 if ll == 0.0 else max(0.0, min(1.0, ((p[0] - ax) * dx +
                                                    (p[1] - ay) * dy) / ll))
        q = (ax + t * dx, ay + t * dy)
        d = math.hypot(p[0] - q[0], p[1] - q[1])
        if d < best[0]:
            best = (d, i + t, q)
    return best


def _split_edges(boundary, coord, tol):
    """Split boundary edges at nodes of other boundary edges that lie on
    them (T-joints of a non-conformal mesh). Returns (edges, count)."""
    nodes = set()
    for a, b, _ in boundary:
        nodes.add(a)
        nodes.add(b)
    out, count = [], 0
    for a, b, inner in boundary:
        pts = [coord[a]] + inner + [coord[b]]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        lo_x, hi_x = min(xs) - tol, max(xs) + tol
        lo_y, hi_y = min(ys) - tol, max(ys) + tol
        cuts = []
        for c in nodes:
            if c == a or c == b:
                continue
            x, y = coord[c]
            if not (lo_x <= x <= hi_x and lo_y <= y <= hi_y):
                continue
            d, s, _ = _project_on_polyline(coord[c], pts)
            if d <= tol and 0.0 < s < len(pts) - 1:
                cuts.append((s, c))
        if not cuts:
            out.append((a, b, inner))
            continue
        cuts.sort()
        count += len(cuts)
        start, piece = a, []
        k = 1               # next polyline point
        for s, c in cuts:
            while k < len(pts) - 1 and k <= s:
                piece.append(pts[k])
                k += 1
            out.append((start, c, piece))
            start, piece = c, []
        while k < len(pts) - 1:
            piece.append(pts[k])
            k += 1
        out.append((start, b, piece))
    return out, count


def _quadratic_2d(a, m, b):
    """Points between a and b on the parabola through a, m, b (t = 1/8 ...
    7/8): the curved edge of a quadratic face. A coarse 45 degree arc then
    loses 0.23% of the area of a quarter disc (the parabola itself 0.08%);
    t = 1/4, 1/2, 3/4 lost 0.7% (tests/test_section_mecway.py)."""
    out = []
    for t in [k / 8.0 for k in range(1, 8)]:
        n0 = (1.0 - t) * (1.0 - 2.0 * t)
        nm = 4.0 * t * (1.0 - t)
        n1 = t * (2.0 * t - 1.0)
        out.append((a[0] * n0 + m[0] * nm + b[0] * n1,
                    a[1] * n0 + m[1] * nm + b[1] * n1))
    return out


def boundary_loops(faces, plane):
    """
    Closed 2D loops [[x, y], ...] (metres, frame of plane) of the outer
    edges of the selected faces: an edge used by one selected face only.
    Quadratic edges are sampled on their parabola. The analysis takes the
    even-odd interior of all loops.

    Repairs (constants above): nodes at the same place are welded, an edge
    with another face's node on it is split there, and free ends of the
    boundary are joined to the nearest free end within GAP_TOL. Returns
    (loops, heal) with heal = {"welded": n, "split": n, "gaps_closed":
    [[length m, [x, y]], ...]}. ValueError when a gap is larger.
    """
    u, v = plane["u"], plane["v"]
    size = plane["size"]
    coord = {}
    raw = []
    for f in faces:
        corners, mids = _face_corners(f["nodes"], f["coords"])
        for i, n in enumerate(f["nodes"]):
            p = f["coords"][i]
            coord[n] = (_dot(p, u), _dot(p, v))
        k = len(corners)
        for i in range(k):
            raw.append((f["nodes"][corners[i]],
                        f["nodes"][corners[(i + 1) % k]],
                        f["nodes"][mids[i]] if i in mids else None))
    canon = _weld(coord, WELD_TOL * size)
    welded = sum(1 for n, c in canon.items() if n != c)
    count, edges = {}, {}
    for a, b, m in raw:
        a, b = canon[a], canon[b]
        if a == b:
            continue            # degenerate after welding
        inner = [] if m is None else _quadratic_2d(coord[a], coord[m],
                                                   coord[b])
        key = (min(a, b), max(a, b))
        count[key] = count.get(key, 0) + 1
        edges[key] = (a, b, inner)
    boundary = [edges[key] for key, c in count.items() if c == 1]
    if not boundary:
        raise ValueError(tr("De selectie heeft geen rand (gesloten "
                            "oppervlak?).",
                            "The selection has no boundary (closed "
                            "surface?)."))
    boundary, split = _split_edges(boundary, coord, TJOINT_TOL * size)
    if split:
        count, edges = {}, {}
        for a, b, inner in boundary:
            key = (min(a, b), max(a, b))
            count[key] = count.get(key, 0) + 1
            edges[key] = (a, b, inner)
        boundary = [edges[key] for key, c in count.items() if c == 1]

    # chains over the corner nodes; free ends (odd degree) first so that an
    # open chain is found from one end to the other
    at = {}
    for idx, (a, b, _) in enumerate(boundary):
        at.setdefault(a, []).append(idx)
        at.setdefault(b, []).append(idx)
    free = set(n for n, lst in at.items() if len(lst) % 2)
    order = [i for i, (a, b, _) in enumerate(boundary)
             if a in free or b in free] + list(range(len(boundary)))
    used = [False] * len(boundary)
    loops, open_chains = [], []
    for start in order:
        if used[start]:
            continue
        used[start] = True
        a, b, inner = boundary[start]
        if b in free and a not in free:
            a, b, inner = b, a, inner[::-1]
        first, pts, cur = a, [coord[a]] + list(inner), b
        while cur != first:
            nxt = [i for i in at[cur] if not used[i]]
            if not nxt:
                break
            i = nxt[0]
            used[i] = True
            a, b, inner = boundary[i]
            if a != cur:        # traverse the edge from cur
                a, b, inner = b, a, inner[::-1]
            pts += [coord[a]] + list(inner)
            cur = b
        if cur == first:
            loops.append(pts)
        else:
            open_chains.append(pts + [coord[cur]])

    gaps = []
    gap_tol = GAP_TOL * size
    while open_chains:
        chain = open_chains.pop(0)
        while True:
            end = chain[-1]
            # candidates: (distance, kind, index)
            cands = []
            if len(chain) >= 3:
                cands.append((math.hypot(end[0] - chain[0][0],
                                         end[1] - chain[0][1]), "self", -1))
            for j, other in enumerate(open_chains):
                cands.append((math.hypot(end[0] - other[0][0],
                                         end[1] - other[0][1]), "fwd", j))
                cands.append((math.hypot(end[0] - other[-1][0],
                                         end[1] - other[-1][1]), "rev", j))
            if not cands:
                cands.append((float("inf"), "none", -1))
            d, kind, j = min(cands)
            if d > gap_tol:
                if d == float("inf"):
                    d = 0.0
                raise ValueError(tr(
                    "De rand van de selectie is niet gesloten: een opening "
                    "bij ({0}; {1}) mm is groter dan {2} mm (of er is geen "
                    "ander rand-eind). Selecteer een gesloten gebied.",
                    "The boundary of the selection is not closed: an "
                    "opening at ({0}; {1}) mm is larger than {2} mm (or "
                    "there is no other free end). Select a closed region."
                ).format("%.4g" % (end[0] * 1e3), "%.4g" % (end[1] * 1e3),
                         "%.4g" % (gap_tol * 1e3)))
            if kind == "self":
                target = chain[0]
            else:
                other = open_chains.pop(j)
                if kind == "rev":
                    other = other[::-1]
                target = other[0]
            if d > WELD_TOL * size:
                gaps.append([d, [0.5 * (end[0] + target[0]),
                                 0.5 * (end[1] + target[1])]])
            if kind == "self":
                loops.append(chain if d > WELD_TOL * size else chain[:-1])
                break
            chain = chain + (other if d > WELD_TOL * size else other[1:])
    loops = [[[p[0], p[1]] for p in lp] for lp in loops if len(lp) >= 3]
    return loops, {"welded": welded, "split": split, "gaps_closed": gaps}


# ==========================================
# CAD (STEP) OF THE SELECTION
# ==========================================
_GEOMETRY_RE = re.compile(r'<(/?)(assembly|geometry)\b([^>]*)>')
_ELSET_RE = re.compile(r'<elset\b([^>]*)>')
_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _xml_unescape(text):
    return (text.replace("&quot;", '"').replace("&apos;", "'")
            .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))


def liml_geometries(liml_path):
    """({geometry id: STEP path}, {component: geometry id}) from the saved
    .liml (attributes only, read as text: fast also for a big model). The
    geometries of a STEP assembly have no file of their own: Mecway 35 puts
    them in an <assembly filename=...>, one per instance."""
    geoms, comps = {}, {}
    folder = os.path.dirname(os.path.abspath(liml_path))

    def full(attrs):
        path = _xml_unescape(attrs["filename"])
        return path if os.path.isabs(path) else os.path.join(folder, path)

    assembly = None
    with io.open(liml_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "assembly" in line or "<geometry" in line:
                for m in _GEOMETRY_RE.finditer(line):
                    attrs = dict(_ATTR_RE.findall(m.group(3)))
                    if m.group(2) == "assembly":
                        assembly = None if m.group(1) or \
                            "filename" not in attrs else full(attrs)
                    elif "id" in attrs and "filename" in attrs:
                        geoms[attrs["id"]] = full(attrs)
                    elif "id" in attrs and assembly:
                        geoms[attrs["id"]] = assembly
            if "<elset" in line:
                for m in _ELSET_RE.finditer(line):
                    attrs = dict(_ATTR_RE.findall(m.group(1)))
                    if "geomid" in attrs and "name" in attrs:
                        comps[_xml_unescape(attrs["name"])] = attrs["geomid"]
    return geoms, comps


class NeedStepFile(Exception):
    """The STEP file is not known (e.g. a model that is not saved): the
    window asks the user. component None: for the model as a whole."""

    def __init__(self, component):
        Exception.__init__(self, component)
        self.component = component


def _stem(path):
    return os.path.splitext(os.path.basename(path))[0].lower()


def step_file(mw, component, known=None):
    """
    Path of the STEP file of a component: the link in the saved .liml (the
    component's geomid; a component meshed after the last save has no geomid
    yet, but generate_mesh names it after the STEP file, tested in Mecway
    35), else the file the user pointed at in this window (known:
    {component: path}). NeedStepFile when neither gives an existing file:
    Mecway's API has no call for the file of a geometry.
    """
    liml = mw.file_name()
    if liml and os.path.isfile(liml):
        geoms, comps = liml_geometries(liml)
        if comps.get(component) in geoms:
            found = [geoms[comps[component]]]
        else:
            found = [p for p in geoms.values()
                     if _stem(p) == component.lower()]
            if not found and len(geoms) == 1:
                found = list(geoms.values())
        for path in found:
            if os.path.isfile(path):
                return path
    path = (known or {}).get(component)
    if path and os.path.isfile(path):
        return path
    raise NeedStepFile(component)


def model_step_files(mw, known=None):
    """All STEP files of the model: the saved .liml (it may be older than the
    open model), else the file the user pointed at (known[""]). NeedStepFile
    (None) when that gives no existing file."""
    paths = []
    liml = mw.file_name()
    if liml and os.path.isfile(liml):
        # a set: the instances of an assembly share one file
        paths = sorted(set(p for p in liml_geometries(liml)[0].values()
                           if os.path.isfile(p)))
    if not paths:
        path = (known or {}).get("")
        if not path or not os.path.isfile(path):
            raise NeedStepFile(None)
        paths = [path]
    return paths


def step_block(path, faces, plane, hint=None):
    """The "step" block for section_analysis (section_step.find_placed and
    placed_loops_2d): the file, the plane, the centroids of the faces and,
    when the faces are known, hint."""
    points = []
    for f in faces:
        corners, _ = _face_corners(f["nodes"], f["coords"])
        pts = [f["coords"][i] for i in corners]
        points.append(list(_mul(reduce(_add, pts), 1.0 / len(pts))))
    block = {"file": path, "normal": list(plane["normal"]),
             "offset": plane["offset"], "u": list(plane["u"]),
             "v": list(plane["v"]), "points": points,
             "tol": max(1e-6, 1e-4 * plane["size"],
                        2.0 * plane.get("deviation", 0.0))}
    if hint:
        block["hint"] = hint
    return block


def step_request(mw, faces, plane, known=None):
    """
    The "step" block of faces of the user's own mesh: the STEP file of their
    component. NeedStepFile when the file is not known; ValueError when the
    faces belong to more than one file.
    """
    paths = set()
    for comp in set(mw.element_component(f["eid"]) for f in faces):
        paths.add(step_file(mw, comp, known))
    if len(paths) > 1:
        raise ValueError(tr("CAD-vlak: de vlakken horen bij meer dan één "
                            "STEP-bestand.",
                            "CAD face: the faces belong to more than one "
                            "STEP file."))
    return step_block(paths.pop(), faces, plane)


def accuracy_values(key):
    """(n_target, n_across) of an ACCURACY key; "normal" when unknown."""
    for k, n_target, n_across in ACCURACY:
        if k == key:
            return n_target, n_across
    return accuracy_values("normal")


def section_input(mw, faces, mode, accuracy="normal", known=None):
    """(job dict for section_analysis, plane) for mode "mesh" or "cad"
    (known: step_file). job["heal"]: the repairs (boundary_loops;
    "flattened" = the deviation from one plane that was straightened,
    metres)."""
    plane = selection_plane(faces)
    n_target, n_across = accuracy_values(accuracy)
    job = {"nu": 0.0, "mesh_size": None, "n_target": n_target,
           "n_across": n_across, "accuracy": accuracy}
    if mode == "cad":
        job["step"] = step_request(mw, faces, plane, known)
        job["heal"] = {}
        # when the STEP does not have the face, the mesh boundary is used
        # (only for the user's own mesh, see prepare)
        try:
            job["fallback_loops"], job["fallback_heal"] = boundary_loops(
                faces, plane)
        except ValueError:
            pass
    else:
        job["loops"], job["heal"] = boundary_loops(faces, plane)
    # 1e-9 of the size is round-off, not a deviation worth reporting
    if plane["deviation"] > 1e-9 * plane["size"]:
        job["heal"]["flattened"] = plane["deviation"]
    return job, plane


# ==========================================
# TEMPORARY FACES OF A STEP WITHOUT A MESH
# ==========================================
# Mecway's API has no access to a surface selected in the Geometry view, and
# no mesh means no faces to select. mw.generate_mesh() would mesh every part
# (192 000 elements and 37 s on a small assembly). So the planar faces of the
# STEP file are shown as tri3 elements at their global position in a temporary
# component (section_analysis.list_faces); the user clicks one in Mecway and
# nothing is computed on these triangles: they only tell which STEP face is
# meant. Everything is removed after the calculation.

def _delete_added(mw, elements, nodes_before, components):
    """Remove these elements, the nodes that were not there before and that
    no other element uses, and these components when they are empty."""
    alive = set(int(e) for e in mw.all_elements())
    gone = [e for e in elements if e in alive]
    if gone:
        mw.delete_elements(gone)
    used = set()
    for e in mw.all_elements():
        used.update(int(n) for n in mw.nodes(e))
    nodes = [int(n) for n in mw.all_nodes()
             if int(n) not in nodes_before and int(n) not in used]
    if nodes:
        mw.delete_nodes(nodes)
    for comp in components:
        if comp in mw.components() and not list(mw.component_elements(comp)):
            mw.delete_component(comp)


def remove_stale_faces(mw):
    """Remove a temporary component that was left behind. True when one
    was found."""
    stale = [c for c in mw.components()
             if str(c).startswith(TEMP_COMPONENT)]
    if not stale:
        return False
    elements = []
    nodes = set()
    for comp in stale:
        for e in mw.component_elements(comp):
            elements.append(int(e))
            nodes.update(int(n) for n in mw.nodes(e))
    others = set(int(n) for n in mw.all_nodes()) - nodes
    _delete_added(mw, elements, others, stale)
    mw.display()
    log("INFO: MecwaySectionProps: left-over temporary faces removed.")
    return True


def build_temp_faces(mw, faces):
    """The faces of section_analysis.list_faces as tri3 elements in a
    temporary component. Returns what is needed to read a pick and to remove
    them again."""
    remove_stale_faces(mw)
    before = set(int(n) for n in mw.all_nodes())
    comp = mw.new_component(TEMP_COMPONENT) or TEMP_COMPONENT
    owner = {}
    try:
        for index, face in enumerate(faces):
            ids = [mw.new_node(Vector(p[0], p[1], p[2]))
                   for p in face["points"]]
            for tri in face["triangles"]:
                eid = mw.new_element("tri3", [ids[k] for k in tri], comp)
                owner[int(eid)] = index
    except Exception:
        _delete_added(mw, sorted(owner), before, [comp])
        raise
    try:
        mw.set_model_active()
        mw.display()
    except Exception as e:
        log("WARNING: MecwaySectionProps: display: {0}".format(e))
    log("INFO: MecwaySectionProps: {0} temporary faces, {1} triangles."
        .format(len(faces), len(owner)))
    return {"elements": sorted(owner), "nodes_before": before,
            "components": [comp], "owner": owner, "faces": faces}


def temp_mesh_alive(mw, temp):
    """False when the temporary faces are gone (removed in Mecway itself)."""
    if not temp:
        return False
    alive = set(int(e) for e in mw.all_elements())
    return any(e in alive for e in temp["elements"])


def discard_temp_mesh(mw, temp):
    """Remove what build_temp_faces added and nothing else."""
    _delete_added(mw, temp["elements"], temp["nodes_before"],
                  temp["components"])
    mw.display()
    log("INFO: MecwaySectionProps: temporary faces removed.")


def picked_faces(mw, temp):
    """Indices in temp["faces"] of what is selected in Mecway: faces in
    face mode, elements in element mode."""
    eids = [int(f.element_id) for f in mw.selected_faces()]
    eids.extend(int(e) for e in mw.selected_elements())
    return sorted(set(temp["owner"][e] for e in eids if e in temp["owner"]))


def temp_job(mw, temp, picked, accuracy):
    """(job, plane, faces) for picked temporary faces. Everything after this
    is the route of a selection; only the STEP faces are already known
    (hint), so nothing is searched."""
    chosen = [temp["faces"][i] for i in picked]
    if len(set(f["file"] for f in chosen)) > 1:
        raise ValueError(tr("CAD-vlak: de vlakken horen bij meer dan één "
                            "STEP-bestand.",
                            "CAD face: the faces belong to more than one "
                            "STEP file."))
    faces = []
    for eid, index in sorted(temp["owner"].items()):
        if index in picked:
            nodes = [int(n) for n in mw.nodes(eid)]
            coords = []
            for n in nodes:
                p = mw.node(n)
                coords.append((float(p.x), float(p.y), float(p.z)))
            faces.append({"eid": eid, "face": 1, "nodes": nodes,
                          "coords": coords,
                          "centre": _mul(reduce(_add, coords), 1.0 / 3.0)})
    plane = selection_plane(faces)
    n_target, n_across = accuracy_values(accuracy)
    occurrences = {}
    for f in chosen:
        occurrences.setdefault(f["occurrence"], []).append(f["face"])
    hint = {"hits": [[k, ids] for k, ids in sorted(occurrences.items())]}
    job = {"nu": 0.0, "mesh_size": None, "n_target": n_target,
           "n_across": n_across, "accuracy": accuracy,
           "step": step_block(chosen[0]["file"], faces, plane, hint),
           "heal": {"temp_mesh": True}}
    return job, plane, faces


def prepare(mw, mode, accuracy="normal", temp=None, known=None):
    """
    The way into a calculation, on the script thread. Returns a dict with
    "temp" (the temporary faces or None) and "state":
    "ready": with "faces", "job" and "plane";
    "pick": temporary faces exist and the user must click one;
    "list": the model has no mesh: list the faces of "paths" and call
    build_temp_faces (not here: the listing is a process);
    "step": the STEP file of "component" is not known (None: of the model).
    A model with its own mesh is never touched.
    """
    if temp is not None and not temp_mesh_alive(mw, temp):
        temp = None
    if temp is not None:
        picked = picked_faces(mw, temp)
        if picked:
            job, plane, faces = temp_job(mw, temp, picked, accuracy)
            return {"state": "ready", "faces": faces, "job": job,
                    "plane": plane, "temp": temp}
        if not list(mw.selected_faces()):
            return {"state": "pick", "temp": temp}
        # something else is selected: the user's own mesh, made meanwhile
        discard_temp_mesh(mw, temp)
        temp = None
    face_ids = list(mw.selected_faces())
    if not face_ids:
        if list(mw.all_elements()):
            raise ValueError(no_faces_text())
        try:
            return {"state": "list", "paths": model_step_files(mw, known),
                    "temp": None}
        except NeedStepFile as e:
            return {"state": "step", "component": e.component, "temp": None}
    faces = read_selection(mw, face_ids)
    try:
        job, plane = section_input(mw, faces, mode, accuracy, known)
    except NeedStepFile as e:
        return {"state": "step", "component": e.component, "temp": None}
    return {"state": "ready", "faces": faces, "job": job, "plane": plane,
            "temp": None}


# ==========================================
# THE ANALYSIS PROCESS
# ==========================================
class MissingPython(Exception):
    """No Python with numpy and scipy (info: section_utils.find_python)."""

    def __init__(self, info):
        Exception.__init__(self, "no Python with numpy and scipy")
        self.info = info


def missing_python_text(info):
    """The prerequisite in words; with info["pip"] it ends in the question
    whether to install."""
    if info.get("own") and not info.get("pip"):
        head = tr(u"De Python uit de instellingen is niet gevonden: {0}",
                  u"The Python in the settings was not found: {0}").format(
                      info["own"])
    elif info.get("pip"):
        head = tr(u"Python is gevonden, maar zonder (recente) numpy en scipy: "
                  u"{0}",
                  u"Python was found, but without (recent) numpy and scipy: "
                  u"{0}").format(info["pip"])
    else:
        head = tr(u"Python 3 is niet gevonden.", u"Python 3 was not found.")
    text = tr(u"Voorwaarde: MecwaySectionProps rekent met Python 3 met numpy "
              u"en scipy.\n\n",
              u"Prerequisite: MecwaySectionProps calculates with Python 3 "
              u"with numpy and scipy.\n\n") + head + u"\n\n"
    if info.get("pip"):
        return text + tr(u"Installeer ze met:\n{0}\n\nNu installeren in een "
                         u"apart venster?",
                         u"Install them with:\n{0}\n\nInstall now in a "
                         u"separate window?").format(
                             su.pip_command(info["pip"]))
    return text + tr(u"Installeer Python 3 van python.org en daarna:\n"
                     u"python -m pip install numpy scipy\n\nOf zet het pad "
                     u"van een python.exe met numpy en scipy als 'python' in "
                     u"{0}.",
                     u"Install Python 3 from python.org and then:\n"
                     u"python -m pip install numpy scipy\n\nOr put the path "
                     u"of a python.exe with numpy and scipy as 'python' in "
                     u"{0}.").format(su.SETTINGS_PATH)


def install_packages(python):
    """Run pip for numpy and scipy in a console window of its own, so the
    user sees what happens; only after the user's yes in the window."""
    import clr
    clr.AddReference("System")
    from System.Diagnostics import Process, ProcessStartInfo
    info = ProcessStartInfo("cmd.exe")
    info.Arguments = u'/c "{0} & pause"'.format(su.pip_command(python))
    info.UseShellExecute = True
    log("INFO: MecwaySectionProps: {0}".format(su.pip_command(python)))
    Process.Start(info)


def work_folder():
    """The work folder (section_utils.work_dir, created)."""
    return su.work_dir()


_STDERR = []         # error output of the running process


def _start(job, name):
    """Write the job and start section_analysis.py without a console window.
    Returns (process, result path). Raises MissingPython when no Python
    with numpy and scipy is found (the window checks that first)."""
    found = su.find_python()
    python = found["path"]
    if not python:
        raise MissingPython(found)
    folder = work_folder()
    src = os.path.join(folder, name + "_input.json")
    dst = os.path.join(folder, name + "_results.json")
    if os.path.isfile(dst):
        os.remove(dst)
    with io.open(src, "w", encoding="utf-8") as f:
        # ensure_ascii=False: IronPython's json fails on non-ASCII text
        # with ensure_ascii=True (e.g. a folder name with an accent).
        f.write(u"{0}".format(json.dumps(job, ensure_ascii=False)))
    script = os.path.join(su.SCRIPTS_DIR, "section_analysis.py")
    import clr
    clr.AddReference("System")
    from System.Diagnostics import Process, ProcessStartInfo
    info = ProcessStartInfo(python)
    info.Arguments = u'{0} "{1}" "{2}" "{3}"'.format(su.PYTHON_FLAGS, script,
                                                     src, dst)
    info.UseShellExecute = False
    info.CreateNoWindow = True
    info.RedirectStandardError = True
    info.WorkingDirectory = folder
    log("INFO: MecwaySectionProps: {0} {1}".format(python, info.Arguments))
    del _STDERR[:]

    def collect(sender, e):
        # read while it runs: a full pipe would block the process
        if e.Data is not None:
            _STDERR.append(e.Data)
    proc = Process()
    proc.StartInfo = info
    proc.ErrorDataReceived += collect
    proc.Start()
    proc.BeginErrorReadLine()
    return proc, dst


def start_analysis(job):
    """Start the calculation: (process, result path)."""
    return _start(job, "section")


def list_step_faces(paths, timeout=120):
    """(faces, unplaced): the planar faces of STEP files at their global
    position, with triangles (section_analysis.list_faces), and the number of
    faces the assembly does not place. Waits for the process."""
    faces = []
    unplaced = 0
    for path in paths:
        proc, dst = _start({"list_faces": path}, "section_faces")
        if not proc.WaitForExit(int(timeout * 1000)):
            proc.Kill()
            raise RuntimeError(tr("Het lezen van de STEP duurde te lang.",
                                  "Reading the STEP file took too long."))
        res = read_results(proc, dst)
        unplaced += res.get("unplaced") or 0
        faces.extend(res["faces"])
    if unplaced:
        log("WARNING: MecwaySectionProps: {0} faces not placed by the "
            "assembly.".format(unplaced))
    if not faces:
        raise ValueError(tr("Geen vlakke vlakken gevonden in de STEP.",
                            "No planar faces found in the STEP file."))
    return faces, unplaced


def read_results(proc, dst):
    """Results dict of a finished process; RuntimeError on a failure."""
    proc.WaitForExit()      # also waits for the last error output
    stderr = u"\n".join(_STDERR)
    if not os.path.isfile(dst):
        if "ImportError" in stderr or "ModuleNotFoundError" in stderr:
            su.forget_python()
        raise RuntimeError(tr("De berekening gaf geen resultaat.\n{0}",
                              "The analysis produced no result.\n{0}")
                           .format(stderr[-1500:]))
    with io.open(dst, encoding="utf-8") as f:
        res = json.loads(f.read())
    if not res.get("success"):
        log("ERROR: MecwaySectionProps: {0}".format(
            res.get("traceback") or res.get("error")))
        raise RuntimeError(res.get("error") or u"?")
    return res


# ==========================================
# GENERAL SECTION IN MECWAY
# ==========================================
def principal_loops(res):
    """The loops of the results in principal coordinates about the centroid:
    [[(v, w), ...], ...]."""
    cx, cy = res["centroid"]
    phi = math.radians(res["phi_deg"])
    c, s = math.cos(phi), math.sin(phi)
    return [[((x - cx) * c + (y - cy) * s, -(x - cx) * s + (y - cy) * c)
             for x, y in loop] for loop in res.get("loops", [])]


def recovery_point(res):
    """Mecway's stress recovery point (principal coordinates V, W): the
    boundary point farthest from the centroid (largest bending stress for
    a general direction of the moment)."""
    best, point = -1.0, (0.0, 0.0)
    for loop in principal_loops(res):
        for v, w in loop:
            r = v * v + w * w
            if r > best:
                best, point = r, (v, w)
    return point


def general_section_values(res):
    """{Mecway property: SI value} of the general section: area, iyy = I
    about V = principal axis 1, izz = I about W = axis 2, torsion constant,
    perimeter and the stress recovery point."""
    py, pz = recovery_point(res)
    return [("area", res["area"]), ("iyy", res["i11_c"]),
            ("izz", res["i22_c"]), ("torsionconstant", res["j"]),
            ("perimeter", res["perimeter"]), ("pointy", py),
            ("pointz", pz)]


# Material groups copied from the component's current material.
_COPY = (("mechanical", "Isotropic", ("youngsmodulus", "poissonratio",
                                      "thermalexpansion")),
         ("density", None, ("density",)))


def create_general_section(mw, name, res, component=None, copy_from=None):
    """
    New Mecway material `name` (Mecway may change the name) with a general
    section from the results; with copy_from the isotropic elastic data
    and density of that material are copied; with component the material
    is assigned to it. Returns the material name.
    """
    mat = mw.new_material(name)
    mw.set_material_type(mat, "geometric", GENERAL_SECTION)
    for prop, value in general_section_values(res):
        mw.set_material_property(mat, prop, float(value))
    if copy_from:
        for group, only, props in _COPY:
            try:
                kind = mw.material_type(copy_from, group)
            except Exception:
                continue
            if not kind or kind == "None" or (only and kind != only):
                continue
            mw.set_material_type(mat, group, kind)
            for prop in props:
                try:
                    value = mw.material_property(copy_from, prop)
                except Exception:
                    continue
                if value is not None:
                    mw.set_material_property(mat, prop, value)
    if component:
        mw.set_material(component, mat)
    log("INFO: MecwaySectionProps: material '{0}' (general section){1}."
        .format(mat, " assigned to '{0}'".format(component)
                if component else ""))
    return mat


def aster_line(material, res):
    """The #ASTER-SECTIE line (without the '** ' prefix handling) for the
    material: SI values, 10 significant digits."""
    aster = dict(res["aster"])
    # The checked values exactly as written into the Mecway material.
    aster["A"], aster["IY"] = res["area"], res["i11_c"]
    aster["IZ"], aster["JX"] = res["i22_c"], res["j"]
    parts = []
    for key in ASTER_KEYS:
        if aster.get(key) is not None:
            parts.append(u"{0}={1}".format(key, "%.10g" % aster[key]))
    return LINE_PREFIX + u"{0}: {1}".format(material, u", ".join(parts))


def _keep(pts, tol):
    """Douglas-Peucker on the open chain pts: the points to keep."""
    keep = set([0, len(pts) - 1])
    stack = [(0, len(pts) - 1)]
    while stack:
        lo, hi = stack.pop()
        worst, index = tol, None
        for i in range(lo + 1, hi):
            d = _project_on_polyline(pts[i], [pts[lo], pts[hi]])[0]
            if d > worst:
                worst, index = d, i
        if index is not None:
            keep.add(index)
            stack.append((lo, index))
            stack.append((index, hi))
    return [pts[i] for i in sorted(keep)]


def simplify_loop(loop, tol):
    """The closed loop with the points that matter within tol. A loop with
    no area at this size comes back with fewer than 3 points."""
    loop = [tuple(p) for p in loop]
    if len(loop) <= 3:
        return loop
    far = max(range(1, len(loop)),
              key=lambda i: math.hypot(loop[i][0] - loop[0][0],
                                       loop[i][1] - loop[0][1]))
    return (_keep(loop[:far + 1], tol)[:-1] +
            _keep(loop[far:] + loop[:1], tol)[:-1])


def shape_loops(res):
    """The loops in (V, W), simplified: SHAPE_TOL of the size of the section,
    coarser when that leaves more than SHAPE_POINTS or SHAPE_TOTAL points."""
    loops = principal_loops(res)
    points = [p for lp in loops for p in lp]
    if not points:
        return []
    tol = SHAPE_TOL * max(
        max(p[0] for p in points) - min(p[0] for p in points),
        max(p[1] for p in points) - min(p[1] for p in points))
    while True:
        out = [lp for lp in [simplify_loop(lp, tol) for lp in loops]
               if len(lp) >= 3]
        if (sum(len(lp) for lp in out) <= SHAPE_TOTAL and
                all(len(lp) <= SHAPE_POINTS for lp in out)):
            return out
        tol *= 1.5


def shape_lines(material, res):
    """
    The ** SECTIE-VORM lines of the section (contract in AGENTS.md):
      ** SECTIE-VORM <material>: N=<points per loop>, A=<area>
      ** SECTIE-VORM <material>: P=v w v w ...
    V, W as in shape_loops, SI. The loops are closed implicitly, the interior
    is even-odd as in the analysis. A lets the reader see that the outline
    still belongs to the material.
    """
    loops = shape_loops(res)
    if not loops:
        return []
    head = SHAPE_PREFIX + u"{0}: ".format(material)
    lines = [head + u"N={0}, A={1}".format(
        u" ".join("%d" % len(lp) for lp in loops), "%.10g" % res["area"])]
    room = SHAPE_LINE - len(head) - 2
    row = u""
    for loop in loops:
        for v, w in loop:
            pair = u"%.5g %.5g" % (v, w)
            if row and len(row) + 1 + len(pair) > room:
                lines.append(head + u"P=" + row)
                row = u""
            row = row + u" " + pair if row else pair
    lines.append(head + u"P=" + row)
    return lines


def _xml_escape(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def aster_line_liml(text, version="34"):
    """A .liml with only a custom model definition holding `text`."""
    return u'<liml version="{0}">\n  <{1}>{2}</{1}>\n</liml>\n'.format(
        version, CUSTOM_TAG, _xml_escape(text))


def store_aster_line(mw, material, res):
    """
    Put the #ASTER-SECTIE line of `material` and the SECTIE-VORM lines of
    its outline in the model: a .liml with only a custom model definition
    is imported into the open model. Mecway then
    keeps it as an extra custom model definition (CCX branch of the tree);
    MecwayAsterBridge reads every one in file order, so a newer line of the
    same material wins (its bridge_from_liml._section_extras). Tested in
    Mecway 34 (23 Oct 2026): no save or reopen needed, also for a model
    without a file. Saving the model and reopening it (the first version)
    closed this window in Mecway's GUI. Returns the line.
    """
    line = aster_line(material, res)
    path = os.path.join(work_folder(), "section_aster_line.liml")
    version = u"34"
    try:
        version = u"{0}".format(mw.version()).split(".")[0] or version
    except Exception:
        pass
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(aster_line_liml(
            u"\n".join([line] + shape_lines(material, res)), version))
    mw.import_file(path, "m")
    log("INFO: MecwaySectionProps: '{0}' and the outline imported as a "
        "custom model definition.".format(line))
    return line


try:
    reduce
except NameError:           # Python 3 (offline tests)
    from functools import reduce
