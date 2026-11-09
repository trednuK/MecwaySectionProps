# MecwaySectionProps

Cross-section properties of a flat face in [Mecway](https://mecway.com), and a Mecway
*General section* made from them in one click.

Select the faces of a cross-section in Mecway (face selection), start the script, and get
area, centroid, second moments of area (also about the principal axes), elastic and
plastic section moduli, torsion constant J, warping constant Iw, shear centre and shear
areas, with a drawing of the section. The input is either the selected mesh faces or the
exact boundary of the CAD (STEP) face they lie on. Small gaps in the boundary are closed
automatically and reported.

*Create general section* makes a Mecway material with a general section (area, Iyy,
Izz, torsion constant, perimeter, stress recovery point). The characteristics Mecway has
no field for (shear coefficients, shear centre eccentricity, warping constant, ...) are
stored in the model as an `#ASTER-SECTIE` line, which
[MecwayAsterBridge](https://github.com/trednuK/MecwayAsterBridge) passes to Code-Aster. The
outline goes along as `SECTIE-VORM` lines, so that the bridge can show the real shape on the
beams.

![The window](docs/images/window_en.png)

The numbers are explained in
[§3.1 of the manual](docs/en/MecwaySectionProps.md#31-the-calculation-tab).

It is the Mecway version of AreaPropsForAlibre: the analysis (a quadratic triangle mesh
of the section and the finite element formulation of Pilkey, as the package
sectionproperties uses) runs in Python with numpy and scipy.

## Requirements

- Mecway 34 or 35 (Windows), with its scripting (IronPython 2.7.9) and Windows Forms.
- Python 3 with numpy and scipy (scipy 1.3 or newer). This is a prerequisite: Python is
  not included. The Python of a Code-Aster installation is found automatically; so is
  another Python with these packages. If numpy or scipy is missing, the window says so
  and offers to run `python -m pip install numpy scipy`.
- Optional: MecwayAsterBridge V2026.7 or newer, to use the extra Code-Aster properties
  and to show the shape of the section on the beams; V2026.8 or newer also warns about a
  beam that does not fit its section.

## Installation

1. Download the [latest release](https://github.com/trednuK/MecwaySectionProps/releases/latest) (*Source code (zip)*,
   unzip) or clone this repository, e.g. to `Documents\GitHub\MecwaySectionProps`.
2. In Mecway: *Tools* > *Scripts...* > *New*, and choose `Scripts\MecwaySectionProps.py`.
   It then appears in the *Tools* menu.

## Use

1. In Mecway choose *Edit* > *Select faces* (and, handy, *Edit* > *Edge detecting
   selection*: one click selects a whole flat face) and select the faces of the section.
2. *Tools* > *MecwaySectionProps*. The window stays open next to Mecway.
3. Choose *Mesh faces* or *CAD face* and the *Accuracy* (mesh fineness), click
   **Calculate**. *Copy* puts the table on the clipboard, *Copy image* the drawing.
   A STEP model or assembly without a mesh is not meshed: its planar faces appear as
   temporary faces in seconds; click one and **Calculate** again, and they are removed.
   A surface selected in Mecway's *Geometry* view cannot be read by scripts.
4. Optionally **Create general section** (material name, component, copy E/ν/ρ, store the
   extra Code-Aster properties).

Full documentation: [English](docs/en/MecwaySectionProps.md),
[Nederlands](docs/MecwaySectionProps.md).

## Accuracy

Checked against sectionproperties (13 sections: geometric properties exact, J, Iw and
shear areas within 1.6e-4) and against Code-Aster's own `MACR_CARA_POUTRE` (AY, AZ, EY,
EZ, JG, IYR2, IZR2 within 1e-6); GUI-tested in Mecway 34. Details in the documentation
§6.

## Development

- `Scripts/`: `MecwaySectionProps.py` (entry point), `section_gui.py`, `section_mecway.py`,
  `section_utils.py` (IronPython 2.7, inside Mecway); `section_analysis.py`,
  `section_mesh.py`, `section_fem.py` (Python 3 with numpy/scipy, started as a
  process); `section_step.py` (STEP reader, both).
- Tests: `python tests/test_section_mecway.py`, `python tests/test_section_step.py`,
  `python tests/test_section_analysis.py` (reruns itself with a Python with numpy/scipy), and
  in Mecway's IronPython without Mecway: `tools/run_ipy.ps1 -Script <test>`.
  `tests/section_aster_check.py` compares with `MACR_CARA_POUTRE` (runs Code-Aster).
- Conventions: [AGENTS.md](AGENTS.md).

## License

[Mozilla Public License 2.0](LICENSE). Mecway is a product of Mecway Ltd; this project
is not affiliated with Mecway Ltd or EDF (Code-Aster).
