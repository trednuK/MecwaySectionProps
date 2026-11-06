# AGENTS.md

MecwaySectionProps: cross-section properties of a flat face selected in Mecway, and a
Mecway general section with an `#ASTER-SECTIE` line for MecwayAsterBridge. Entry point
and module overview: `Scripts/MecwaySectionProps.py`. User docs: `docs/` (Dutch) and
`docs/en/` (English), same structure; keep both up to date.

## Runtime

- Inside Mecway (IronPython 2.7.9): `MecwaySectionProps.py`, `section_gui.py`,
  `section_mecway.py`, `section_utils.py`. Python 2.7 code: no f-strings, type hints or
  `pathlib`; `"{0}".format(x)`; numbers in user text with `%`-formatting (IronPython's
  `"{0:.4g}"` follows the Windows locale). Standard library plus `clr`/Windows Forms.
- `mw` exists only in the entry script; `section_gui` passes it on, `section_mecway` is the
  only module that calls it. All `mw` calls run on Mecway's script thread
  (`section_gui._MwCaller`); the window has its own STA thread.
- The analysis (`section_analysis.py`, `section_mesh.py`, `section_fem.py`) is CPython 3
  with numpy and scipy only. That Python is a prerequisite the user installs, never
  bundled: `section_utils.find_python` takes Code-Aster's, then the `PATH` and default
  folders; when missing, the window gives the command and offers to run pip, only after
  the user's yes, and never in Code-Aster's Python. No other packages.
  `section_step.py` must work in both.
- Mecway API: only what is in Mecway's API reference (Help > API reference); do not copy
  text from it or from the manual. Values through the API are SI.
  `mw.selected_faces()` is empty for a surface selected in the Geometry view, so a model
  without elements gets temporary tri3 faces from the STEP file
  (`section_mecway.prepare`), which must always be removed again. Never
  `mw.generate_mesh()`: it meshes every part.
- STEP assemblies: `x_parent = inv(A_child) A_parent x_child` (Open CASCADE's order,
  measured on Mecway 35, `tests/data/section_step/assembly_rect_hole.step`). Not the
  other order: the two only agree when a frame is the identity.

## Contract with MecwayAsterBridge

The line `** ASTER-SECTIE <material>: A=.., IY=.., IZ=.., JX=.., AY=.., AZ=.., EY=..,
EZ=.., RY=.., RZ=.., RT=.., JG=.., IYR2=.., IZR2=..` (SI, local y = principal axis 1 =
Mecway V, z = axis 2 = W; EY/EZ = vector shear centre -> centroid, as `MACR_CARA_POUTRE`)
is read by MecwayAsterBridge (`bridge_custom.py`, `bridge_from_liml._section_extras`).
The lines `** SECTIE-VORM <material>: N=<points per loop, spaces>, A=<area>` followed by
`** SECTIE-VORM <material>: P=v w v w ...` hold the simplified outline (principal V, W
about the centroid, SI, loops closed implicitly, even-odd interior; P lines concatenate;
a new N for a material replaces what was read; split on the last colon). They are read by
MecwayAsterBridge, which draws the section on the beams (`bridge_custom.py`,
`bridge_section_view.py`) and compares A with the material. The line
`** SECTIE-RICHTING <material>: V=vx vy vz, U=ux uy uz` (global unit vectors, `%.6g`) holds
the V axis a beam needs and the beam direction the data are written for; the newest line of
a material wins, and the bridge warns about a beam that does not fit. Never start these
lines with `** ASTER-SECTIE `: the bridge reports such a line as an error. A change of any
of these formats needs the same change there.

Element orientation has no API. `section_mecway.orientation_xml` imports a card together
with its empty element selection (a card alone loses its selection), and the script fills
that selection. Never delete a `SECTION_V_*` selection: its card stays with
`selection=""`, which the bridge reports as an error on every run; take the elements out
instead. Two cards on one element make Mecway refuse to solve.

## Checking

```bash
python tests/test_section_mecway.py
python tests/test_section_step.py
python tests/test_section_analysis.py
powershell -ExecutionPolicy Bypass -File tools/run_ipy.ps1 -Script tests/test_section_mecway.py
```

`tools/gui_cap.py` makes the window images of `docs/images/` offscreen, without Mecway, from
an own example (`tools/gui_cap_data.py`).

A real run is only possible in Mecway (computer use on the open instance; never on the
user's own model files). `WorkDir/` and `Scripts/section_settings.json` are local (not
in git).

## Conventions

- License MPL-2.0; a new source file gets the header of `Scripts/section_utils.py`.
- English for code comments, docstrings, log lines and commit messages; user text in both
  languages with `tr(nl, en)` (Dutch first).
- Support Code-Aster behaviour with a source (U/R document), otherwise "NOT verified".
- This repository is public: no personal data or own paths in commits.
