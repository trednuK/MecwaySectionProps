# Changelog

## Unreleased

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
