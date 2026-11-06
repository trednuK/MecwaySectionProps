# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# gui_cap.py
# The window of the tool as a PNG for the documentation, without Mecway: a
# fake mw and the results of an equal angle 150 x 150 x 10, offscreen.
#
#   python tools/gui_cap_data.py <results.json>        (numpy and scipy)
#   powershell -ExecutionPolicy Bypass -File tools/run_ipy.ps1 \
#       -Script tools/gui_cap.py -ScriptArgs <repo>,<results.json>,<out.png>,nl
import io
import json
import os
import sys

repo, data, out = sys.argv[1], sys.argv[2], sys.argv[3]
lang = sys.argv[4] if len(sys.argv) > 4 else "en"
sys.path.insert(0, os.path.join(repo, "Scripts"))
import section_gui as gui   # noqa: E402
import section_utils as su  # noqa: E402

su.settings = lambda: {"language": lang}
gui._lang = lambda: lang


class FakeMw(object):
    def components(self):
        return ["Beam"]

    def material(self, comp):
        return "Steel"

    def component_elements(self, comp):
        return [1]

    def element_shape(self, eid):
        return "line2"


class Direct(object):
    def call(self, f):
        return f()


with io.open(data, encoding="utf-8") as f:
    res = json.load(f)
window = gui._Window(FakeMw(), Direct())
D, F = window.D, window.F
form = window.form
form.StartPosition = F.FormStartPosition.Manual
form.Location = D.Point(-4000, -4000)
form.Size = D.Size(1120, 860)
window.res = res
window.plane = {"normal": (0.0, 0.0, 1.0), "u": (1.0, 0.0, 0.0),
                "v": (0.0, 1.0, 0.0), "offset": 2.0, "size": 0.2,
                "deviation": 0.0}
window.source = ("faces", 12)
window.component = "Beam"
window.name = u"L150x150x10"


def capture(sender, e):
    window.components = [("Beam", "Steel", True)]
    window.render()
    F.Application.DoEvents()
    bmp = D.Bitmap(form.Width, form.Height)
    form.DrawToBitmap(bmp, D.Rectangle(0, 0, form.Width, form.Height))
    bmp.Save(out)
    bmp.Dispose()
    form.Close()


form.Shown += capture
F.Application.Run(form)
print("saved " + out)
