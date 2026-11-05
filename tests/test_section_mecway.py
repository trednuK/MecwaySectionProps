# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# Offline test of Scripts/section_mecway.py (Python 2.7 and 3): plane and
# boundary of selected faces, quadratic faces, holes, repairs and the
# #ASTER-SECTIE line (the format MecwayAsterBridge reads).
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

if check.failed:
    print("FOUT: test_section_mecway")
    sys.exit(1)
print("Alle controles OK")
