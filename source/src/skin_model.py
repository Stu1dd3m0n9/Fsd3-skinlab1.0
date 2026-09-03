# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""Skin source: extracted folder or .xzp package, .xui + .xur aware."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

try:
    from .xzp import read_xzp
except ImportError:  # run as plain script (path already fixed by launcher)
    from xzp import read_xzp  # type: ignore


def _norm(rel: str) -> str:
    return rel.replace("/", "\\").lower()


class SkinSource:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.is_xzp = path.lower().endswith(".xzp")
        self._xzp: dict[str, bytes] | None = None
        self._names_cache: list[str] | None = None
        if self.is_xzp:
            self._xzp = read_xzp(self.path)

    def read(self, rel: str) -> bytes:
        key = _norm(rel)
        if self.is_xzp:
            assert self._xzp is not None
            if key not in self._xzp:
                raise FileNotFoundError(rel)
            return self._xzp[key]
        full = os.path.join(self.path, key.replace("\\", os.sep))
        with open(full, "rb") as fh:
            return fh.read()

    def exists(self, rel: str) -> bool:
        try:
            self.read(rel)
            return True
        except (FileNotFoundError, KeyError, OSError):
            return False

    def _names(self) -> list[str]:
        if self._names_cache is not None:  # one walk per source, not per query
            return self._names_cache
        if self.is_xzp:
            assert self._xzp is not None
            self._names_cache = sorted(self._xzp.keys())
            return self._names_cache
        out: list[str] = []
        for root, _d, files in os.walk(self.path):
            for fn in files:
                rel = os.path.relpath(os.path.join(root, fn), self.path)
                out.append(rel.replace(os.sep, "\\").lower())
        self._names_cache = sorted(out)
        return self._names_cache

    def list_xui(self) -> list[str]:
        return [n for n in self._names() if n.endswith(".xui")]

    def list_xur(self) -> list[str]:
        return [n for n in self._names() if n.endswith(".xur")]

    def list_images(self) -> list[str]:
        exts = (".png", ".jpg", ".jpeg", ".dds", ".bmp")
        return [n for n in self._names() if n.endswith(exts)]

    def info(self) -> dict:
        info: dict = {
            "name": os.path.basename(self.path.rstrip(os.sep)),
            "author": "",
            "version": "",
            "menus": [],
            "backgrounds": [],
            "scenes_xui": self.list_xui(),
            "scenes_xur": self.list_xur(),
            "is_xzp": self.is_xzp,
        }
        try:
            root = ET.fromstring(self.read("skin.xml").decode("utf-8", "replace"))
            sk = root.find("./settings/Skin")
            if sk is not None and sk.text:
                info["name"] = sk.text.strip()
            for tag in ("Author", "Version"):
                el = root.find("./settings/" + tag)
                if el is not None and el.text:
                    info[tag.lower()] = el.text.strip()
            for bg in root.findall("./Backgrounds/background"):
                info["backgrounds"].append({
                    "label": bg.get("label", ""),
                    "path": (bg.text or "").strip(),
                })
            dflt = root.find("./Backgrounds/default")
            if dflt is not None and dflt.text:
                info["default_bg"] = dflt.text.strip()
        except Exception as e:
            info["error"] = f"skin.xml: {e}"[:200]
        try:
            raw = self.read("Settings\\MenuSettings.xml").decode("utf-8", "replace")
            body = raw[raw.index("?>") + 2:] if raw.lstrip().startswith("<?xml") else raw
            mroot = ET.fromstring("<wrap>" + body + "</wrap>")
            for menu in mroot.findall("./menusettings/menu"):
                mid = menu.get("id") or menu.findtext("id")
                tabs: list[str] = []
                for t in mroot.findall("./tabsettings/tab"):
                    pid = t.get("parentid") or t.findtext("parentid")
                    if pid == mid:
                        txt = t.get("text") or t.findtext("text")
                        if txt:
                            tabs.append(txt)
                info["menus"].append({"text": menu.findtext("text") or menu.get("text", ""),
                                      "tabs": tabs})
        except Exception as e:
            info["menu_error"] = f"MenuSettings.xml: {e}"[:200]
        return info
