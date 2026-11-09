# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# test_section_docs.py
# The manual on the window's tab (Scripts/section_docs.py), CPython or
# IronPython, no Mecway, nothing fetched from the web:
#   - both manuals convert, with every image found and as a data URI;
#   - every link inside a manual lands on a heading, the references to the
#     window parts (§3.1, §3.2) are links, the link to the other manual
#     switches the language;
#   - section_docs.py is still a copy of beam_docs.py of
#     MecwayAdvancedBeamAnalysis when that repository is next to this one.
#
#   python tests/test_section_docs.py
from __future__ import print_function

import io
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(REPO, "Scripts"))
import section_docs as sdoc  # noqa: E402

IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
ID_RE = re.compile(r'id="(h-\d+)"')
HREF_RE = re.compile(r'href="#([^"]+)"')


def check(name, cond, detail=""):
    print(("OK   " if cond else "FOUT ") + name +
          ("" if cond or not detail else "  ({0})".format(detail)))
    if not cond:
        check.failed = True


check.failed = False

for lang in ("nl", "en"):
    html, text = sdoc.doc_html(lang)
    check("{0}: the manual is read".format(lang), len(text) > 1000)
    check("{0}: the page carries the marker".format(lang),
          u'id="{0}"'.format(sdoc.MARKER_ID) in html)
    images = IMAGE_RE.findall(text)
    check("{0}: every image in the page, none missing".format(lang),
          html.count(u"<img ") == len(images) and u"noimg" not in html,
          (len(images), html.count(u"<img ")))
    check("{0}: the two window images are used".format(lang),
          any(u"window_{0}.png".format(lang) in i for i in images) and
          any(u"window_manual_{0}.png".format(lang) in i for i in images))
    check("{0}: images as data URIs, nothing fetched".format(lang),
          u'src="http' not in html and u'src="data:image/' in html)
    ids = set(ID_RE.findall(html))
    anchors = HREF_RE.findall(html)
    loose = [a for a in anchors if a not in ids and
             not a.startswith(sdoc.LANG_PREFIX)]
    check("{0}: every link inside lands on a heading ({1} links)".format(
        lang, len(anchors)), not loose, loose[:5])
    other = u"en" if lang == "nl" else u"nl"
    check("{0}: the link to the other manual switches language".format(lang),
          u'href="#{0}{1}"'.format(sdoc.LANG_PREFIX, other) in html)
    # the references to the window parts link to their headings
    numbers = dict((m.group(1), k + 1) for k, m in enumerate(
        re.match(r"^(\d+(?:\.\d+)*)\.?\s", h) for _, h in sdoc.headings(text))
        if m)
    check("{0}: §3.1 and §3.2 are links".format(lang),
          all(u'<a href="#h-{0}">'.format(numbers[n]) in html
              for n in ("3.1", "3.2")))
    check("{0}: the contents line links all eight chapters".format(lang),
          all(u'href="#h-{0}"'.format(numbers[str(n)]) in html
              for n in range(1, 9)))

check("resolve_link: anchor, language, web, nothing",
      sdoc.resolve_link(u"about:blank#h-3") == ("anchor", u"h-3") and
      sdoc.resolve_link(u"about:blank#lang-en") == ("lang", u"en") and
      sdoc.resolve_link(u"https://example.org/x") ==
      ("web", u"https://example.org/x") and
      sdoc.resolve_link(u"file:///c:/x") == (None, None))

SOURCE = os.path.join(os.path.dirname(REPO), "MecwayAdvancedBeamAnalysis",
                      "Scripts", "beam_docs.py")


def code(path, names):
    """The code below the header of a docs module with its own names made
    neutral, line endings ignored."""
    with io.open(path, encoding="utf-8") as f:
        text = f.read().replace(u"\r\n", u"\n")
    text = text[text.index(u"\nimport base64"):]
    for old in names:
        text = text.replace(old, u"<NAME>")
    return text


if os.path.isfile(SOURCE):
    mine = code(os.path.join(REPO, "Scripts", "section_docs.py"),
                (u'u"MecwaySectionProps.md"', u'u"section-doc"'))
    theirs = code(SOURCE, (u'u"MecwayAdvancedBeamAnalysis.md"',
                           u'u"beam-doc"'))
    check("copy: section_docs.py is the same code as beam_docs.py",
          mine == theirs, "update the copy from MecwayAdvancedBeamAnalysis")
else:
    print("SKIP copy check: MecwayAdvancedBeamAnalysis is not next to this "
          "repository")

if check.failed:
    print("FOUT: test_section_docs")
    sys.exit(1)
print("Alle controles OK")
