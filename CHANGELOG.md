# Changelog

## Unreleased

- **STEP without a mesh**: Mecway's API cannot read a surface selected in the Geometry
  view, saved or not. A model without elements now shows the planar faces of the STEP
  file as temporary tri3 faces (no mesh: 2 s against 37 s and 192 000 elements on a small
  assembly); click one and Calculate. Everything added is removed afterwards.
- **STEP assemblies**: faces are found at the position Mecway shows, with placements
  through `ITEM_DEFINED_TRANSFORMATION`, also nested. Measured on Mecway 35's own preview
  (inv(A_child) A_parent); on a real 3-part assembly all 83 planar faces coincide.
- **CAD face without a saved .liml**: the window asks for the STEP file; `<assembly>`
  in a saved .liml is read. If the STEP has no face at that place under your own mesh,
  the mesh boundary is used with a note, instead of stopping.
- **Prerequisite Python 3 with numpy and scipy**, not only Code-Aster's: Code-Aster, then
  the `PATH` and the default folders; a Python that is too old is skipped (scipy < 1.3
  stopped with a `return_length` error). When missing, the window gives the pip command
  and offers to run it. Setting `python` (`aster_python` still works).
- **Straightening**: faces that are not exactly in one plane (up to 1% of the size)
  are projected onto the best-fitting plane and the deviation is reported, instead of
  stopping (Mecway GUI test: 0.0002 mm).
- **Accuracy** choice in the window (coarse / normal / fine / very fine: about 1000,
  3000, 10000, 30000 elements, 2-6 rows across thin walls), remembered in the settings.
- **Copy image**: only the drawing on the clipboard, twice as sharp as on screen.

First version as a repository of its own (until 24 October 2026 part of
MecwayAsterBridge, commits 7b1d8fb, 95d3b84 and 3994f0a there).

- Section properties of a flat face selected in Mecway: area, centroid, second moments
  (also principal), elastic and plastic section moduli, torsion and warping constant,
  shear centre and shear areas, with a drawing; NL/EN, mm/m, Copy.
- Input: the boundary of the selected mesh faces, or the exact boundary of the STEP face
  they lie on. Small gaps are repaired and reported.
- *Create general section*: a Mecway material with a general section, and an
  `#ASTER-SECTIE` line for MecwayAsterBridge as an extra custom model definition.
- Own settings (`Scripts/section_settings.json`): language, work folder, Code-Aster's
  Python (found automatically); no dependency on MecwayAsterBridge.
