# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# gui_cap_data.py
# Results of an equal angle 150 x 150 x 10 for tools/gui_cap.py.
#
#   python tools/gui_cap_data.py <results.json>
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "Scripts"))
import section_analysis  # noqa: E402

T, A = 0.010, 0.150
res = section_analysis.run_analysis(
    {"loops": [[[0.0, 0.0], [A, 0.0], [A, T], [T, T], [T, A], [0.0, A]]],
     "n_target": 3000})
with open(sys.argv[1], "w") as f:
    json.dump(section_analysis._jsonable(res), f, indent=1)
