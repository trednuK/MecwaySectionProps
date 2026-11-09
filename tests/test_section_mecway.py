# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# Offline test of Scripts/section_mecway.py (Python 2.7 and 3): plane and
# boundary of selected faces, quadratic faces, holes, repairs and the
# #ASTER-SECTIE and SECTIE-VORM lines (the formats MecwayAsterBridge reads).
#
#   python tests/test_section_mecway.py

from __future__ import print_function

import io
import math
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(globals().get("__file__",
                                                     sys.argv[0])))
sys.path.insert(0, os.path.join(_HERE, "..", "Scripts"))
import section_utils  # noqa: E402
section_utils.settings()["language"] = "en"   # in memory only
import section_mecway as smw  # noqa: E402

LOG = []
smw.log = LOG.append


def check(name, cond):
    print(("OK   " if cond else "FOUT ") + name)
    if not cond:
        check.failed = True


check.failed = False


def area(loop):
    a = 0.0
    for i in range(len(loop)):
        x0, y0 = loop[i]
        x1, y1 = loop[(i + 1) % len(loop)]
        a += x0 * y1 - x1 * y0
    return 0.5 * a


def even_odd_area(loops):
    """Area of nested loops: the absolute areas with sign by depth."""
    return sum(abs(area(lp)) * (1 if _depth(lp, loops) % 2 == 0 else -1)
               for lp in loops)


def _inside(pt, loop):
    x, y = pt
    c = False
    for i in range(len(loop)):
        x0, y0 = loop[i]
        x1, y1 = loop[(i + 1) % len(loop)]
        if (y0 > y) != (y1 > y) and \
                x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            c = not c
    return c


def _depth(lp, loops):
    return sum(1 for other in loops if other is not lp and
               _inside(lp[0], other))


def grid_faces(nx, ny, w, h, z, skip=(), below=True):
    """quad4 faces of a grid in the plane z (element centres below)."""
    nid = {}

    def node(i, j):
        key = (i, j)
        if key not in nid:
            nid[key] = len(nid) + 1
        return nid[key]
    faces = []
    for i in range(nx):
        for j in range(ny):
            if (i, j) in skip:
                continue
            corners = [(i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)]
            nodes = [node(a, b) for a, b in corners]
            coords = [(a * w / nx, b * h / ny, z) for a, b in corners]
            cx = (i + 0.5) * w / nx
            cy = (j + 0.5) * h / ny
            faces.append({"eid": len(faces) + 1, "face": 1, "nodes": nodes,
                          "coords": coords,
                          "centre": (cx, cy, z - 0.01 if below else z + 0.01)})
    return faces


# --- rectangle of 2 x 2 quad4 faces at z = 0.2 ---------------------------
faces = grid_faces(2, 2, 0.1, 0.05, 0.2)
plane = smw.selection_plane(faces)
check("normal +z (outward from the elements)",
      max(abs(a - b) for a, b in zip(plane["normal"], (0, 0, 1))) < 1e-12)
check("offset 0.2", abs(plane["offset"] - 0.2) < 1e-12)
check("u = X, v = Y", smw.axis_name(plane["u"]) == "X" and
      smw.axis_name(plane["v"]) == "Y")
loops, heal = smw.boundary_loops(faces, plane)
check("one loop of 8 corner points", len(loops) == 1 and len(loops[0]) == 8)
check("area 0.005", abs(abs(area(loops[0])) - 0.005) < 1e-15)
# elements above the face: normal -z, mirrored view (u = -X)
plane2 = smw.selection_plane(grid_faces(2, 2, 0.1, 0.05, 0.2, below=False))
check("normal -z when the elements are above", plane2["normal"][2] < -0.999
      and smw.axis_name(plane2["u"]) == u"−X")

# --- hole: 3 x 3 grid without the centre face ------------------------------
faces = grid_faces(3, 3, 0.03, 0.03, 0.0, skip=[(1, 1)])
loops, heal = smw.boundary_loops(faces, smw.selection_plane(faces))
check("hole: two loops", len(loops) == 2)
check("hole: even-odd area 8e-4", abs(even_odd_area(loops) - 8e-4) < 1e-15)

# --- quadratic face (quad8, alternating corner/mid), curved edge ------------
r = 0.01
c45 = r * math.cos(math.radians(45.0))
# quarter disc between 0 and 90 degrees: corners (0,0), (r,0), (0,r) +
# a 4th corner on the arc at 45 deg; midside nodes on the arcs
corner = [(0.0, 0.0), (r, 0.0), (c45, c45), (0.0, r)]


def arc_pt(a):
    return (r * math.cos(math.radians(a)), r * math.sin(math.radians(a)))
mids = [(r / 2, 0.0), arc_pt(22.5), arc_pt(67.5), (0.0, r / 2)]
for order in ("alternating", "grouped"):
    if order == "alternating":
        pts = [corner[0], mids[0], corner[1], mids[1], corner[2], mids[2],
               corner[3], mids[3]]
    else:
        pts = corner + mids
    face = {"eid": 1, "face": 1, "nodes": list(range(1, 9)),
            "coords": [(x, y, 0.0) for x, y in pts],
            "centre": (0.004, 0.004, -0.001)}
    lp, _ = smw.boundary_loops([face], smw.selection_plane([face]))
    exact = math.pi * r * r / 4
    a = abs(area(lp[0]))
    check("quad8 {0}: 32 boundary points".format(order), len(lp[0]) == 32)
    # coarse on purpose (two 45 degree arcs): 0.23% too small
    check("quad8 {0}: area of the quarter disc within 0.3% ({1:.5f})"
          .format(order, a / exact), abs(a / exact - 1) < 3e-3)

# --- repairs: duplicate nodes and a T-joint ----------------------------------
def quad(eid, ids, pts):
    cx = sum(p[0] for p in pts) / 4.0
    cy = sum(p[1] for p in pts) / 4.0
    return {"eid": eid, "face": 1, "nodes": ids,
            "coords": [(x, y, 0.0) for x, y in pts], "centre": (cx, cy, -0.1)}
# two unit squares; the right one has its own nodes on the shared edge, 1e-5
# (relative 5e-6 of the size) away from the left one's
d = 1e-5
faces = [quad(1, [1, 2, 3, 4], [(0, 0), (1, 0), (1, 1), (0, 1)]),
         quad(2, [12, 5, 6, 13], [(1 + d, 0), (2, 0), (2, 1), (1 + d, 1)])]
loops, heal = smw.boundary_loops(faces, smw.selection_plane(faces))
check("duplicate nodes welded: one loop, area 2", len(loops) == 1 and
      abs(abs(area(loops[0])) - 2.0) < 1e-4 and heal["welded"] == 2)
# T-joint: a tall square on the left, two squares on the right; node (1, 1)
# of the right ones lies on the left one's edge
faces = [quad(1, [1, 2, 3, 4], [(0, 0), (1, 0), (1, 2), (0, 2)]),
         quad(2, [2, 5, 6, 7], [(1, 0), (2, 0), (2, 1), (1, 1)]),
         quad(3, [7, 6, 8, 3], [(1, 1), (2, 1), (2, 2), (1, 2)])]
loops, heal = smw.boundary_loops(faces, smw.selection_plane(faces))
check("T-joint split: one loop, area 4", len(loops) == 1 and
      abs(abs(area(loops[0])) - 4.0) < 1e-12 and heal["split"] == 1)
check("nothing to repair in a proper mesh", heal["welded"] == 0 and
      heal["gaps_closed"] == [])
# a real slit (two squares 0.1 apart) stays: two loops, no gap closed
faces = [quad(1, [1, 2, 3, 4], [(0, 0), (1, 0), (1, 1), (0, 1)]),
         quad(2, [5, 6, 7, 8], [(1.1, 0), (2.1, 0), (2.1, 1), (1.1, 1)])]
loops, heal = smw.boundary_loops(faces, smw.selection_plane(faces))
check("a real slit is kept", len(loops) == 2 and heal["gaps_closed"] == [])

# --- almost planar: straightened; curved: error -------------------------------
# (Mecway GUI test 24 Oct 2026: 0.0002 mm out of plane on a 30 mm section)
faces = grid_faces(2, 1, 0.1, 0.05, 0.0)
faces[1]["coords"][1] = (0.1, 0.0, 2e-7)
plane = smw.selection_plane(faces)
loops, heal = smw.boundary_loops(faces, plane)
check("2e-7 m out of plane: straightened, deviation reported",
      0.0 < plane["deviation"] < 2e-7 and len(loops) == 1 and
      abs(abs(area(loops[0])) - 0.005) < 1e-9)


class FakeMw(object):
    pass


job, plane = smw.section_input(FakeMw(), faces, "mesh", "fine")
check("job: flattened in heal, accuracy fine = 10000 elements",
      job["heal"].get("flattened") == plane["deviation"] and
      job["n_target"] == 10000 and job["accuracy"] == "fine")
job, _ = smw.section_input(FakeMw(), grid_faces(2, 1, 0.1, 0.05, 0.0), "mesh",
                           "nonsense")
check("flat faces: nothing flattened; unknown accuracy -> normal",
      "flattened" not in job["heal"] and job["n_target"] == 3000)
faces[1]["coords"][1] = (0.1, 0.0, 0.005)
try:
    smw.selection_plane(faces)
    check("curved (4% of the size) -> ValueError", False)
except ValueError:
    check("curved (4% of the size) -> ValueError", True)
try:
    smw.selection_plane([])
    check("no faces -> ValueError", False)
except ValueError:
    check("no faces -> ValueError", True)

# --- temporary faces of a STEP without a mesh ------------------------------


class Vec(object):
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class Fid(object):
    def __init__(self, eid, face):
        self.element_id = eid
        self.face_number = face


class StepMw(object):
    """Model as Mecway 35 gives it: no elements, generate_mesh is not used,
    the selection is what the user clicked."""

    def __init__(self, path=None):
        self.path = path
        self.comps = ["Default"]
        self.elements = {}
        self.owner = {}
        self.pts = {}
        self.sel_faces = []
        self.sel_elements = []

    def generate_mesh(self):
        raise AssertionError("the whole model must not be meshed")

    def new_component(self, name):
        self.comps.append(name)
        return name

    def new_node(self, p):
        n = max(list(self.pts) + [100]) + 1
        self.pts[n] = p
        return n

    def new_element(self, shape, nodes, comp):
        assert shape == "tri3"
        e = max(list(self.elements) + [0]) + 1
        self.elements[e] = list(nodes)
        self.owner[e] = comp
        return e

    def components(self):
        return list(self.comps)

    def all_elements(self):
        return sorted(self.elements)

    def all_nodes(self):
        return sorted(self.pts)

    def nodes(self, eid):
        return list(self.elements[eid])

    def node(self, n):
        return self.pts[n]

    def element_component(self, eid):
        return self.owner[eid]

    def component_elements(self, comp):
        return [e for e in sorted(self.elements) if self.owner[e] == comp]

    def selected_faces(self):
        return list(self.sel_faces)

    def selected_elements(self):
        return list(self.sel_elements)

    def delete_elements(self, ids):
        for e in ids:
            del self.elements[e]
            del self.owner[e]

    def delete_nodes(self, ids):
        for n in ids:
            del self.pts[n]

    def delete_component(self, name):
        self.comps.remove(name)

    def file_name(self):
        return self.path

    def set_model_active(self):
        pass

    def display(self):
        pass


def listed(file_name, occurrence, face, z):
    """One face as section_analysis.list_faces gives it: a 0.1 m square at
    height z, two triangles counter-clockwise about +Z."""
    return {"file": file_name, "occurrence": occurrence, "face": face,
            "normal": [0.0, 0.0, 1.0], "offset": z,
            "points": [[0.0, 0.0, z], [0.1, 0.0, z], [0.1, 0.1, z],
                       [0.0, 0.1, z]],
            "triangles": [[0, 1, 2], [0, 2, 3]]}


smw.Vector = Vec
mw = StepMw()
state = smw.prepare(mw, "cad")
check("no mesh, not saved: the STEP file of the model is asked",
      state["state"] == "step" and state["component"] is None)
state = smw.prepare(mw, "cad", "normal", None, {"": __file__})
check("file known: list its faces, nothing is meshed",
      state["state"] == "list" and state["paths"] == [__file__])
temp = smw.build_temp_faces(mw, [listed("a.step", 2, 41, 0.04),
                                 listed("a.step", 2, 42, 0.04),
                                 listed("a.step", 0, 77, 0.09)])
check("temporary faces: 6 tri3 in one component of their own",
      len(mw.elements) == 6 and mw.comps[-1] == smw.TEMP_COMPONENT)
state = smw.prepare(mw, "cad", "normal", temp)
check("nothing clicked yet: wait for the pick", state["state"] == "pick")
mw.sel_faces = [Fid(2, 1)]
state = smw.prepare(mw, "mesh", "normal", temp)
step = state["job"]["step"]
check("face mode: the known STEP face, whatever the Input choice",
      state["state"] == "ready" and step["hint"] == {"hits": [[2, [41]]]} and
      step["file"] == "a.step" and
      state["job"]["heal"] == {"temp_mesh": True})
check("plane from the triangles: normal +Z (outward), offset 0.04",
      abs(state["plane"]["normal"][2] - 1.0) < 1e-12 and
      abs(state["plane"]["offset"] - 0.04) < 1e-12 and
      abs(state["plane"]["deviation"]) < 1e-12)
mw.sel_faces = []
mw.sel_elements = [5]
state = smw.prepare(mw, "cad", "normal", temp)
check("element mode works too",
      state["job"]["step"]["hint"] == {"hits": [[0, [77]]]})
mw.sel_elements = [1, 3]
state = smw.prepare(mw, "cad", "normal", temp)
check("two faces of one part in one plane",
      state["job"]["step"]["hint"] == {"hits": [[2, [41, 42]]]})
mw.sel_elements = [1, 5]
try:
    smw.prepare(mw, "cad", "normal", temp)
    check("faces in two planes -> ValueError", False)
except ValueError:
    check("faces in two planes -> ValueError", True)
temp["faces"][1]["file"] = "b.step"
mw.sel_elements = [1, 3]
try:
    smw.prepare(mw, "cad", "normal", temp)
    check("faces of two files -> ValueError", False)
except ValueError:
    check("faces of two files -> ValueError", True)

temp["faces"][1]["file"] = "a.step"

mw.pts[1] = Vec(0.0, 0.0, 1.0)      # the user's own node, not used
temp["nodes_before"].add(1)
mw.elements[99] = [1]
mw.owner[99] = "mine"
mw.comps.append("mine")
smw.discard_temp_mesh(mw, temp)
check("temporary faces removed, nothing else",
      sorted(mw.elements) == [99] and sorted(mw.pts) == [1] and
      mw.comps == ["Default", "mine"])
state = smw.prepare(StepMw(), "cad", "normal", temp, {"": __file__})
check("temporary faces that are gone: listed again",
      state["state"] == "list" and state["temp"] is None)

mw = StepMw()
temp = smw.build_temp_faces(mw, [listed("a.step", 0, 1, 0.0)])
own = mw.new_node(Vec(1.0, 2.0, 3.0))
mesh = [mw.new_node(Vec(0.1 * (k == 1), 0.1 * (k == 2), 0.5)) for k in range(3)]
mw.comps.append("mine")
mine = mw.new_element("tri3", mesh, "mine")
mw.face_nodes = lambda fid: mesh
mw.sel_faces = [Fid(mine, 1)]
state = smw.prepare(mw, "mesh", "normal", temp)
check("own mesh made meanwhile: the temporary faces go, its face is used",
      state["state"] == "ready" and state["temp"] is None and
      sorted(mw.elements) == [mine] and smw.TEMP_COMPONENT not in mw.comps)
mw = StepMw()


class Broken(StepMw):
    def new_element(self, shape, nodes, comp):
        if len(self.elements) == 3:
            raise Exception("refused")
        return StepMw.new_element(self, shape, nodes, comp)


broken = Broken()
try:
    smw.build_temp_faces(broken, [listed("a.step", 0, 1, 0.0),
                                  listed("a.step", 0, 2, 0.1)])
    check("failure while building: nothing stays behind", False)
except Exception:
    check("failure while building: nothing stays behind",
          not broken.elements and not broken.pts and
          broken.comps == ["Default"])
smw.build_temp_faces(mw, [listed("a.step", 0, 1, 0.0)])
own = mw.new_node(Vec(1.0, 1.0, 1.0))
check("left-over component is removed at the next start, own node stays",
      smw.remove_stale_faces(mw) and not mw.elements and
      sorted(mw.pts) == [own] and mw.comps == ["Default"] and
      not smw.remove_stale_faces(mw))

folder = tempfile.mkdtemp()
try:
    liml = os.path.join(folder, "model.liml")
    step = os.path.join(folder, "part.step")
    for name, text in ((step, u"x"), (liml, u'<liml version="35">\n'
                        u'<geometry id="1" filename="part.step">\n'
                        u'<geometry id="2" filename="gone.step">\n'
                        u'<elset name="Default" />\n</liml>\n')):
        with io.open(name, "w", encoding="utf-8") as f:
            f.write(text)
    mw = StepMw(liml)
    state = smw.prepare(mw, "cad")
    check("saved: the existing STEP files of the .liml, no question",
          state["state"] == "list" and len(state["paths"]) == 1 and
          os.path.normcase(state["paths"][0]) == os.path.normcase(step))
    other = os.path.join(folder, "assembly.liml")
    with io.open(other, "w", encoding="utf-8") as f:
        f.write(u'<assembly filename="part.step" source="step">\n'
                u'<geometry id="1" colorrgb="637F61">\n</geometry>\n'
                u'<geometry id="2" colorrgb="5869D9">\n</geometry>\n'
                u'</assembly>\n<geometry id="3" filename="b.step">\n'
                u'<elset name="PART(2)" geomid="2">\n')
    geoms, comps = smw.liml_geometries(other)
    with io.open(os.path.join(folder, "b.step"), "w", encoding="utf-8") as f:
        f.write(u"x")
    check("assembly in the .liml: each file is listed once",
          [os.path.basename(x) for x in
           smw.model_step_files(StepMw(other))] == ["b.step", "part.step"])
    check("assembly in the .liml: instances share the file, others not",
          os.path.basename(geoms["1"]) == "part.step" and
          geoms["1"] == geoms["2"] and
          os.path.basename(geoms["3"]) == "b.step" and
          comps == {"PART(2)": "2"})
    plate = [{"eid": 1, "face": 1, "nodes": [1, 2, 3],
              "coords": [(0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.0, 0.1, 0.0)],
              "centre": (0.03, 0.03, -0.1)}]
    mw.owner[1] = "part"
    plane = smw.selection_plane(plate)
    block = smw.step_request(mw, plate, plane, {"part": "other.step"})
    check("own mesh: the link of the .liml wins over a remembered file",
          os.path.normcase(block["file"]) == os.path.normcase(step))
finally:
    shutil.rmtree(folder)

mw = StepMw()
for k in range(3):
    mw.new_node(Vec(0.1 * (k == 1), 0.1 * (k == 2), 0.0))
mw.new_element("tri3", [101, 102, 103], "part")
mw.comps.append("part")
try:
    smw.prepare(mw, "mesh")
    check("own mesh, no selection -> ValueError, mesh untouched", False)
except ValueError:
    check("own mesh, no selection -> ValueError, mesh untouched",
          len(mw.elements) == 1)
mw.sel_faces = [Fid(1, 1)]
mw.face_nodes = lambda fid: [101, 102, 103]
state = smw.prepare(mw, "cad", "normal", None, {"part": __file__})
check("own mesh, CAD: the mesh boundary goes along as fallback",
      state["state"] == "ready" and state["temp"] is None and
      len(state["job"]["fallback_loops"]) == 1)

# --- the prerequisite: Python with numpy and scipy --------------------------
su = section_utils
su.save_setting = lambda key, value: None         # no write in a test
values = su.settings()
values["python"] = u"C:\\does\\not\\exist\\python.exe"
found = su.find_python()
check("Python of the settings missing: said so, nothing else is tried",
      found["path"] is None and found["pip"] is None and found["own"] and
      "does" in smw.missing_python_text(found))
values["python"] = ""
text = smw.missing_python_text({"path": None, "pip": u"C:\\Py\\python.exe",
                                "own": ""})
check("Python without the packages: the pip command and the question",
      u'"C:\\Py\\python.exe" -m pip install numpy scipy' in text and
      text.rstrip().endswith("?"))
text = smw.missing_python_text({"path": None, "pip": None, "own": ""})
check("no Python: where to get it, no question",
      "python.org" in text and not text.rstrip().endswith("?"))
check("pip is never offered for a missing file",
      su.check_python(u"C:\\does\\not\\exist\\python.exe") ==
      (False, "no_run"))
for path in su._aster_pythons():
    ok, why = su.check_python(path)
    if "Python37" in path:
        check("old Python of Code-Aster refused ({0})".format(why), not ok)
    elif "Python311" in path:
        check("Python of Code-Aster accepted ({0})".format(why), ok)

# --- the #ASTER-SECTIE line -------------------------------------------------
res = {"area": 1.8e-05, "i11_c": 1.35e-09, "i22_c": 5.4e-13,
       "j": 2.16e-12, "perimeter": 0.0136, "centroid": [0.0, 0.0],
       "phi_deg": 0.0, "loops": [[[-0.0015, -0.003], [0.0015, -0.003],
                                  [0.0015, 0.003], [-0.0015, 0.003]]],
       "aster": {"A": 1.8e-05, "IY": 1.35e-09, "IZ": 5.4e-13,
                 "JX": 2.16e-12, "AY": 1.2, "AZ": 1.2, "EY": 0.0,
                 "EZ": 0.0, "RY": 0.003, "RZ": 0.0015, "RT": 0.0015,
                 "JG": 1e-18, "IYR2": 0.0, "IZR2": 0.0}}
line = smw.aster_line(u"Plat 3x6", res)
check("line starts with '** ASTER-SECTIE Plat 3x6: A='",
      line.startswith(u"** ASTER-SECTIE Plat 3x6: A=1.8e-05, IY="))
py, pz = smw.recovery_point(res)
check("stress recovery point at a corner",
      abs(abs(py) - 0.0015) < 1e-12 and abs(abs(pz) - 0.003) < 1e-12)
values = dict(smw.general_section_values(res))
check("iyy = I11, izz = I22", values["iyy"] == 1.35e-09 and
      values["izz"] == 5.4e-13)

snippet = smw.aster_line_liml(line.replace(u"Plat 3x6", u"A&B"))
check("import .liml: one custom model definition, name escaped",
      snippet.count(u"<ccxmodeldefinition>") == 1 and
      u"** ASTER-SECTIE A&amp;B: A=" in snippet)

# The format MecwayAsterBridge reads (bridge_from_liml._section_extras
# there): '** ASTER-SECTIE <material>: KEY=float, ...', keys A, IY, IZ, JX
# (checked against the material) and the extra ones; SI values.
import re  # noqa: E402
m = re.match(r"^\*\* ASTER-SECTIE (.+): (.*)$", line)
pairs = dict((k.strip(), float(v)) for k, v in
             (p.split("=") for p in m.group(2).split(","))) if m else {}
check("line grammar: material and KEY=float pairs",
      m is not None and m.group(1) == u"Plat 3x6" and
      set(smw.ASTER_KEYS) == set(pairs) and pairs["AY"] == 1.2 and
      pairs["IY"] == 1.35e-09 and pairs["A"] == 1.8e-05)

# --- the SECTIE-VORM lines ---------------------------------------------------
def read_shape(lines, material):
    """The reader of the contract in AGENTS.md (bridge_section_view there)."""
    head = u"** SECTIE-VORM {0}: ".format(material)
    counts, area, numbers = None, None, []
    for text in lines:
        if not text.startswith(head):
            raise ValueError(text)
        body = text[len(head):]
        if body.startswith(u"N="):
            left, right = body[2:].split(u", A=")
            counts = [int(n) for n in left.split()]
            area, numbers = float(right), []
        else:
            numbers += [float(n) for n in body[2:].split()]
    pts = list(zip(numbers[0::2], numbers[1::2]))
    if len(pts) != sum(counts):
        raise ValueError("count")
    loops, at = [], 0
    for n in counts:
        loops.append(pts[at:at + n])
        at += n
    return loops, area


lines = smw.shape_lines(u"Plat 3x6", res)
loops, shape_area = read_shape(lines, u"Plat 3x6")
check("outline: one loop of 4 points and the area",
      [len(lp) for lp in loops] == [4] and shape_area == 1.8e-05)
check("outline: not an ASTER-SECTIE line (the bridge would report it)",
      not any(t.startswith(smw.LINE_PREFIX) for t in lines))
check("outline: area of the rectangle", abs(abs(area(loops[0])) - 1.8e-05)
      < 1e-12)

# rotated and shifted L: V, W are principal, about the centroid; one point
# on the far corner, and the handedness (x, y) -> (V, W) is kept
phi = 30.0
c30, s30 = math.cos(math.radians(phi)), math.sin(math.radians(phi))


def placed(v, w):
    return [0.5 + v * c30 - w * s30, 0.25 + v * s30 + w * c30]


ell = [(0.0, 0.0), (0.06, 0.0), (0.06, 0.006), (0.006, 0.006), (0.006, 0.04),
       (0.0, 0.04)]
res_l = dict(res, centroid=[0.5, 0.25], phi_deg=phi,
             loops=[[placed(v, w) for v, w in ell]])
got = read_shape(smw.shape_lines(u"L", res_l), u"L")[0][0]
check("outline: rotation and centroid removed, same order",
      len(got) == 6 and all(abs(a[0] - b[0]) < 1e-4 and abs(a[1] - b[1]) < 1e-4
                            for a, b in zip(got, ell)))
check("outline: sign of the area kept (no mirror image)",
      area(got) * area(ell) > 0.0)

# a tube of 2 x 720 points: limits, line length, the hole stays a hole
circle = [[math.cos(math.radians(a * 0.5)), math.sin(math.radians(a * 0.5))]
          for a in range(720)]
ring = [[[0.05 * x, 0.05 * y] for x, y in circle],
        [[0.04 * x, 0.04 * y] for x, y in circle[::-1]]]
res_t = dict(res, loops=ring, centroid=[0.0, 0.0], phi_deg=0.0)
lines = smw.shape_lines(u"Buis", res_t)
loops, _ = read_shape(lines, u"Buis")
check("outline: limits per loop and in total",
      len(loops) == 2 and all(3 <= len(lp) <= smw.SHAPE_POINTS for lp in loops)
      and sum(len(lp) for lp in loops) <= smw.SHAPE_TOTAL)
check("outline: lines fit", max(len(t) for t in lines) <= smw.SHAPE_LINE)
exact = math.pi * (0.05 ** 2 - 0.04 ** 2)
check("outline: area of the tube within 3%",
      abs(abs(area(loops[0])) - abs(area(loops[1])) - exact) < 0.03 * exact)

# a hole far below the tolerance goes; nothing but one point for no loops
speck = [[1e-6 * x, 1e-6 * y] for x, y in circle[::120]]
res_s = dict(res, loops=res["loops"] + [speck])
check("outline: a speck of a hole is left out",
      len(smw.shape_loops(res_s)) == 1)
check("outline: no loops, no lines", smw.shape_lines(u"X", dict(res, loops=[]))
      == [])
text = smw.aster_line_liml(u"\n".join([line] + lines))
check("import .liml: ASTER line and outline in one definition",
      text.count(u"<ccxmodeldefinition>") == 1 and u"\n** SECTIE-VORM Buis: N="
      in text)

# --- the beam: V axis, direction, mirrored data ------------------------------
class BeamMw(object):
    """Beams as Mecway 35 gives them. import_file behaves as measured: a card
    comes in on its own selection, renamed when the name is taken; a card
    without that selection in the same file would lose its selection."""

    def __init__(self, ends, path=None):
        self.ends = ends
        self.path = path
        self.selections = {}
        self.cards = []
        self.imported = []
        self.props = {}
        self.assigned = {}

    def component_elements(self, comp):
        return sorted(self.ends)

    def element_shape(self, eid):
        return "line2"

    def nodes(self, eid):
        return [2 * eid, 2 * eid + 1]

    def node(self, n):
        p = self.ends[n // 2][n % 2]
        return Vec(p[0], p[1], p[2])

    def named_selections(self):
        return list(self.selections)

    def named_selection(self, name):
        return list(self.selections[name])

    def add_to_named_selection(self, name, e):
        self.selections[name].append(e)

    def remove_from_named_selection(self, name, e):
        self.selections[name].remove(e)

    def file_name(self):
        return self.path

    def version(self):
        return "35.0.9802"

    def new_material(self, name):
        return name

    def set_material_type(self, mat, group, kind):
        pass

    def set_material_property(self, mat, prop, value):
        self.props[prop] = value

    def set_material(self, comp, mat):
        self.assigned[comp] = mat

    def import_file(self, path, unit):
        assert unit == "m"
        text = io.open(path, encoding="utf-8").read()
        self.imported.append(text)
        if u"<orientation " in text:
            assert u"<elementselection " in text
            name = text.split(u'<elementselection name="')[1].split(u'"')[0]
            while name in self.selections:
                name += u"(2)"
            self.selections[name] = []
            self.cards.append(name)


a45 = 2.0 ** -0.5
beam_plane = {"normal": (0.0, 0.0, 1.0), "u": (1.0, 0.0, 0.0),
              "v": (0.0, 1.0, 0.0)}
res_b = dict(res, phi_deg=45.0, centroid=[0.0, 0.0], perimeter=0.3, j=1e-9,
             loops=[[(0.06, 0.0), (0.0, 0.06), (0.0, 0.0)]],
             aster=dict(res["aster"], EY=0.02, EZ=0.01, IYR2=2e-8, IZR2=3e-8))
up = {1: ((0, 0, 0), (0, 0, 0.5)), 2: ((0, 0, 0.5), (0, 0, 1.0))}
down = {1: ((0, 0, 1.0), (0, 0, 0.5)), 2: ((0, 0, 0.5), (0, 0, 0))}
mixed = {1: up[1], 2: down[2]}
skew = {1: ((0, 0, 0), (0.1, 0, 1.0))}

v_axis = smw.principal_axis(res_b, beam_plane)
check("V axis: phi 45 about +Z is (0.707, 0.707, 0)",
      abs(v_axis[0] - a45) < 1e-12 and abs(v_axis[1] - a45) < 1e-12)
check("default V as in the manual: Y along Z, Z x U otherwise",
      smw.default_v((0.0, 0.0, 1.0)) == (0.0, 1.0, 0.0) and
      smw.default_v((1.0, 0.0, 0.0)) == (0.0, 1.0, 0.0) and
      smw.default_v((0.0, 1.0, 0.0)) == (-1.0, 0.0, 0.0))
count = smw.beam_directions(smw.beam_axes(BeamMw(mixed), "B"), (0, 0, 1.0))
check("beam directions: one along, one against",
      count["along"] == 1 and count["against"] == 1 and count["skew"] == 0)

work = tempfile.mkdtemp()
try:
    section_utils.WORK_DIR = work
    smw.work_folder = lambda: work

    mw = BeamMw(up)
    plan = smw.beam_plan(mw, res_b, beam_plane, "B", True)
    check("beams along n at 45 degrees: a card on both, unsaved model noted",
          plan["card"] == [1, 2] and not plan["mirrored"] and
          len(plan["notes"]) == 1)
    mat, sel, notes = smw.assign_section(mw, u"P", res_b, beam_plane, "B")
    check("assign: one import with lines, card and selection, filled",
          len(mw.imported) == 1 and sel == u"SECTION_V_P" and
          mw.selections[sel] == [1, 2] and mw.cards == [sel] and
          mw.imported[0].count(u"<ccxmodeldefinition>") == 1)
    text = mw.imported[0]
    check("assign: card holds the V vector and all seven children",
          all(u"<{0}>".format(t) in text for t in
              ("ux", "uy", "uz", "vx", "vy", "vz", "angleu")) and
          u"<vx>0.707106781186548</vx>" in text.replace(
              u"0.7071067811865476", u"0.707106781186548"))
    line = [t for t in text.split(u"\n") if u"SECTIE-RICHTING" in t][0]
    check("direction line as in the contract",
          line.startswith(u"** SECTIE-RICHTING P: V=0.707107 0.707107 0, U=0 "
                          u"0 1") and
          not line.startswith(smw.LINE_PREFIX))

    mat, sel2, notes = smw.assign_section(mw, u"P", res_b, beam_plane, "B")
    check("assign again: the old selection is emptied and stays, so that no "
          "element has two cards and no card loses its selection",
          sel2 != sel and mw.selections[sel] == [] and
          mw.selections[sel2] == [1, 2] and len(mw.cards) == 2)

    mw = BeamMw(up)
    plain = dict(res_b, phi_deg=90.0)
    plan = smw.beam_plan(mw, plain, beam_plane, "B", True)
    check("default V already axis 1: no card", plan["card"] is None)
    rect = dict(res_b, phi_deg=-90.0,
                aster=dict(res_b["aster"], EY=0.0, EZ=0.0, IYR2=0.0, IZR2=0.0))
    plan = smw.beam_plan(BeamMw(up), rect, beam_plane, "B", True)
    check("default V is -axis 1 of a symmetric section: no card",
          plan["card"] is None)
    plan = smw.beam_plan(BeamMw(up), plain.__class__(res_b, phi_deg=-90.0),
                         beam_plane, "B", True)
    check("default V is -axis 1 of an open section: a card",
          plan["card"] == [1, 2])

    # The same symmetric section without a card: the beams keep Mecway's
    # default V = -axis 1, so the lines must be written for that V, or the
    # bridge and the beam analysis report the beam turned 180 degrees.
    def direction(text):
        """(V, U) of the SECTIE-RICHTING line in text."""
        line = [t for t in text.splitlines() if u"SECTIE-RICHTING" in t][0]
        v, u = line.split(u": ", 1)[1].split(u"<")[0].split(u", ")
        return ([float(x) for x in v[2:].split()],
                [float(x) for x in u[2:].split()])

    def near(a, b):
        return max(abs(x - y) for x, y in zip(a, b)) < 1e-12

    mw = BeamMw(up)
    mat, sel, notes = smw.assign_section(mw, u"R", rect, beam_plane, "B")
    text = mw.imported[0]
    turned = smw.for_beam(rect, False, True)
    got_v, got_u = direction(text)
    check("symmetric section without a card: the line gives the default V",
          sel is None and mw.cards == [] and near(got_v, (0, 1, 0)) and
          near(got_u, (0, 0, 1)))
    check("... and the outline is written for that V (turned 180 degrees)",
          all(t in text for t in smw.shape_lines(mat, turned)) and
          not all(t in text for t in smw.shape_lines(mat, rect)))
    plain_pt = smw.recovery_point(rect)
    turned_pt = smw.recovery_point(turned)
    check("... the recovery point too",
          abs(turned_pt[0] + plain_pt[0]) < 1e-12 and
          abs(turned_pt[1] + plain_pt[1]) < 1e-12 and
          abs(mw.props["pointy"] - turned_pt[0]) < 1e-12 and
          abs(mw.props["pointz"] - turned_pt[1]) < 1e-12)
    check("... and the results of the window are not changed",
          "turn_v" not in rect and "mirror_w" not in rect)
    plan = smw.beam_plan(BeamMw(up), rect, beam_plane, "B", False)
    check("box off, symmetric section: the default V, only the unsaved note",
          near(plan["v"], (0, 1, 0)) and plan["turned"] and
          len(plan["notes"]) == 1 and
          (u"opgeslagen" in plan["notes"][0] or u"saved" in plan["notes"][0]))
    mw = BeamMw(down)
    smw.assign_section(mw, u"R", rect, beam_plane, "B")
    got_v, got_u = direction(mw.imported[0])
    check("beam against n, default V = -axis 1: V of the beam, U reversed",
          near(got_v, (0, 1, 0)) and near(got_u, (0, 0, -1)) and
          not mw.cards)
    # Values of the line: a turn about U reverses V and W (EY, EZ, IYR2 and
    # IZR2), a mirror in W reverses W only (EZ, IYR2).
    def values(data):
        line = smw.aster_line(u"P", data)
        return dict((k, float(x)) for k, x in
                    (p.split(u"=") for p in line.split(u": ", 1)[1]
                     .split(u", ")))
    got = values(smw.for_beam(res_b, False, True))
    check("turned: EY, EZ, IYR2 and IZR2 reversed",
          (got["EY"], got["EZ"], got["IYR2"], got["IZR2"]) ==
          (-0.02, -0.01, -2e-08, -3e-08))
    got = values(smw.for_beam(res_b, True, True))
    check("turned and mirrored: EY and IZR2 reversed, EZ and IYR2 not",
          (got["EY"], got["EZ"], got["IYR2"], got["IZR2"]) ==
          (-0.02, 0.01, 2e-08, -3e-08))
    # One beam exactly along Z (default V = +Y) and one tilted 0.6 degrees to
    # -X (default V = Z x U = -Y): no V fits both.
    split = {1: up[1], 2: ((0, 0, 0), (-0.01, 0, 1.0))}
    plan = smw.beam_plan(BeamMw(split), rect, beam_plane, "B", True)
    check("default Vs opposite on beams of one direction: a card",
          plan["card"] == [1, 2] and plan["v"] == smw.principal_axis(
              rect, beam_plane))
    plan = smw.beam_plan(BeamMw(split), rect, beam_plane, "B", False)
    check("... box off: axis 1 and a note with the V vector",
          plan["card"] is None and not plan.get("turned") and
          len(plan["notes"]) == 1 and u"−Y" in plan["notes"][0])
    # Beams along +X and -X: the default V reverses with U, so the minority
    # would keep the opposite V. A card gives all of them axis 1.
    x_plane = {"normal": (1.0, 0.0, 0.0), "u": (0.0, 1.0, 0.0),
               "v": (0.0, 0.0, 1.0)}
    x_rect = dict(rect, phi_deg=180.0)
    both_x = {1: ((0, 0, 0), (0.5, 0, 0)), 2: ((0.5, 0, 0), (1.0, 0, 0)),
              3: ((2.0, 0, 0), (1.5, 0, 0))}
    plan = smw.beam_plan(BeamMw(both_x), x_rect, x_plane, "B", True)
    check("symmetric section on beams in both senses along X: a card",
          plan["card"] == [1, 2, 3] and not plan["turned"])
    # Box off after an earlier assignment with the box on: the tool's own
    # card still gives the beams axis 1, so the lines stay for axis 1.
    mw = BeamMw(up)
    mw.selections[u"SECTION_V_R"] = [1, 2]
    plan = smw.beam_plan(mw, rect, beam_plane, "B", False)
    check("box off, beams still on an earlier card of the tool: axis 1",
          not plan["turned"] and
          plan["v"] == smw.principal_axis(rect, beam_plane) and
          mw.selections[u"SECTION_V_R"] == [1, 2])

    # T (flange 60x10, stem 10x150), symmetric about W only, on a beam
    # along +Y: Mecway's default V is -X, axis 1 is +X. -V also reverses
    # W = U x V, so the section would be turned 180 degrees (EY, EZ, IYR2
    # and IZR2 all odd): a card, and the data as they are.
    tee = dict(res_b, area=0.0021, i11_c=5.560357142857e-06,
               i22_c=1.925e-07, j=6.979468739776e-08, phi_deg=0.0,
               perimeter=0.44, centroid=[0.0, 0.09785714285714],
               loops=[[[-0.005, 0.0], [0.005, 0.0], [0.005, 0.15],
                       [0.03, 0.15], [0.03, 0.16], [-0.03, 0.16],
                       [-0.03, 0.15], [-0.005, 0.15]]],
               aster=dict(res_b["aster"], EY=0.0, EZ=-0.0513842027,
                          IYR2=-8.795918367e-08, IZR2=0.0))
    tee_plane = {"normal": (0.0, 1.0, 0.0), "u": (1.0, 0.0, 0.0),
                 "v": (0.0, 0.0, -1.0)}
    along_y = {1: ((0, 0, 0), (0, 0.5, 0)), 2: ((0, 0.5, 0), (0, 1.0, 0))}
    beams_y = smw.beam_axes(BeamMw(along_y), "B")
    check("T on a beam along +Y: default V is -axis 1, turned 180 degrees",
          smw.principal_axis(tee, tee_plane) == (1.0, 0.0, 0.0) and
          abs(smw.worst_turn(tee, beams_y, (1.0, 0.0, 0.0)) - 180.0) < 1e-9)
    plan = smw.beam_plan(BeamMw(along_y), tee, tee_plane, "B", True)
    check("T symmetric about W only, default V = -V: a card",
          plan["card"] == [1, 2] and not plan["mirrored"])
    mw = BeamMw(along_y)
    mat, sel, notes = smw.assign_section(mw, u"T", tee, tee_plane, "B")
    text = mw.imported[0]
    line = [t for t in text.split(u"\n") if smw.LINE_PREFIX in t][0]
    vals = dict(p.split(u"=") for p in line.split(u": ", 1)[1].split(u", "))
    check("T: card with V = +X, data stored as they are",
          sel and mw.selections[sel] == [1, 2] and
          u"<vx>1</vx><vy>0</vy><vz>0</vz>" in text and
          u"V=1 0 0, U=0 1 0" in text and
          float(vals[u"EZ"]) == -0.0513842027 and
          float(vals[u"IYR2"]) == -8.795918367e-08)
    plan = smw.beam_plan(BeamMw(along_y), tee, tee_plane, "B", False)
    check("T, box off: a note with the 180 degrees",
          plan["card"] is None and
          any(u"180.0" in n for n in plan["notes"]))

    mw = BeamMw(down)
    mat, sel, notes = smw.assign_section(mw, u"P", res_b, beam_plane, "B")
    text = mw.imported[0]
    plain_line = smw.aster_line(u"P", res_b)
    check("beam against n: data mirrored, U reversed, V the same",
          u"U=0 0 -1" in text and
          u"V=0.707107 0.707107" in text and u"EZ=-0.01" in text and
          u"IYR2=-2e-08" in text and u"IZR2=3e-08" in text and
          u"EY=0.02" in text and u"EZ=0.01" in plain_line and
          any(u"tegen de normaal" in n or u"against the normal" in n
              for n in notes))
    same = smw.recovery_point(res_b)
    mirror = smw.recovery_point(smw.for_beam(res_b, True))
    check("beam against n: recovery point mirrored in W",
          abs(mirror[0] - same[0]) < 1e-12 and abs(mirror[1] + same[1]) < 1e-12)
    check("the results of the window are not changed", "mirror_w" not in res_b)

    plan = smw.beam_plan(BeamMw(mixed), res_b, beam_plane, "B", True)
    check("mixed directions, not symmetric about V: card plus a note",
          plan["card"] == [1, 2] and not plan["mirrored"] and
          len(plan["notes"]) == 2)
    even = dict(res_b, aster=dict(res_b["aster"], EZ=0.0, IYR2=0.0))
    plan = smw.beam_plan(BeamMw(mixed), even, beam_plane, "B", True)
    check("mixed directions, symmetric about V: no note about it",
          len(plan["notes"]) == 1)

    plan = smw.beam_plan(BeamMw(skew), res_b, beam_plane, "B", True)
    check("skew beam: no card, the angle and vector in a note",
          plan["card"] is None and u"5.7" in plan["notes"][0] and
          u"0.707" in plan["notes"][0])
    plan = smw.beam_plan(BeamMw(up), res_b, beam_plane, "B", False)
    check("box off: no card, a note with the 45 degrees",
          plan["card"] is None and u"45.0" in plan["notes"][0])
    plan = smw.beam_plan(BeamMw(up), res_b, beam_plane, None, True)
    check("no component: no card, no notes",
          plan["card"] is None and plan["notes"] == [])

    mw = BeamMw(up)
    smw.assign_section(mw, u"P", res_b, beam_plane, None, store=False)
    check("nothing to import: no import", mw.imported == [])
    mw = BeamMw(up)
    mat, sel, _ = smw.assign_section(mw, u"P", res_b, beam_plane, "B",
                                     store=False)
    check("store off: only the card, no custom definition",
          u"ccxmodeldefinition" not in mw.imported[0] and sel)

    saved = os.path.join(work, "saved.liml")

    def write_model(body):
        with io.open(saved, "w", encoding="utf-8") as f:
            f.write(u'<liml version="35">\n' + body + u"\n</liml>\n")

    write_model(u'<elem eid="2" shape="line2" nodes="1 2" orientationvx="1" '
                u'orientationvy="0" orientationvz="0" />')
    plan = smw.beam_plan(BeamMw(up, saved), res_b, beam_plane, "B", True)
    check("saved model: attributes on a beam, no card and a note",
          plan["card"] is None and len(plan["notes"]) == 1 and
          smw.foreign_orientation(BeamMw(up, saved), [1, 2]) == 1)
    plan = smw.beam_plan(BeamMw(up, saved), rect, beam_plane, "B", False)
    check("box off, an own orientation in the saved model: axis 1 is kept",
          not plan["turned"] and
          plan["v"] == smw.principal_axis(rect, beam_plane))
    write_model(u'<orientation selection="Mine">\n</orientation>')
    mw = BeamMw(up, saved)
    mw.selections[u"Mine"] = [1]
    check("saved model: a card of the user on a beam counts",
          smw.foreign_orientation(mw, [1, 2]) == 1)
    write_model(u'<orientation selection="SECTION_V_P">\n</orientation>\n'
                u'<orientation selection="">\n</orientation>')
    mw = BeamMw(up, saved)
    mw.selections[u"SECTION_V_P"] = [1, 2]
    check("saved model: an own card and an empty one do not count",
          smw.foreign_orientation(mw, [1, 2]) == 0)
    plan = smw.beam_plan(mw, res_b, beam_plane, "B", True)
    check("saved model without other orientations: card, no note",
          plan["card"] == [1, 2] and plan["notes"] == [] and
          mw.selections[u"SECTION_V_P"] == [])
    write_model(u'<solution>\n<elem eid="1" orientationvx="1" />\n</solution>')
    check("saved model: the copy inside <solution> is not read",
          smw.foreign_orientation(BeamMw(up, saved), [1, 2]) == 0)
finally:
    shutil.rmtree(work, ignore_errors=True)

# --- every direction: the outline on the beam is the original face ----------
def closure(normal, phi_deg, against, turned=False):
    """Largest distance between the original corners of a face with this
    normal and the outline placed on a beam the way Mecway places it: V from
    the card projected on the plane normal to U, W = U x V. turned: the
    beam has -axis 1 as its V and the data are written for it."""
    n = smw._norm(normal)
    u, v = smw.plane_axes(n)
    pln = {"normal": n, "u": u, "v": v, "offset": 0.3}
    flat = [(0.21, 0.13), (0.27, 0.13), (0.27, 0.136), (0.216, 0.136),
            (0.216, 0.17), (0.21, 0.17)]
    data = dict(res_b, phi_deg=phi_deg, centroid=[0.23, 0.14],
                loops=[[list(p) for p in flat]])
    use = smw.for_beam(data, against, turned)
    beam_v = smw._mul(smw.principal_axis(data, pln), -1.0 if turned else 1.0)
    beam_u = smw._mul(n, -1.0 if against else 1.0)
    beam_w = smw._cross(beam_u, beam_v)
    worst = abs(smw._dot(beam_v, beam_u))

    def place(x, y):
        return smw._add(smw._add(smw._mul(u, x), smw._mul(v, y)),
                        smw._mul(n, 0.3))
    origin = place(0.23, 0.14)
    for (x, y), (bv, bw) in zip(flat, smw.principal_loops(use)[0]):
        at = smw._add(smw._add(origin, smw._mul(beam_v, bv)),
                      smw._mul(beam_w, bw))
        worst = max(worst, smw._dist(at, place(x, y)))
    return worst


def spread():
    axes = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0), (1, 0, 1), (0, 1, 1),
            (1, -1, 0), (1, 1, 1), (1, -2, 3), (0.001, 1, 0), (1e-5, 1, 1e-5),
            (0, 0.9995, 0.03)]
    out = axes + [tuple(-c for c in a) for a in axes]
    # a fixed spiral over the sphere
    for k in range(200):
        z = -1.0 + (2.0 * k + 1.0) / 200.0
        r = math.sqrt(1.0 - z * z)
        a = k * 2.399963
        out.append((r * math.cos(a), r * math.sin(a), z))
    return out


worst_all = 0.0
for normal in spread():
    for phi_deg in (0.0, 30.0, 45.0, 90.0, -30.0, -89.0):
        for against in (False, True):
            for turn in (False, True):
                worst_all = max(worst_all,
                                closure(normal, phi_deg, against, turn))
check("every direction, both senses, V or -V: outline on the original face "
      "(worst {0:.2e} m)".format(worst_all), worst_all < 1e-12)

turned = {1: ((0, 0, 0), (0.1, -0.2, 0.3))}
n_t = smw._norm((1, -2, 3))
u_t, v_t = smw.plane_axes(n_t)
pln_t = {"normal": n_t, "u": u_t, "v": v_t, "offset": 0.0}
plan = smw.beam_plan(BeamMw(turned), res_b, pln_t, "B", True)
check("beam in a general direction: card, along n", plan["card"] == [1] and
      not plan["mirrored"] and smw._dist(plan["u"], n_t) < 1e-12)
turned = {1: ((0.1, -0.2, 0.3), (0, 0, 0))}
plan = smw.beam_plan(BeamMw(turned), res_b, pln_t, "B", True)
check("beam in a general direction, reversed: mirrored",
      plan["mirrored"] and smw._dist(plan["u"], smw._mul(n_t, -1.0)) < 1e-12)

if check.failed:
    print("FOUT: test_section_mecway")
    sys.exit(1)
print("Alle controles OK")
