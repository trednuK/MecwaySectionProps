# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# MecwaySectionProps.py
# Entry point of MecwaySectionProps: cross-section properties of a flat
# face in Mecway (the Mecway version of AreaPropsForAlibre). Register it in
# Mecway under Tools > Scripts (README.md) and run it with
# the faces of a cross-section selected (face selection).
#
# 'mw' (Mecway API) exists only in this script's namespace; it is passed to
# section_gui.run_window, and from there to section_mecway (the only module
# that calls mw).
#
# Modules:
#   section_utils     : settings, language, log, work folder, Code-Aster's
#                       Python
#   section_gui       : the non-modal window (table, plot, buttons)
#   section_mecway    : selection -> plane and boundary, CAD (STEP) request,
#                       Mecway material, #ASTER-SECTIE line in the .liml
#   section_analysis  : the analysis itself (Python 3 of the Code-Aster
#                       installation, numpy/scipy; started as a process):
#                       section_mesh (triangle mesh), section_fem
#                       (properties), section_step (exact STEP boundary)
# MecwayAsterBridge (github.com/trednuK/MecwayAsterBridge) reads the
# #ASTER-SECTIE line and passes the extra characteristics to
# AFFE_CARA_ELEM.
#
# Compatible with IronPython 2.7.9.

import os
import sys
import traceback

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
    if _HERE not in sys.path:
        sys.path.insert(0, _HERE)
except NameError:
    pass

from section_utils import log, tr
import section_gui


def main():
    token = section_gui.claim_instance()
    if token is None:
        # Second start while the window is open: bring it to the front.
        if not section_gui.activate_existing():
            mw.message(section_gui.instance_busy_text())
        return
    try:
        section_gui.run_window(mw)
    except Exception:
        log("ERROR: MecwaySectionProps: {0}".format(traceback.format_exc()))
        mw.message(tr(u"MecwaySectionProps gestopt door een fout:\n{0}",
                      u"MecwaySectionProps stopped by an error:\n{0}")
                   .format(traceback.format_exc()))
    finally:
        section_gui.release_instance(token)


main()
