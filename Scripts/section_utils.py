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
#   find_python()              a python.exe with numpy and scipy, the
#                              prerequisite of section_analysis.py
#
# Settings (all optional; empty = automatic):
#   "language":     "nl" or "en" (the NL/EN buttons of the window save it;
#                   default: the Windows display language)
#   "work_dir":     work folder; default WorkDir next to the Scripts folder
#   "accuracy":     coarse, normal, fine or very_fine (section_mecway.ACCURACY;
#                   the window's Accuracy choice saves it); default normal
#   "python":       python.exe with numpy and scipy (the older name
#                   "aster_python" still works); default: searched, see
#                   find_python
#   "python_found": the Python the search found last (written by find_python)
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
_DEFAULTS = {"language": "", "work_dir": "", "python": "", "aster_python": ""}
# Oldest scipy with cKDTree.query_ball_point(return_length=...), which
# section_mesh needs (the Python 3.7 of an old Code-Aster has an older one).
MIN_SCIPY = (1, 3)
# -E: ignore PYTHONPATH and PYTHONHOME, but keep the user's site-packages,
# where "pip install" puts packages without write access to Python's folder.
PYTHON_FLAGS = "-E"
_PROBE = ("import sys, numpy, scipy, scipy.optimize, scipy.sparse, "
          "scipy.spatial; sys.stdout.write('SECTIONPY %d %s %s\\n' % ("
          "sys.version_info[0], numpy.__version__, scipy.__version__))")
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


def _aster_pythons():
    """Pythons of the Code-Aster installations under
    %LOCALAPPDATA%\\code_aster, newest first (layout of the Windows build,
    e.g. v2025\\17.4\\Python311\\python.exe, also v2025\\Python311)."""
    root = os.path.join(os.environ.get("LOCALAPPDATA", ""), "code_aster")
    found = []
    try:
        releases = os.listdir(root)
    except OSError:
        return []
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
    return [f[1] for f in sorted(found, key=lambda f: f[0], reverse=True)]


def _plain_pythons():
    """Other Pythons on this PC: the PATH (not the Microsoft Store stub in
    WindowsApps, which only opens the Store) and the default install
    folders, newest first."""
    found = []
    for folder in os.environ.get("PATH", "").split(os.pathsep):
        # not a relative entry: that would run a python.exe in the folder of
        # the model
        folder = folder.strip('" ')
        exe = os.path.join(folder, "python.exe")
        if (os.path.isabs(folder) and "windowsapps" not in exe.lower() and
                os.path.isfile(exe)):
            found.append(exe)
    tops = []
    for name in ("LOCALAPPDATA", "ProgramFiles"):
        top = os.environ.get(name, "")
        if top:
            tops.append(os.path.join(top, "Programs", "Python"))
            tops.append(top)
    for top in tops:
        try:
            names = os.listdir(top)
        except OSError:
            continue
        for name in names:
            exe = os.path.join(top, name, "python.exe")
            if name.lower().startswith("python") and os.path.isfile(exe):
                found.append(exe)
    return sorted(found, key=lambda p: _version_key(
        os.path.basename(os.path.dirname(p))), reverse=True)


def _run_quiet(exe, args, timeout=60):
    """(exit code, stdout) of a program, without a window; (None, "") when
    it cannot be started or does not end in time."""
    try:
        import clr
    except ImportError:
        clr = None
    try:
        if clr is None:
            import subprocess
            proc = subprocess.Popen([exe] + list(args),
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL,
                                    creationflags=0x08000000)
            try:
                out = proc.communicate(timeout=timeout)[0]
            except subprocess.TimeoutExpired:
                proc.kill()
                return None, ""
            return proc.returncode, out.decode("utf-8", "replace")
        clr.AddReference("System")
        from System.Diagnostics import Process, ProcessStartInfo
        info = ProcessStartInfo(exe)
        info.Arguments = u" ".join(
            u'"{0}"'.format(a.replace('"', '\\"')) for a in args)
        info.UseShellExecute = False
        info.CreateNoWindow = True
        info.RedirectStandardOutput = True
        proc = Process.Start(info)
        if not proc.WaitForExit(int(timeout * 1000)):
            proc.Kill()
            return None, ""
        return proc.ExitCode, proc.StandardOutput.ReadToEnd()
    except Exception as e:
        log("WARNING: could not run {0}: {1}".format(exe, e))
        return None, ""


def check_python(path):
    """(ok, reason) of a python.exe, with the flags section_analysis runs
    with. Reason: the versions when ok, else "no_run" (does not start),
    "no_packages" (no numpy or scipy) or "old" (Python 2 or an old scipy)."""
    code, out = _run_quiet(path, [PYTHON_FLAGS, "-c", _PROBE])
    if code is None:
        return False, "no_run"
    words = [w for line in out.splitlines() if line.startswith("SECTIONPY")
             for w in line.split()]
    if code != 0 or len(words) != 4:
        return False, "no_packages"
    if words[1] != "3" or tuple(_version_key(words[3])[:2]) < MIN_SCIPY:
        return False, "old"
    return True, "numpy {0}, scipy {1}".format(words[2], words[3])


def find_python(refresh=False):
    """
    The Python for section_analysis.py, the prerequisite of the program:
    {"path": python.exe with numpy and scipy or None, "pip": a Python that
    runs but lacks them or None, "own": the path from the settings or ""}.

    Search order: the setting "python" (nothing else when it is set), the
    Python found last, the Code-Aster installations, the other Pythons of
    this PC. A Python of Code-Aster is never offered for pip: installing
    packages there could break Code-Aster.
    """
    values = settings()
    own = expand_path(values.get("python") or values.get("aster_python"))
    if own:
        ok, why = check_python(own) if os.path.isfile(own) else (False, "")
        if ok:
            return {"path": own, "pip": None, "own": own}
        mine = why == "no_packages" and own not in _aster_pythons()
        return {"path": None, "pip": own if mine else None, "own": own}
    known = expand_path(values.get("python_found"))
    if known and os.path.isfile(known) and not refresh:
        return {"path": known, "pip": None, "own": ""}
    aster = _aster_pythons()
    pip = None
    seen = set()
    for path in aster + _plain_pythons():
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        ok, why = check_python(path)
        if ok:
            log("INFO: MecwaySectionProps: Python {0} ({1}).".format(path,
                                                                     why))
            save_setting("python_found", path)
            return {"path": path, "pip": None, "own": ""}
        if pip is None and why != "no_run" and path not in aster:
            pip = path
    return {"path": None, "pip": pip, "own": ""}


def forget_python():
    """Search again next time (the Python found last no longer works)."""
    save_setting("python_found", "")


def pip_command(python):
    """The command that installs the prerequisite packages."""
    return u'"{0}" -m pip install numpy scipy'.format(python)
