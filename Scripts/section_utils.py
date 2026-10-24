# -*- coding: utf-8 -*-
# Copyright (C) 2026 trednuK
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# section_utils.py
# Responsibility: what the Mecway side of MecwaySectionProps shares:
#   settings()/save_setting()  the user's settings (Scripts/section_settings.json,
#                              not in git)
#   language()/tr(nl, en)      Dutch or English user text
#   log(text)                  log file in the work folder
#   work_dir()                 work folder (created when needed)
#   aster_python()             python.exe of the Code-Aster installation
#                              (numpy and scipy, for section_analysis.py)
#
# Settings (all optional; empty = automatic):
#   "language":     "nl" or "en" (the NL/EN buttons of the window save it;
#                   default: the Windows display language)
#   "work_dir":     work folder; default WorkDir next to the Scripts folder
#   "accuracy":     coarse, normal, fine or very_fine (section_mecway.ACCURACY;
#                   the window's Accuracy choice saves it); default normal
#   "aster_python": python.exe with numpy and scipy; default: found in the
#                   Code-Aster installation under %LOCALAPPDATA%\code_aster
#
# Compatible with IronPython 2.7.9 (Mecway) and CPython 3 (tests).

import io
import json
import os
import re
import time

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_PATH = os.path.join(SCRIPTS_DIR, "section_settings.json")
LOG_NAME = "section_props_log.txt"
_DEFAULTS = {"language": "", "work_dir": "", "aster_python": ""}
_CACHE = {}


def settings():
    """The settings, defaults filled in (read once per module load)."""
    if "settings" not in _CACHE:
        values = dict(_DEFAULTS)
        try:
            with io.open(SETTINGS_PATH, encoding="utf-8") as f:
                values.update(json.loads(f.read()))
        except (IOError, OSError, ValueError):
            pass
        _CACHE["settings"] = values
    return _CACHE["settings"]


def save_setting(key, value):
    """Store one setting; a failure (read-only folder) is only logged."""
    values = settings()
    values[key] = value
    try:
        with io.open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            f.write(u"{0}".format(json.dumps(values, indent=1,
                                             ensure_ascii=False)))
    except (IOError, OSError) as e:
        log("WARNING: settings not saved: {0}".format(e))


def _windows_language():
    try:
        from System.Globalization import CultureInfo
        name = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName
        return "nl" if name == "nl" else "en"
    except Exception:
        return "en"


def language():
    """ "nl" or "en": the setting, else the Windows display language."""
    lang = settings().get("language")
    return lang if lang in ("nl", "en") else _windows_language()


def tr(nl, en):
    """Text in the current language (Dutch first, then English)."""
    return nl if language() == "nl" else en


def expand_path(path):
    if not path:
        return ""
    return os.path.expanduser(os.path.expandvars(u"{0}".format(path).strip()))


def work_dir():
    """The work folder (created): the setting, else WorkDir next to the
    Scripts folder."""
    folder = expand_path(settings().get("work_dir")) or os.path.join(
        os.path.dirname(SCRIPTS_DIR), "WorkDir")
    if not os.path.isdir(folder):
        os.makedirs(folder)
    return folder


def log(text):
    """Append a line with a time stamp to the log; never raises."""
    try:
        path = os.path.join(work_dir(), LOG_NAME)
        with io.open(path, "a", encoding="utf-8") as f:
            f.write(u"[{0}] {1}\n".format(time.strftime("%Y-%m-%d %H:%M:%S"),
                                          text))
    except Exception:
        pass


def _version_key(name):
    return [int(p) for p in re.findall(r"\d+", name)]


def aster_python():
    """
    python.exe with numpy and scipy: the setting "aster_python", else the
    Python of the newest Code-Aster installation under
    %LOCALAPPDATA%\\code_aster (layout of the Windows build, e.g.
    v2025\\17.4\\Python311\\python.exe, also v2025\\Python311). None when
    none is found.
    """
    own = expand_path(settings().get("aster_python"))
    if own:
        return own if os.path.isfile(own) else None
    root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "code_aster")
    found = []
    try:
        releases = os.listdir(root)
    except OSError:
        return None
    for rel in releases:
        rel_dir = os.path.join(root, rel)
        if not os.path.isdir(rel_dir):
            continue
        for sub in os.listdir(rel_dir):
            sub_dir = os.path.join(rel_dir, sub)
            if sub.lower().startswith("python"):
                # the release's own Python, below a version folder
                found.append(([_version_key(rel), [-1]],
                              os.path.join(sub_dir, "python.exe")))
            elif os.path.isdir(sub_dir):
                for py in os.listdir(sub_dir):
                    if py.lower().startswith("python"):
                        found.append(([_version_key(rel), _version_key(sub)],
                                      os.path.join(sub_dir, py,
                                                   "python.exe")))
    found = [f for f in found if os.path.isfile(f[1])]
    if not found:
        return None
    return sorted(found, key=lambda f: f[0])[-1][1]
