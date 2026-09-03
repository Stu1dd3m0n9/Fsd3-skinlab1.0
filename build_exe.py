# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""Build a hard-to-reverse native exe with Nuitka (one-time setup).

Why Nuitka instead of shipping .py: CPython bytecode (.pyc) decompiles back
to near-original source in seconds, so plain scripts offer zero protection.
Nuitka compiles everything to machine code, which moves reversing from
"trivial" to "serious effort". Nothing stops a determined reverser —
the license is your real protection; this just raises the cost.

Release posture matters more than tooling: an MIT release gives everyone the
legal right to the source anyway, so ship the exe alone (no .py files next
to it) and keep the repo private if secrecy is the goal — or publish the
source openly and skip this script entirely.

Usage:
  pip install nuitka
  python build_exe.py        # needs a C compiler once; Nuitka will offer it
  -> dist/exe/Fsd3SkinStudio.exe (+ support files; ship the whole folder)

Notes:
- Standalone folder build on purpose: onefile repacks unpack on every
  launch and slows startup; a folder starts fast.
- Do NOT drop XUIHelper.CLI.exe or XDK tools into dist/ — users fetch
  those themselves (separate licenses).
- Expect a Windows SmartScreen / Defender first-run prompt on a fresh
  unsigned exe; normal for indie releases.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "dist", "exe")


def main() -> int:
    if shutil.which("nuitka") is None and not _has_nuitka_module():
        print("Nuitka is not installed. Run:  pip install nuitka")
        return 1
    os.makedirs(OUT, exist_ok=True)
    cmd = [
        sys.executable, "-m", "nuitka",
        "--standalone",
        "--enable-plugin=tk-inter",
        "--assume-yes-for-downloads",
        "--output-dir=" + OUT,
        "--output-filename=Fsd3SkinStudio.exe",
        "--company-name=StoicDemon",
        "--product-name=FSD3 Skin Studio",
        "--file-description=FSD3 Skin Studio (.xui + .xur)",
        os.path.join(HERE, "app.py"),
    ]
    print("$ " + " ".join(cmd))
    rc = subprocess.call(cmd, cwd=HERE)
    if rc != 0:
        print("Nuitka build failed with code", rc)
        return rc
    print("Built. Ship the dist/exe folder WITHOUT any .py source files.")
    print("Reminder: keep XUIHelper/XDK tools out of the release.")
    return 0


def _has_nuitka_module() -> bool:
    try:
        import nuitka  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main())
