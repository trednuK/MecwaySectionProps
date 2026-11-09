# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# gui_cap.py
# The window as a PNG, without Mecway and without showing anything: the form is
# never shown (no Show, no Application.Run, so it never takes the focus), it
# gets its handles and is drawn with DrawToBitmap. A fake mw and the results of
# an own example, an equal angle 150 x 150 x 10 (tools/gui_cap_data.py, run with
# the Python the tool itself finds). Settings, log and work files go to a
# temporary folder: the user's own settings are never touched.
#
# The images of the documentation, numbered at the place of the real controls,
# in Dutch and English (window_nl.png, window_en.png, window_manual_nl.png,
# window_manual_en.png):
#
#   powershell -ExecutionPolicy Bypass -File tools/run_ipy.ps1 \
#       -Script tools/gui_cap.py -ScriptArgs <repo>,doc,<folder>
#
# tests/test_section_gui.py uses the fakes and the harness of this file.
# Marks and the manual capture follow tools/gui_cap.py of
# MecwayAdvancedBeamAnalysis (same author).
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


class FakeMw(object):
    """A model with one beam component, as the window reads it at the start."""

    def components(self):
        return ["Beam"]

    def material(self, comp):
        return "Steel"

    def component_elements(self, comp):
        return [1]

    def element_shape(self, eid):
        return "line2"

    def file_name(self):
        return u""


class Direct(object):
    """The window's _MwCaller without a script thread: calls at once."""

    def call(self, f):
        return f()


def example_results(repo, folder):
    """The results of the example section (a dict), made by
    tools/gui_cap_data.py with the Python the tool finds (numpy, scipy)."""
    import section_utils as su
    python = su.find_python().get("path")
    if not python:
        raise RuntimeError("no Python with numpy and scipy for the example")
    out = os.path.join(folder, "res.json")
    subprocess.check_call([python, "-E", os.path.join(
        repo, "tools", "gui_cap_data.py"), out])
    with io.open(out, encoding="utf-8") as f:
        return json.load(f)


class Harness(object):
    """A window that is never shown, with its fakes, in a temp folder."""

    def __init__(self, repo, lang="en", res=None):
        sys.path.insert(0, os.path.join(repo, "Scripts"))
        self.folder = tempfile.mkdtemp(prefix="section_gui_")
        import section_utils as su
        su._CACHE["settings"] = dict(su._DEFAULTS, language=lang,
                                     work_dir=self.folder)
        su.save_setting = lambda key, value: su._CACHE["settings"].update(
            {key: value})
        import section_gui as gui
        import clr
        clr.AddReference("System.Windows.Forms")
        clr.AddReference("System.Drawing")
        import System.Drawing as D
        import System.Windows.Forms as F
        self.gui, self.D, self.F = gui, D, F
        gui._lang = lambda: lang
        self.window = gui._Window(FakeMw(), Direct())
        w = self.window
        form = w.form
        form.StartPosition = F.FormStartPosition.Manual
        form.Location = D.Point(-8000, -8000)
        w.components = [("Beam", "Steel", True)]
        w.component = "Beam"
        if res is not None:
            w.res = res
            w.plane = {"normal": (0.0, 0.0, 1.0), "u": (1.0, 0.0, 0.0),
                       "v": (0.0, 1.0, 0.0), "offset": 2.0, "size": 0.2,
                       "deviation": 0.0}
            w.source = ("faces", 12)
            w.name = u"L150x150x10"
        w.render()
        self.handles(form)
        w._layout_body()

    def handles(self, control):
        """Real window handles, without showing anything."""
        h = control.Handle
        for child in control.Controls:
            self.handles(child)
        return h

    def pump(self, condition, seconds=20.0):
        """Run events until condition() holds; False on a timeout."""
        from System.Threading import Thread
        end = time.time() + seconds
        while time.time() < end:
            self.F.Application.DoEvents()
            if condition():
                return True
            Thread.CurrentThread.Join(2)
        return False

    def open_doc(self, seconds=20.0):
        """The tab with the manual, until the manual stands on it."""
        w = self.window
        w.tabs.SelectedIndex = 1
        self.handles(w.page_doc)
        ok = self.pump(lambda: w.doc_ready() and not w.doc_loading, seconds)
        # the browser element paints a moment after the page is complete
        # (MecwayAdvancedBeamAnalysis measured a blank capture straight after)
        self.pump(lambda: False, 0.8)
        return ok

    def capture(self, path):
        from System.Drawing.Imaging import ImageFormat, PixelFormat
        D = self.D
        w = self.window
        form = w.form
        self.F.Application.DoEvents()
        bmp = D.Bitmap(form.Width, form.Height, PixelFormat.Format32bppArgb)
        form.DrawToBitmap(bmp, D.Rectangle(0, 0, form.Width, form.Height))
        viewer = w.doc_viewer
        if w._doc_shown() and w._is_browser():
            # the form leaves the browser element blank; it draws itself
            page = D.Bitmap(viewer.Width, viewer.Height,
                            PixelFormat.Format32bppArgb)
            viewer.DrawToBitmap(page, D.Rectangle(0, 0, viewer.Width,
                                                  viewer.Height))
            # its place through the tab page: PointToScreen of the browser
            # element leaves out the offscreen position of the form
            at = w.page_doc.PointToScreen(viewer.Location)
            g = D.Graphics.FromImage(bmp)
            g.DrawImage(page, at.X - form.Left, at.Y - form.Top,
                        viewer.Width, viewer.Height)
            g.Dispose()
            page.Dispose()
        if path:
            bmp.Save(path, ImageFormat.Png)
        return bmp

    def close(self):
        w = self.window
        w._on_closing(None, None)
        w.form.Dispose()
        shutil.rmtree(self.folder, ignore_errors=True)


# ---------------------------------------------------------------- documentation
MARGIN = 30
DISC = 20
MARK_COLOUR = (196, 60, 0)


class Marks(object):
    """Numbered discs on a capture. The form is drawn between two white
    margins and each disc goes where the real control is, so the numbers
    follow the layout."""

    def __init__(self, harness):
        self.h = harness
        self.D = harness.D
        self.items = []

    def corner(self, control):
        """Top left of a control in the final image."""
        form = self.h.window.form
        p = control.PointToScreen(self.D.Point(0, 0))
        return p.X - form.Left + MARGIN, p.Y - form.Top

    def left(self, number, control, dy=None):
        """In the left margin, level with a control (or dy below its top)."""
        x, y = self.corner(control)
        y += control.Height // 2 if dy is None else dy
        self.items.append((number, (MARGIN // 2, y), (x, y)))

    def right(self, number, control, dy=None):
        """In the right margin, level with a control."""
        x, y = self.corner(control)
        end = x + control.Width
        y += control.Height // 2 if dy is None else dy
        width = self.h.window.form.Width
        self.items.append((number, (width + MARGIN + MARGIN // 2, y),
                           (end, y)))

    def below(self, number, control, dx=12, down=24):
        """Under a control, with a short line up to it."""
        x, y = self.corner(control)
        tx, ty = x + dx, y + control.Height
        self.items.append((number, (tx, ty + down), (tx, ty)))

    def at(self, number, control, x, y, dx, dy):
        """Next to pixel x, y of a control, with a line to that pixel."""
        cx, cy = self.corner(control)
        self.items.append((number, (cx + int(x) + dx, cy + int(y) + dy),
                           (cx + int(x), cy + int(y))))

    def save(self, path, texts=()):
        from System.Drawing.Drawing2D import SmoothingMode
        from System.Drawing.Imaging import ImageFormat, PixelFormat
        D = self.D
        shot = self.h.capture(None)
        out = D.Bitmap(shot.Width + 2 * MARGIN, shot.Height,
                       PixelFormat.Format32bppArgb)
        g = D.Graphics.FromImage(out)
        g.Clear(D.Color.White)
        g.DrawImage(shot, MARGIN, 0, shot.Width, shot.Height)
        # The text of these controls is in a native part that DrawToBitmap
        # leaves out on a form that was never shown; the strings are the
        # controls' own.
        for control in texts:
            x, y = self.corner(control)
            g.DrawString(control.Text, control.Font, D.Brushes.Black,
                         float(x + 3), float(y + 3))
        g.SmoothingMode = SmoothingMode.AntiAlias
        colour = D.Color.FromArgb(*MARK_COLOUR)
        pen = D.Pen(colour, 1.5)
        brush = D.SolidBrush(colour)
        ring = D.Pen(D.Color.White, 1.5)
        font = D.Font("Segoe UI", 8.5, D.FontStyle.Bold)
        centre = D.StringFormat()
        centre.Alignment = D.StringAlignment.Center
        centre.LineAlignment = D.StringAlignment.Center
        for number, spot, target in self.items:
            if target:
                g.DrawLine(pen, spot[0], spot[1], target[0], target[1])
                g.FillEllipse(brush, target[0] - 2, target[1] - 2, 4, 4)
        for number, spot, target in self.items:
            r = D.Rectangle(spot[0] - DISC // 2, spot[1] - DISC // 2, DISC,
                            DISC)
            g.FillEllipse(brush, r)
            g.DrawEllipse(ring, r)
            g.DrawString(str(number), font, D.Brushes.White, D.RectangleF(
                float(r.X), float(r.Y) + 0.5, float(DISC), float(DISC)),
                centre)
        g.Dispose()
        shot.Dispose()
        out.Save(path, ImageFormat.Png)
        out.Dispose()


def _tab_marks(m, numbers):
    """The two tabs: the first in the left margin, the second beside it."""
    w = m.h.window
    x0, y0 = m.corner(w.tabs)
    first, second = w.tabs.GetTabRect(0), w.tabs.GetTabRect(1)
    mid = y0 + first.Y + first.Height // 2
    m.items.append((numbers[0], (MARGIN // 2, mid), (x0 + first.X + 4, mid)))
    m.items.append((numbers[1], (x0 + second.Right + 26, mid),
                    (x0 + second.Right, mid)))


def _calculation(h, path):
    """The tab Calculation with the example: every part numbered, top to
    bottom (the order of the table in §3 of the manual)."""
    w = h.window
    m = Marks(h)
    m.left(1, w.subtitle_label)
    m.right(2, w.lang_buttons["en"])
    _tab_marks(m, (3, 4))
    m.below(5, w.mode_radios["mesh"])
    m.below(6, w.calc_button, 60)
    m.below(7, w.unit_box, 30)
    m.below(8, w.accuracy_box, 90)
    m.left(9, w.table, 60)
    plot = w.plot
    # the drawing of the section: its centroid (about the middle of the plot)
    m.at(10, plot, plot.Width * 0.50, plot.Height * 0.39, -60, -50)
    m.right(11, plot, plot.Height - 70)
    m.at(12, w.name_box, w.name_box.Width // 2, 0, 0, -16)
    m.at(13, w.component_box, w.component_box.Width // 2, 0, 0, -16)
    m.at(14, w.copy_check, 150, 0, 0, -16)
    m.left(15, w.store_check)
    m.left(16, w.orient_check)
    m.right(17, w.gs_button)
    m.left(18, w.status_label)
    m.below(19, w.copy_image_button, 80, 12)
    m.below(20, w.copy_button, 55, 12)
    m.right(21, w.close_button)
    m.save(path, [w.unit_box, w.accuracy_box, w.name_box, w.component_box])


def client_rect(element):
    """(left, top, width, height) of an element of the manual in the pixels
    of the browser element."""
    try:
        r = element.DomElement.getBoundingClientRect()
        return (int(r.left), int(r.top), int(r.right - r.left),
                int(r.bottom - r.top))
    except Exception:
        o = element.OffsetRectangle
        return o.X, o.Y, o.Width, o.Height


def _manual(h, path):
    """The tab with the manual, at its top: the tabs, the language buttons
    and the contents line with its links."""
    w = h.window
    ok = h.open_doc()
    viewer = w.doc_viewer
    # the contents line: the first paragraph with links to headings
    links = []
    for p in viewer.Document.GetElementsByTagName("p"):
        links = [a for a in p.GetElementsByTagName("a")
                 if u"#h-" in u"{0}".format(a.GetAttribute("href"))]
        if len(links) >= 4:
            break
    m = Marks(h)
    _tab_marks(m, (1, 2))
    m.right(3, w.lang_buttons["en"])
    if len(links) >= 4:
        x, y, lw, lh = client_rect(links[3])
        # through the tab page, as in Harness.capture
        m.at(4, w.page_doc, viewer.Left + x + lw, viewer.Top + y + lh // 2,
             24, 18)
    m.save(path)
    w.tabs.SelectedIndex = 0
    h.pump(lambda: True, 0.05)
    return ok


def doc_images(repo, folder):
    """The four images of the documentation into folder."""
    if not os.path.isdir(folder):
        os.makedirs(folder)
    work = tempfile.mkdtemp(prefix="section_cap_")
    try:
        sys.path.insert(0, os.path.join(repo, "Scripts"))
        res = example_results(repo, work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    for lang in ("nl", "en"):
        h = Harness(repo, lang, res)
        try:
            _calculation(h, os.path.join(folder,
                                         "window_{0}.png".format(lang)))
            if not _manual(h, os.path.join(
                    folder, "window_manual_{0}.png".format(lang))):
                print("manual {0}: not on the page in time".format(lang))
        finally:
            h.close()
        print("images {0} written".format(lang))


# run_ipy.ps1 does not run a script as __main__: the arguments decide
if len(sys.argv) > 3 and sys.argv[2] == "doc":
    doc_images(sys.argv[1], sys.argv[3])
