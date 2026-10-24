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
  with numpy and scipy only: the Python of the Code-Aster installation
  (`section_utils.aster_python`). No pip packages, ever (the user runs only Mecway and
  Code-Aster). `section_step.py` must work in both.
- Mecway API: only what is in Mecway's API reference (Help > API reference); do not copy
  text from it or from the manual. Values through the API are SI.

## Contract with MecwayAsterBridge

The line `** ASTER-SECTIE <material>: A=.., IY=.., IZ=.., JX=.., AY=.., AZ=.., EY=..,
EZ=.., RY=.., RZ=.., RT=.., JG=.., IYR2=.., IZR2=..` (SI, local y = principal axis 1 =
Mecway V, z = axis 2 = W; EY/EZ = vector shear centre -> centroid, as `MACR_CARA_POUTRE`)
is read by MecwayAsterBridge (`bridge_custom.py`, `bridge_from_liml._section_extras`).
A change of the format needs the same change there.

## Checking

```bash
python tests/test_section_mecway.py
python tests/test_section_step.py
python tests/test_section_analysis.py
powershell -ExecutionPolicy Bypass -File tools/run_ipy.ps1 -Script tests/test_section_mecway.py
```

A real run is only possible in Mecway (computer use on the open instance; never on the
user's own model files). `WorkDir/` and `Scripts/section_settings.json` are local (not
in git).

## Conventions

- License MPL-2.0; a new source file gets the header of `Scripts/section_utils.py`.
- English for code comments, docstrings, log lines and commit messages; user text in both
  languages with `tr(nl, en)` (Dutch first).
- Support Code-Aster behaviour with a source (U/R document), otherwise "NOT verified".
- This repository is public: no personal data or own paths in commits.
