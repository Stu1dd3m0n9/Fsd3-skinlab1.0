# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""Tkinter Canvas renderer: full .xui scenes + .xur string-model previews.

.xui full render: visuals expanded beforehand, timelines evaluated
beforehand, Z-depth perspective scale, XuiFigure polygons, SizeMode
stretch, ARGB colors, sample list rows. DDS that won't decode draws a
labeled placeholder instead of a broken tile.

.xur preview: draws the guessed control tree (class + id) as a readable
stack so EVERY scene shows something; decompile for pixel-exact render.
"""
from __future__ import annotations

import io
import os
import tkinter as tk
from typing import Callable

from PIL import Image, ImageTk

try:
    from .xui import Node
except ImportError:  # direct script run
    from xui import Node  # type: ignore


def argb_to_hex(s: str | None, default: str = "#ffffff") -> tuple[str, float]:
    if not s:
        return default, 1.0
    h = s.strip().lower().replace("0x", "")
    if len(h) == 8:
        try:
            return "#" + h[2:], int(h[0:2], 16) / 255.0
        except ValueError:
            return default, 1.0
    if len(h) == 6:
        try:
            int(h, 16)
            return "#" + h, 1.0
        except ValueError:
            return default, 1.0
    return default, 1.0


def parse_pos(s: str | None) -> tuple[float, float, float]:
    if not s:
        return 0.0, 0.0, 0.0
    try:
        parts = [float(x) for x in s.split(",")]
        while len(parts) < 3:
            parts.append(0.0)
        return parts[0], parts[1], parts[2]
    except ValueError:
        return 0.0, 0.0, 0.0


def parse_size(node: Node) -> tuple[float, float]:
    try:
        w = float(node.props.get("Width", "0") or 0)
    except ValueError:
        w = 0.0
    try:
        h = float(node.props.get("Height", "0") or 0)
    except ValueError:
        h = 0.0
    return w, h


Z_SCALE = 1.0 / 1200.0


class Renderer:
    def __init__(self, read_image: Callable[[str], bytes | None]):
        self.read_image = read_image
        self._img_cache: dict[tuple[str, int, int], ImageTk.PhotoImage] = {}
        self._pil_cache: dict[str, Image.Image | None] = {}
        self.items: list[tuple[int, Node, tuple[float, float, float, float]]] = []

    def clear(self) -> None:
        self._img_cache.clear()
        self._pil_cache.clear()

    def _pil(self, rel: str) -> Image.Image | None:
        key = rel.lower()
        if key in self._pil_cache:
            return self._pil_cache[key]
        try:
            data = self.read_image(rel)
            if data is None:
                self._pil_cache[key] = None
                return None
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            self._pil_cache[key] = img
            return img
        except Exception:
            self._pil_cache[key] = None
            return None

    def _photo(self, rel: str, w: int, h: int) -> ImageTk.PhotoImage | None:
        if w <= 0 or h <= 0:
            return None
        key = (rel.lower(), w, h)
        if key in self._img_cache:
            return self._img_cache[key]
        pil = self._pil(rel)
        if pil is None:
            return None
        try:
            ph = ImageTk.PhotoImage(pil.resize((max(1, w), max(1, h)), Image.BILINEAR))
            self._img_cache[key] = ph
            return ph
        except Exception:
            return None

    def render(self, canvas: tk.Canvas, root: Node, scale: float = 1.0,
               select_id: str = "") -> None:
        canvas.delete("all")
        canvas.image = []  # drop last frame's refs (was an unbounded leak)
        self.items.clear()
        for child in root.children:
            self._draw(child, canvas, 0.0, 0.0, scale, select_id)

    def render_xur(self, canvas: tk.Canvas, info: dict, scene: str,
                   scale: float = 1.0) -> None:
        """Readable placeholder layout for a compiled scene."""
        canvas.delete("all")
        canvas.image = []
        self.items.clear()
        W = 1280 * scale
        canvas.create_rectangle(0, 0, W, 720 * scale, fill="#0c0c12", outline="")
        y = 12 * scale
        canvas.create_text(12 * scale, y, anchor="nw",
                           text=f"{scene}  ·  XUR v{info.get('version')}  ·  "
                                f"{len(info.get('controls', []))} named entries  ·  "
                                f"{info.get('size', 0)} bytes",
                           fill="#ffb300", font=("Segoe UI", max(8, int(13 * scale))))
        y += 30 * scale
        canvas.create_text(12 * scale, y, anchor="nw",
                           text="Compiled .xur preview (string-table) — decompile via "
                                "XUIHelper for pixel-exact render.",
                           fill="#8888aa", font=("Segoe UI", max(7, int(10 * scale))))
        y += 26 * scale
        for c in info.get("controls", [])[:40]:
            h = 22 * scale
            if y + h > 700 * scale:
                break
            canvas.create_rectangle(12 * scale, y, W - 12 * scale, y + h,
                                    fill="#1a2233", outline="#33415e")
            canvas.create_text(18 * scale, y + 2, anchor="nw",
                               text=f"{c['class']}   {c['id']}",
                               fill="white", font=("Segoe UI", max(7, int(10 * scale))))
            y += h + 3 * scale
        imgs = info.get("images", [])[:6]
        if imgs:
            canvas.create_text(12 * scale, y + 4, anchor="nw",
                               text="images: " + ", ".join(imgs)[:160],
                               fill="#7fa8d0", font=("Segoe UI", max(7, int(9 * scale))))

    def _draw(self, node: Node, canvas: tk.Canvas, ox: float, oy: float,
              scale: float, select_id: str) -> None:
        if node.tag == "XuiFigure":
            self._draw_figure(node, canvas, ox, oy, scale)
            return
        x, y, z = parse_pos(node.props.get("Position"))
        w, h = parse_size(node)
        zoom = max(0.4, min(2.5, 1.0 + z * Z_SCALE))
        X, Y = (ox + x) * scale, (oy + y) * scale
        W, H = w * zoom * scale, h * zoom * scale
        nid = node.props.get("Id", "")
        is_sel = bool(select_id and nid == select_id)
        tag = node.tag
        if tag == "XuiImage":
            self._draw_image(node, canvas, X, Y, W, H, nid, is_sel, scale)
        elif tag in ("XuiText", "XuiTextPresenter"):
            color, _a = argb_to_hex(node.props.get("TextColor", "0xFFFFFFFF"), "#fff")
            try:
                pts = float(node.props.get("PointSize", "15") or 15)
            except ValueError:
                pts = 15.0
            iid = canvas.create_text(X, Y, text=node.props.get("Text", nid or "text"),
                                     fill=color, anchor="nw",
                                     font=("Segoe UI", max(7, int(pts * zoom * scale * 0.9))),
                                     width=max(10, int(W)))
            self._track(canvas, iid, node, is_sel)
        elif tag in ("XuiButton", "XuiNavButton"):
            iid = canvas.create_rectangle(X, Y, X + W, Y + H, fill="#2b3a55",
                                          outline="#ffb300" if is_sel else "#7fb2ff",
                                          width=2 if is_sel else 1)
            canvas.create_text(X + W / 2, Y + H / 2,
                               text=node.props.get("Text", nid or "button"),
                               fill="white", font=("Segoe UI", max(7, int(12 * zoom * scale))))
            self._track(canvas, iid, node, False)
        elif tag in ("XuiList", "XuiListBox"):
            iid = canvas.create_rectangle(X, Y, X + W, Y + H, fill="#14141c",
                                          outline="#ffb300" if is_sel else "#6666aa",
                                          width=2 if is_sel else 1)
            rows = max(1, min(8, int(H // max(20, 22 * zoom * scale))))
            for i in range(rows):
                ry = Y + 4 + i * (H - 8) / rows
                canvas.create_rectangle(X + 4, ry, X + W - 4, ry + (H - 8) / rows - 3,
                                        fill="#2e6fd8" if i == 0 else "#23232e", outline="")
                canvas.create_text(X + 10, ry + 2, text=f"{nid or 'list'} · row {i + 1}",
                                   fill="white", anchor="nw",
                                   font=("Segoe UI", max(7, int(10 * zoom * scale))))
            self._track(canvas, iid, node, False)
        elif tag in ("XuiSlider", "XuiEdit"):
            iid = canvas.create_rectangle(X, Y, X + W, Y + H, fill="#101018",
                                          outline="#ffb300" if is_sel else "#888",
                                          width=2 if is_sel else 1)
            canvas.create_text(X + 6, Y + H / 2, text=f"{tag} · {nid}",
                               fill="#ccc", anchor="w", font=("Segoe UI", 8))
            self._track(canvas, iid, node, False)
        elif tag in ("XuiScene", "XuiTabScene", "XuiGroup", "XuiControl",
                     "XuiCanvas", "XuiVisual"):
            if w > 0 and h > 0 and tag in ("XuiScene", "XuiGroup"):
                iid = canvas.create_rectangle(X, Y, X + W, Y + H,
                                              outline="#ffb300" if is_sel else "#3a3a3a",
                                              dash=None if is_sel else (3, 3),
                                              width=2 if is_sel else 1)
                self._track(canvas, iid, node, False)
            for c in node.children:
                self._draw(c, canvas, ox + x, oy + y, scale, select_id)
        else:
            for c in node.children:
                self._draw(c, canvas, ox + x, oy + y, scale, select_id)

    def _track(self, canvas: tk.Canvas, iid: int, node: Node, is_sel: bool):
        try:
            box = tuple(canvas.bbox(iid) or (0, 0, 0, 0))
        except Exception:
            box = (0, 0, 0, 0)
        self.items.append((iid, node, box))  # type: ignore[arg-type]
        if is_sel:
            try:
                canvas.itemconfig(iid, outline="#ffb300", width=2)
            except Exception:
                pass

    def _draw_image(self, node, canvas, X, Y, W, H, nid, is_sel, scale):
        rel = node.props.get("ImagePath", "")
        ph = self._photo(rel, int(W), int(H)) if rel else None
        if ph is not None:
            iid = canvas.create_image(X, Y, image=ph, anchor="nw")
            canvas.image.append(ph)  # keep ref; list reset per render() above
            self._track(canvas, iid, node, is_sel)
        else:
            label = os.path.basename(rel) if rel else "(no image)"
            if rel.lower().endswith(".dds"):
                label = "DDS→PNG needed: " + label
            iid = canvas.create_rectangle(X, Y, X + max(W, 40), Y + max(H, 24),
                                          fill="#202028",
                                          outline="#ffb300" if is_sel else "#8888aa",
                                          width=2 if is_sel else 1)
            canvas.create_text(X + max(W, 40) / 2, Y + max(H, 24) / 2, text=label,
                               fill="#aab", font=("Segoe UI", max(7, int(9 * scale))),
                               width=max(W, 40))
            self._track(canvas, iid, node, False)

    def _draw_figure(self, node, canvas, ox, oy, scale):
        fig = node.figure or {}
        pts = fig.get("points", [])
        if len(pts) < 3:
            return
        fill, _a = argb_to_hex(fig.get("fill"), "")
        coords: list[float] = []
        for px, py in pts:
            coords += [(ox + px) * scale, (oy + py) * scale]
        canvas.create_polygon(coords, fill=fill if fill else "",
                              outline=argb_to_hex(fig.get("stroke"), "#000")[0])
