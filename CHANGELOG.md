# Changelog

## Unreleased

- **Display scale**: at a Windows display scale above 100 % the window grows with its text.
  At 125 % the header ran into the tabs and the input choice into *Calculate*. The window
  also stays within the screen.
- **Sections far from the origin**: the section is meshed about the centre of its bounding box,
  so a face 100 m or more from the model origin no longer stops with a Qhull error; the results
  are the same as at the origin.
- **V axis of a section that is symmetric in one axis only**: Mecway's default V opposite to the
  needed V is no longer treated as right unless the section is point-symmetric (opposite V turns
  the section 180 degrees). A T section on a beam now gets its V-axis card, and EZ and IYR2 keep
  their sign.
- **Manual in the window**: a second tab *Handleiding/Manual* shows the manual in the chosen
  language, with its images; links to chapters scroll, the link to the other language
  switches it, web links open in your own browser. The window images in the manual are
  numbered, with a table under each that explains every part. Checked offscreen in Mecway's
  IronPython, and by the user in the Mecway window (tab, images, language switch).

## V2026.3 (2026-11-07)

- **Shear stress fields**: `section_fem.shear_fields` gives the shear stress over the section
  for a unit torque and unit shear forces, and `warping_properties` also returns the shear
  functions. No change for users; MecwayAdvancedBeamAnalysis uses this to show the stress
  on every point of a section.

## V2026.2 (2026-11-06)

- **V axis of the beam**: *Create general section* now sets the Element orientation of
  the beams it assigns the section to (box on by default). Without it the beam is turned
  and its stiffness is wrong. The API has no call for this: the card comes in by import.
  Skew beams and beams with an orientation of their own are left alone, with a note.
- **Beams against the normal** get their data mirrored in W (`EZ`, `IYR2`, recovery point,
  outline), so that the section is right in both directions.
- **Documentation**: new window images in Dutch and English, made with `tools/gui_cap.py`
  without Mecway; advice to use `POU_D_TG` for open sections in Code-Aster.
- **`** SECTIE-RICHTING` line**: the V axis and direction a section belongs to, for
  MecwayAsterBridge to warn about a beam that no longer fits.

## V2026.1 (2026-11-06)

- **Shape of the section in the model**: with the extra Code-Aster properties, *Create
  general section* also stores the simplified outline as `** SECTIE-VORM` lines, for
  MecwayAsterBridge to draw the section on the beams.
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
