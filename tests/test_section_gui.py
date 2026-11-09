# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# test_section_gui.py
# The window offscreen in Mecway's IronPython, without Mecway and without
# showing anything (tools/gui_cap.py Harness: never shown, so it takes no
# focus): the two tabs, the manual on the second tab in both languages, and
# what may not break it: a redraw of the window while the manual is shown or
# loading, a refresh of the page, the link to the other language, an anchor.
#
#   powershell -ExecutionPolicy Bypass -File tools/run_ipy.ps1 \
#       -Script tests/test_section_gui.py
from __future__ import print_function

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

failed = []


def check(name, cond, detail=""):
    print(("OK   " if cond else "FOUT ") + name +
          ("" if cond or not detail else "  ({0})".format(detail)))
    if not cond:
        failed.append(name)


try:
    import clr  # noqa: F401
except ImportError:
    print("SKIP test_section_gui: needs Mecway's IronPython (run_ipy.ps1)")
    sys.exit(0)

import gui_cap  # noqa: E402

h = gui_cap.Harness(REPO, "nl")
w = h.window
try:
    check("two tabs, Dutch names", w.tabs.TabPages.Count == 2 and
          w.page_calc.Text == u"Berekening" and
          w.page_doc.Text == u"Handleiding")
    check("the calculation is on the first tab",
          w.calc_button.Parent is not None and
          w.page_calc.Controls.Count == 4)
    check("the manual is not made before its tab opens",
          w.doc_viewer is None and w.doc_loads == 0)

    w.render()
    check("a redraw keeps the tabs and does not add controls",
          w.tabs.TabPages.Count == 2 and w.page_calc.Controls.Count == 4 and
          w.head_host.Controls.Count == 1)

    check("the manual opens in Dutch", h.open_doc() and w.doc_lang == "nl" and
          w.doc_loads == 1, (w.doc_lang, w.doc_loads))
    viewer = w.doc_viewer
    check("the browser element is used", w._is_browser())

    w.render()
    h.pump(lambda: False, 0.3)
    check("a redraw in the same language keeps the page",
          w.doc_viewer is viewer and w.doc_loads == 1 and w.doc_ready())

    check("an anchor scrolls", w.doc_scroll_to(u"h-3") and
          not w.doc_scroll_to(u"h-9999"))

    w._load_doc()
    w.render()                      # while the page is still loading
    check("a redraw while loading does not break the manual",
          h.pump(lambda: w.doc_ready() and not w.doc_loading, 20.0) and
          w.doc_viewer is viewer)

    loads = w.doc_loads
    viewer.Refresh()
    check("a refresh (F5) still shows the manual",
          h.pump(lambda: w.doc_ready() and not w.doc_loading, 20.0),
          (w.doc_loads - loads))

    w._follow(u"about:blank#lang-en")
    check("the link to the other manual switches the language",
          h.pump(lambda: w.lang == "en" and w.doc_lang == "en" and
                 w.doc_ready() and not w.doc_loading, 20.0) and
          w.page_doc.Text == u"Manual" and
          w.page_calc.Text == u"Calculation", (w.lang, w.doc_lang))

    w._follow(u"about:blank#h-2")
    check("a link to a heading stays on the page", w.doc_ready() and
          w.lang == "en")

    w.tabs.SelectedIndex = 0
    h.pump(lambda: True, 0.05)
    w._set_lang("nl")
    h.pump(lambda: w.lang == "nl" and w.page_calc.Text == u"Berekening", 5.0)
    loads = w.doc_loads
    check("a language change with the manual hidden loads nothing",
          w.doc_lang == "en" and w.doc_loads == loads)
    w.tabs.SelectedIndex = 1
    check("opening the tab again loads the manual in the new language",
          h.pump(lambda: w.doc_lang == "nl" and w.doc_ready() and
                 not w.doc_loading, 20.0))
finally:
    h.close()
check("closed: no more work on the page", w.closed)

if failed:
    print("FOUT: test_section_gui ({0})".format(len(failed)))
    sys.exit(1)
print("Alle controles OK")
