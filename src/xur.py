# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""XUR (compiled XUI, magic XUIB) inspector + decompile bridge.

Retail FSD3 skins ship ONLY .xur (e.g. default.xzp). A full binary
reimplementation of XUR v5/v8 is out of scope for v1; instead this module:

1. Parses what Python can read reliably: magic, version, section list,
   and the full UTF-16LE string pool (class names, Ids, Texts, ImagePaths).
2. Guesses a control tree: every Xui* class token starts a control, the
   following non-class string(s) are its Id / Text / paths. Good enough to
   SHOW something for every scene instead of a blank pane.
3. Bridges to a real decompiler when the user points at one:
   XUIHelper.CLI (SGCSam/XUIHelper, open source, XURv5+XURv8 <-> XUI)
   `conv -s <in.xur> -f xuiv12 -o <out.xui> -g V5|V8`
   or the XDK XuiTool (manual). Decompiled .xui then gets the full render.

XUR versions: v5 = dash 1888-9199 (FSD3 / default.xzp era),
v8 = dash 12611-17559.
"""
from __future__ import annotations

import os
import re
import struct
import subprocess

XUI_CLASS_RE = re.compile(r"Xui[A-Za-z]+")
UTF16_RUN_RE = re.compile(rb"(?:[\x20-\x7e\x80-\xff]\x00){2,}")
SECTIONS = (b"STRN", b"VECT", b"DATA", b"KEYD", b"TIML", b"ANIM", b"XUIB")


def parse_xur(data: bytes) -> dict:
    """Best-effort parse. Never raises on trailing garbage; raises on bad magic."""
    if data[:4] != b"XUIB":
        raise ValueError("not an XUR file (missing XUIB magic)")
    version = struct.unpack(">I", data[4:8])[0] if len(data) >= 8 else 0
    # section scan (tolerant: lengths vary by version)
    sections: list[tuple[str, int, int]] = []
    for tag in SECTIONS[1:]:
        pos = 0
        while True:
            i = data.find(tag, pos)
            if i < 0:
                break
            ln = struct.unpack(">I", data[i + 4:i + 8])[0] if len(data) >= i + 8 else 0
            sections.append((tag.decode(), i, ln))
            pos = i + 4
    strings = _extract_strings(data)
    controls = _guess_controls(_extract_strings_ordered(data))
    texts = [s for s in strings if s and not s.startswith("Xui")
             and "\\" not in s and len(s) <= 64]
    images = [s for s in strings if "\\" in s and s.lower().endswith(
        (".png", ".jpg", ".dds", ".bmp", ".xur", ".xui"))]
    return {
        "version": version,
        "size": len(data),
        "sections": sections,
        "strings": strings,
        "controls": controls,  # [{class, id}]
        "texts": texts[:200],
        "images": images[:200],
    }


def _extract_strings_ordered(data: bytes) -> list[str]:
    """All string hits in file order, duplicates kept (for control counting)."""
    out: list[str] = []
    for m in UTF16_RUN_RE.finditer(data):
        try:
            s = m.group(0).decode("utf-16-le")
        except UnicodeDecodeError:
            continue
        for part in re.split(r"[\x00-\x1f]+", s):
            part = part.strip()
            if len(part) >= 2:
                out.append(part)
    return out


def _extract_strings(data: bytes) -> list[str]:
    # de-dup preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in _extract_strings_ordered(data):
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


def _guess_controls(strings: list[str]) -> list[dict]:
    """Pair each Xui* class token with the next non-class string as its Id."""
    controls: list[dict] = []
    i = 0
    while i < len(strings):
        s = strings[i]
        if XUI_CLASS_RE.fullmatch(s):
            cid = ""
            if i + 1 < len(strings) and not XUI_CLASS_RE.fullmatch(strings[i + 1]):
                cid = strings[i + 1]
            controls.append({"class": s, "id": cid})
            i += 2 if cid else 1
        else:
            i += 1
    return controls


def version_group(version: int) -> str:
    return "V5" if version <= 5 else "V8"


def decompile_with_xuihelper(xur_path: str, out_xui: str, cli_exe: str,
                             group: str = "V5") -> tuple[bool, str]:
    """Run XUIHelper.CLI conv. Returns (ok, log)."""
    if not os.path.isfile(cli_exe):
        return False, f"CLI not found: {cli_exe}"
    cmd = [cli_exe, "conv", "-s", xur_path, "-f", "xuiv12",
           "-o", out_xui, "-g", group]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except Exception as e:
        return False, f"failed to launch CLI: {e}"
    log = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and os.path.isfile(out_xui)
    return ok, f"$ {' '.join(cmd)}\nexit={proc.returncode}\n{log[:2000]}"
