# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""FSD3 Skin Studio — create + render FSD3 skins, .xui AND .xur.

Retail skins (default.xzp) ship compiled .xur only: those scenes are listed
with an [xur] badge and get a string-table preview (control tree, texts,
image refs) instead of a blank pane. Point the studio at XUIHelper.CLI
(SGCSam/XUIHelper, open source) to decompile any .xur -> .xui for the full
pixel render, or use XDK XuiTool manually.

Run:  python -m src.main
"""
from __future__ import annotations

import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import xml.etree.ElementTree as ET

try:
    from .skin_model import SkinSource
    from .xui import (Node, parse_xui, parse_visuals, parse_timelines,
                      apply_timelines, expand_visuals, build_id_map,
                      _build as _xui_build)
    from .renderer import Renderer, parse_pos as _parse_pos
    from .creator import (create_skin, new_scene, validate_skin,
                          control_xml, CONTROL_KINDS)
    from .xur import parse_xur, version_group, decompile_with_xuihelper
    from .xzp import write_xzp
except ImportError:  # direct run
    from skin_model import SkinSource  # type: ignore
    from xui import Node, parse_xui, parse_visuals, parse_timelines, apply_timelines, expand_visuals, build_id_map, _build as _xui_build  # type: ignore
    from renderer import Renderer, parse_pos as _parse_pos  # type: ignore
    from creator import create_skin, new_scene, validate_skin, control_xml, CONTROL_KINDS  # type: ignore
    from xur import parse_xur, version_group, decompile_with_xuihelper  # type: ignore
    from xzp import write_xzp  # type: ignore

CANON_W, CANON_H = 1280, 720


def _node_to_etree(node: Node) -> ET.Element:
    el = ET.Element(node.tag)
    if node.tag == "XuiFigure" and node.figure:
        return el
    if node.props:
        p = ET.SubElement(el, "Properties")
        for k, v in node.props.items():
            e = ET.SubElement(p, k)
            e.text = v
    for c in node.children:
        if c.tag == "XuiFigure":
            continue
        el.append(_node_to_etree(c))
    return el


def _extract_timelines_block(text: str) -> str:
    m = re.search(r"<Timelines>.*</Timelines>", text, re.DOTALL)
    return m.group(0) if m else ""


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FSD3 Skin Studio — .xui + .xur")
        self.geometry("1400x860")
        self.source: SkinSource | None = None
        self.folder: str | None = None
        self.scenes: list[tuple[str, str]] = []  # (rel, kind)
        self.current: str = ""
        self.current_kind: str = ""
        self.root_node: Node | None = None
        self.base_root: Node | None = None
        self.visuals: dict[str, Node] = {}
        self.timelines = None
        self.timelines_block = ""
        self.xur_info: dict | None = None
        self.time = 0.0
        self.playing = False
        self.selected_id = ""
        self.bg_override = ""
        self.cli_path = tk.StringVar(value="")
        self._id_map: dict[str, list[Node]] = {}  # built once per scene
        self._tl_touched: list = []  # (node, prop, saved_value_or_None)
        self._cfg_after: str | None = None  # resize debounce handle
        self.renderer = Renderer(read_image=self._read_image)
        self._drag_start: tuple[int, int] | None = None
        self._build_ui()

    def _read_image(self, rel: str) -> bytes | None:
        if self.source is None:
            return None
        try:
            return self.source.read(rel)
        except (FileNotFoundError, KeyError, OSError):
            return None

    # -- UI -------------------------------------------------------------
    def _build_ui(self):
        tb = ttk.Frame(self)
        tb.pack(fill="x", padx=6, pady=4)
        for label, cmd in [
            ("Open folder…", self.open_folder),
            ("Open .xzp…", self.open_xzp),
            ("Extract .xzp…", self.extract_xzp),
            ("New skin…", self.new_skin_wizard),
            ("Save scene", self.save_scene),
            ("Pack .xzp…", self.pack_xzp),
            ("Validate", self.do_validate),
        ]:
            ttk.Button(tb, text=label, command=cmd).pack(side="left", padx=2)
        self.dirty_lbl = ttk.Label(tb, text="")
        self.dirty_lbl.pack(side="right")

        mid = ttk.Frame(self)
        mid.pack(fill="both", expand=True, padx=6)

        left = ttk.Frame(mid, width=230)
        left.pack(side="left", fill="y", padx=(0, 6))
        ttk.Label(left, text="Scenes (.xui full / [xur] preview)").pack(anchor="w")
        self.scene_box = tk.Listbox(left, height=20, width=32)
        self.scene_box.pack(fill="y", expand=True)
        self.scene_box.bind("<<ListboxSelect>>", lambda _e: self._on_scene_pick())
        row = ttk.Frame(left)
        row.pack(fill="x", pady=4)
        ttk.Button(row, text="New scene…", command=self.new_scene_dlg).pack(side="left")
        ttk.Button(row, text="Add control…", command=self.add_control_dlg).pack(side="left", padx=2)
        ttk.Label(left, text="Backdrop").pack(anchor="w", pady=(6, 0))
        self.bg_var = tk.StringVar()
        self.bg_combo = ttk.Combobox(left, textvariable=self.bg_var, width=30)
        self.bg_combo.pack(fill="x")
        self.bg_combo.bind("<<ComboboxSelected>>", lambda _e: self._refresh())
        ttk.Label(left, text="Skin info").pack(anchor="w", pady=(6, 0))
        self.info_txt = tk.Text(left, height=8, width=32)
        self.info_txt.pack(fill="x")

        center = ttk.Frame(mid)
        center.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(center, bg="#0c0c12", width=960, height=540,
                                highlightthickness=1, highlightbackground="#333")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", lambda _e: self._refresh())
        tl = ttk.Frame(center)
        tl.pack(fill="x", pady=4)
        ttk.Label(tl, text="Timeline").pack(side="left")
        self.time_var = tk.DoubleVar(value=0)
        self.time_slider = ttk.Scale(tl, from_=0, to=80, variable=self.time_var,
                                     command=lambda _v: self._on_scrub())
        self.time_slider.pack(side="left", fill="x", expand=True, padx=6)
        self.time_lbl = ttk.Label(tl, text="t=0")
        self.time_lbl.pack(side="left")
        ttk.Button(tl, text="▶ Play", command=self._toggle_play).pack(side="left", padx=4)
        self.status = tk.Text(center, height=5)
        self.status.pack(fill="x")

        right = ttk.Frame(mid, width=300)
        right.pack(side="right", fill="y", padx=(6, 0))
        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True)
        tab_edit = ttk.Frame(nb)
        tab_credits = ttk.Frame(nb)
        nb.add(tab_edit, text="Editor")
        nb.add(tab_credits, text="Credits")
        self._build_credits_tab(tab_credits)
        ttk.Label(tab_edit, text="XUR tools (compiled scenes)").pack(anchor="w")
        xrow = ttk.Frame(tab_edit)
        xrow.pack(fill="x", pady=2)
        ttk.Entry(xrow, textvariable=self.cli_path, width=22).pack(side="left", fill="x", expand=True)
        ttk.Button(xrow, text="CLI…", command=self.pick_cli, width=6).pack(side="left", padx=2)
        ttk.Button(tab_edit, text="Decompile current .xur → .xui",
                   command=self.decompile_current).pack(fill="x", pady=2)
        ttk.Label(tab_edit, text="XUIHelper.CLI conv -s in.xur -f xuiv12 -o out.xui -g V5|V8. "
                              "Or decompile manually in XDK XuiTool.",
                  wraplength=280, foreground="#666").pack()
        ttk.Label(tab_edit, text="Selected control").pack(anchor="w", pady=(6, 0))
        self.prop_rows: dict[str, tk.StringVar] = {}
        form = ttk.Frame(tab_edit)
        form.pack(fill="x")
        for key in ["Id", "Position", "Width", "Height", "Text", "TextColor",
                    "PointSize", "ImagePath", "Visual", "Opacity", "ClassOverride"]:
            r = ttk.Frame(form)
            r.pack(fill="x", pady=1)
            ttk.Label(r, text=key, width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(r, textvariable=var, width=24).pack(side="left", fill="x", expand=True)
            self.prop_rows[key] = var
        brow = ttk.Frame(tab_edit)
        brow.pack(fill="x", pady=6)
        ttk.Button(brow, text="Apply", command=self.apply_props).pack(side="left")
        ttk.Button(brow, text="Delete", command=self.delete_selected).pack(side="left", padx=4)
        ttk.Label(tab_edit, text="Skin.xml (name/author/version)").pack(anchor="w")
        self.skin_rows: dict[str, tk.StringVar] = {}
        sform = ttk.Frame(tab_edit)
        sform.pack(fill="x")
        for key in ["name", "author", "version"]:
            r = ttk.Frame(sform)
            r.pack(fill="x", pady=1)
            ttk.Label(r, text=key, width=14).pack(side="left")
            var = tk.StringVar()
            ttk.Entry(r, textvariable=var, width=24).pack(side="left", fill="x", expand=True)
            self.skin_rows[key] = var
        ttk.Button(tab_edit, text="Apply skin info", command=self.apply_skin_info).pack(pady=4)
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, _ev=None) -> None:
        # resize storms fire dozens of events/sec; one deferred redraw
        if self._cfg_after is not None:
            try:
                self.after_cancel(self._cfg_after)
            except Exception:
                pass
        self._cfg_after = self.after(120, self._refresh)

    def _build_credits_tab(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="FSD3 Skin Studio",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=8, pady=(8, 0))
        ttk.Label(parent, text="Create + render FreeStyleDash 3 skins (.xui + .xur).",
                  wraplength=260).pack(anchor="w", padx=8)
        ttk.Separator(parent).pack(fill="x", padx=8, pady=8)
        ttk.Label(parent, text="Developer",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8)
        ttk.Label(parent, text="StoicDemon",
                  font=("Segoe UI", 12, "bold"), foreground="#ffb300").pack(anchor="w", padx=8)
        ttk.Label(parent, text="Design & development — skin engine research, "
                               "viewer, creator, and XUR tooling.",
                  wraplength=260).pack(anchor="w", padx=8)
        ttk.Separator(parent).pack(fill="x", padx=8, pady=8)
        ttk.Label(parent, text="Built with",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=8)
        for line in [
            "Python + Tkinter + Pillow",
            "XUR conversion: XUIHelper by SGCSam (GPL-3.0)",
            "XUI format: Microsoft XDK XuiTool",
            "Dash: FreeStyleDash 3 by Team FSD",
        ]:
            ttk.Label(parent, text="•  " + line, wraplength=250).pack(anchor="w", padx=8)

    # -- logging ----------------------------------------------------------
    def say(self, msg: str):
        self.status.insert("end", msg + "\n")
        self.status.see("end")

    # -- open / load ------------------------------------------------------
    def open_folder(self):
        d = filedialog.askdirectory(title="Open extracted skin folder")
        if d:
            self._load(SkinSource(d), folder=d)

    def open_xzp(self):
        f = filedialog.askopenfilename(title="Open skin .xzp (incl. retail default.xzp)",
                                       filetypes=[("FSD skins", "*.xzp"), ("All", "*.*")])
        if f:
            self._load(SkinSource(f), folder=None)

    def extract_xzp(self):
        f = filedialog.askopenfilename(title="Pick .xzp to extract",
                                       filetypes=[("FSD skins", "*.xzp")])
        if not f:
            return
        dest = filedialog.askdirectory(title="Extract into folder…")
        if not dest:
            return
        try:
            from .xzp import read_xzp as _rx
        except ImportError:
            from xzp import read_xzp as _rx  # type: ignore
        files = _rx(f)
        for rel, data in files.items():
            out = os.path.join(dest, rel.replace("\\", os.sep))
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with open(out, "wb") as fh:
                fh.write(data)
        self.say(f"extracted {len(files)} files -> {dest}")
        self._load(SkinSource(dest), folder=dest)

    def _load(self, source: SkinSource, folder: str | None):
        self.source = source
        self.folder = folder
        try:
            info = source.info()
        except Exception as e:
            messagebox.showerror("Open", f"Could not read skin:\n{e}")
            return
        xui, xur = info["scenes_xui"], info["scenes_xur"]
        bgs = info.get("backgrounds", [])
        self.bg_combo["values"] = ["(scene default)"] + [
            f"{b['label']} :: {b['path']}" for b in bgs]
        self.bg_combo.current(0)
        self.bg_override = ""
        self.info_txt.delete("1.0", "end")
        self.info_txt.insert("end",
                             f"{info.get('name','?')}  {info.get('author','')}  {info.get('version','')}\n"
                             f".xui: {len(xui)}  .xur: {len(xur)}  backgrounds: {len(bgs)}\n")
        for m in info.get("menus", []):
            self.info_txt.insert("end", "menu: " + m.get("text", "") + "\n")
        if info.get("error"):
            self.info_txt.insert("end", info["error"] + "\n")
        if not xui and xur:
            self.info_txt.insert("end", "retail .xur-only skin: [xur] preview; "
                                        "decompile for full render.\n")
        self.skin_rows["name"].set(info.get("name", ""))
        self.skin_rows["author"].set(info.get("author", ""))
        self.skin_rows["version"].set(info.get("version", ""))
        self.visuals = {}
        try:
            self.visuals = parse_visuals(source.read("skin.xui").decode("utf-8", "replace"))
        except (FileNotFoundError, KeyError, OSError):
            pass
        self.scenes = [(s, "xui") for s in xui] + [(s, "xur") for s in xur
                                                   if s[:-4] + ".xui" not in xui]
        self.scene_box.delete(0, "end")
        for rel, kind in self.scenes:
            self.scene_box.insert("end", rel + ("  [xur]" if kind == "xur" else ""))
        self.renderer.clear()
        if self.scenes:
            idx = next((i for i, (r, _k) in enumerate(self.scenes) if r == "main.xui"), 0)
            self.scene_box.selection_set(idx)
            self._load_scene(*self.scenes[idx])
        self.say(f"opened {'xzp' if source.is_xzp else 'folder'}: {source.path} "
                 f"({len(xui)} xui, {len(xur)} xur, {len(self.visuals)} visuals)")
        self.dirty_lbl.configure(text="")

    def _on_scene_pick(self):
        sel = self.scene_box.curselection()
        if sel:
            self._load_scene(*self.scenes[sel[0]])

    def _load_scene(self, rel: str, kind: str):
        assert self.source is not None
        self.current, self.current_kind = rel, kind
        self.selected_id = ""
        self.time = 0.0
        self.time_var.set(0)
        if kind == "xur":
            try:
                self.xur_info = parse_xur(self.source.read(rel))
            except Exception as e:
                self.say(f"{rel}: XUR parse failed: {e}")
                return
            self.root_node = self.base_root = None
            self.timelines = None
            self.time_slider.configure(to=1)
            self._refresh()
            n = len(self.xur_info["controls"])
            self.say(f"{rel}: XUR v{self.xur_info['version']} preview "
                     f"(~{n} named entries, {len(self.xur_info['strings'])} strings) — "
                     f"decompile for pixel-exact render")
            return
        try:
            text = self.source.read(rel).decode("utf-8", "replace")
        except (FileNotFoundError, KeyError, OSError) as e:
            self.say(f"cannot read {rel}: {e}")
            return
        self.timelines_block = _extract_timelines_block(text)
        try:
            base = parse_xui(text)
        except ET.ParseError as e:
            self.say(f"{rel}: XML error: {e}")
            return
        expand_visuals(base, self.visuals)
        self.base_root = base
        self.root_node = base
        self.timelines = parse_timelines(text)
        self._reindex_scene()
        self.time_slider.configure(to=max(1, self.timelines.duration))
        self._refresh()
        self.say(f"{rel}: full render ({len(self.timelines.tracks)} tracks, "
                 f"{len(self.timelines.frames)} named frames)")

    def _reindex_scene(self) -> None:
        """Rebuild id-map + timeline snapshot after load or structural edit."""
        self._id_map = build_id_map(self.base_root) if self.base_root else {}
        self._tl_touched = []
        if self.base_root is None or self.timelines is None:
            return
        seen: set[tuple[int, str]] = set()
        for track in self.timelines.tracks:
            for node in self._id_map.get(track.target_id, []):
                key = (id(node), track.prop)
                if key not in seen:
                    seen.add(key)
                    saved = node.props.get(track.prop)
                    self._tl_touched.append((node, track.prop, saved))

    def _restore_pristine(self) -> None:
        """Undo timeline evaluation so the tree holds authored values."""
        for node, prop, saved in self._tl_touched:
            if saved is None:
                node.props.pop(prop, None)
            else:
                node.props[prop] = saved

    # -- render -----------------------------------------------------------
    def _refresh(self):
        if self.current_kind == "xur":
            if self.xur_info is None:
                return
            cw = max(200, self.canvas.winfo_width())
            ch = max(200, self.canvas.winfo_height())
            self.renderer.render_xur(self.canvas, self.xur_info, self.current,
                                     scale=min(cw / CANON_W, ch / CANON_H))
            self._show_props()
            return
        if self.base_root is None:
            return
        # restore pristine props, then evaluate timelines in place —
        # no per-frame deepcopy or tree walk (id-map built once per scene)
        self._restore_pristine()
        if self.timelines is not None:
            apply_timelines(self.base_root, self.timelines, self.time, self._id_map)
        bg = None
        if self.bg_override:
            bg = Node(tag="XuiImage",
                      props={"Id": "BackdropOverride", "Width": "1280",
                             "Height": "720", "Position": "0,0,0",
                             "ImagePath": self.bg_override})
            self.base_root.children.insert(0, bg)
        try:
            cw = max(200, self.canvas.winfo_width())
            ch = max(200, self.canvas.winfo_height())
            self.renderer.render(self.canvas, self.base_root,
                                 scale=min(cw / CANON_W, ch / CANON_H),
                                 select_id=self.selected_id)
        finally:
            if bg is not None:
                self.base_root.children.remove(bg)
        self.time_lbl.configure(text=f"t={self.time:.1f}")
        self._show_props()

    def _on_scrub(self):
        self.time = float(self.time_var.get())
        self._refresh()

    def _toggle_play(self):
        self.playing = not self.playing
        if self.playing:
            self._tick()

    def _tick(self):
        if not self.playing or self.timelines is None:
            return
        dur = max(1.0, self.timelines.duration)
        self.time = (self.time + 1.0) % (dur + 1.0)
        self.time_var.set(self.time)
        self._refresh()
        self.after(90, self._tick)

    # -- selection / editing (.xui only) ------------------------------------
    def _hit(self, x: int, y: int) -> Node | None:
        best, best_area = None, None
        for _iid, node, (x0, y0, x1, y1) in self.renderer.items:
            if x0 <= x <= x1 and y0 <= y <= y1:
                area = abs(x1 - x0) * abs(y1 - y0)
                if best is None or area < best_area:
                    best, best_area = node, area
        return best

    def _on_click(self, ev):
        if self.current_kind != "xui":
            return
        node = self._hit(ev.x, ev.y)
        if node is not None and node.id:
            self.selected_id = node.id
            self._drag_start = (ev.x, ev.y)
            self._refresh()

    def _on_drag(self, ev):
        if self.current_kind != "xui" or not self.selected_id or self.base_root is None:
            return
        if not self._drag_start:
            return
        sx, sy = self._drag_start
        cw = max(200, self.canvas.winfo_width())
        scale = min(cw / CANON_W, max(200, self.canvas.winfo_height()) / CANON_H)
        dx, dy = (ev.x - sx) / (scale or 1), (ev.y - sy) / (scale or 1)
        if abs(dx) < 2 and abs(dy) < 2:
            return
        node = self._find(self.base_root, self.selected_id)
        if node is not None:
            x, y, z = _parse_pos(node.props.get("Position"))
            node.props["Position"] = f"{x + dx:.3f},{y + dy:.3f},{z:.3f}"
            self._drag_start = (ev.x, ev.y)
            self.dirty_lbl.configure(text="● unsaved")
            self._refresh()

    def _find(self, root: Node, nid: str) -> Node | None:
        if root.id == nid:
            return root
        for c in root.children:
            hit = self._find(c, nid)
            if hit:
                return hit
        return None

    def _show_props(self):
        node = self._find(self.base_root, self.selected_id) if self.base_root else None
        for key, var in self.prop_rows.items():
            var.set(node.props.get(key, "") if node is not None else "")

    def apply_props(self):
        if self.base_root is None or not self.selected_id or self.current_kind != "xui":
            return
        node = self._find(self.base_root, self.selected_id)
        if node is None:
            return
        for key, var in self.prop_rows.items():
            v = var.get().strip()
            if v:
                node.props[key] = v
            elif key in node.props:
                del node.props[key]
        self.selected_id = node.props.get("Id", self.selected_id)
        self._reindex_scene()
        self.dirty_lbl.configure(text="● unsaved")
        self._refresh()
        self.say(f"edited {self.selected_id}")

    def delete_selected(self):
        if self.base_root is None or not self.selected_id or self.current_kind != "xui":
            return
        if self._remove(self.base_root, self.selected_id):
            self.say(f"deleted {self.selected_id}")
            self.selected_id = ""
            self._reindex_scene()
            self.dirty_lbl.configure(text="● unsaved")
            self._refresh()

    def _remove(self, parent: Node, nid: str) -> bool:
        for i, c in enumerate(parent.children):
            if c.id == nid:
                del parent.children[i]
                return True
            if self._remove(c, nid):
                return True
        return False

    # -- XUR tools ----------------------------------------------------------
    def pick_cli(self):
        f = filedialog.askopenfilename(title="Pick XUIHelper.CLI.exe",
                                       filetypes=[("Exe", "*.exe"), ("All", "*.*")])
        if f:
            self.cli_path.set(f)

    def decompile_current(self):
        if self.current_kind != "xur" or self.source is None:
            messagebox.showinfo("Decompile", "Select an [xur] scene first.")
            return
        cli = self.cli_path.get().strip()
        if not cli:
            messagebox.showinfo("Decompile", "Pick XUIHelper.CLI.exe first (CLI… button). "
                                            "Or decompile manually in XDK XuiTool.")
            return
        import tempfile
        tmp = tempfile.mkdtemp(prefix="fsd3xur_")
        src_tmp = os.path.join(tmp, os.path.basename(self.current))
        with open(src_tmp, "wb") as fh:
            fh.write(self.source.read(self.current))
        group = version_group(self.xur_info["version"] if self.xur_info else 5)
        out = os.path.join(tmp, os.path.basename(self.current)[:-4] + ".xui")
        ok, log = decompile_with_xuihelper(src_tmp, out, cli, group)
        self.say(log)
        if not ok:
            messagebox.showerror("Decompile", "XUIHelper failed — see log.")
            return
        with open(out, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        try:
            base = parse_xui(text)
        except ET.ParseError as e:
            messagebox.showerror("Decompile", f"Decompiled XUI won't parse: {e}")
            return
        expand_visuals(base, self.visuals)
        self.base_root = base
        self.timelines = parse_timelines(text)
        self.timelines_block = _extract_timelines_block(text)
        self._reindex_scene()
        self.current_kind = "xui (decompiled)"
        self.time_slider.configure(to=max(1, self.timelines.duration))
        self._refresh()
        self.say(f"decompiled {self.current} -> full render "
                 f"({len(self.timelines.tracks)} tracks)")
        if self.folder is not None:
            save = messagebox.askyesno("Decompile", "Save decompiled .xui next to the skin?")
            if save:
                dest = os.path.join(self.folder, os.path.basename(self.current)[:-4] + ".xui")
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.say(f"saved {dest}")

    # -- creation -----------------------------------------------------------
    def new_skin_wizard(self):
        dlg = tk.Toplevel(self)
        dlg.title("New skin")
        dlg.geometry("360x260")
        vars_ = {k: tk.StringVar(value=v) for k, v in
                 [("name", "MySkin"), ("author", ""), ("version", "1.0")]}
        for k in ("name", "author", "version"):
            r = ttk.Frame(dlg)
            r.pack(fill="x", padx=8, pady=4)
            ttk.Label(r, text=k, width=10).pack(side="left")
            ttk.Entry(r, textvariable=vars_[k]).pack(side="left", fill="x", expand=True)

        def go():
            parent = filedialog.askdirectory(title="Pick PARENT folder for new skin")
            if not parent:
                return
            dest = os.path.join(parent, vars_["name"].get().strip() or "MySkin")
            create_skin(dest, vars_["name"].get(), vars_["author"].get(), vars_["version"].get())
            dlg.destroy()
            self._load(SkinSource(dest), folder=dest)

        ttk.Button(dlg, text="Create", command=go).pack(pady=10)

    def new_scene_dlg(self):
        if self.source is None or self.folder is None:
            messagebox.showinfo("New scene", "Open (or create) a skin FOLDER first — "
                                            ".xzp files are read-only.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("New scene")
        name_v, sid_v, cls_v = (tk.StringVar(value=v) for v in
                                ("settings.xui", "SettingsMain", "ScnOptionsMain"))
        for label, var in [("file", name_v), ("scene Id", sid_v), ("ClassOverride", cls_v)]:
            r = ttk.Frame(dlg)
            r.pack(fill="x", padx=8, pady=4)
            ttk.Label(r, text=label, width=14).pack(side="left")
            ttk.Entry(r, textvariable=var).pack(side="left", fill="x", expand=True)

        def go():
            fn = name_v.get().strip() or "settings.xui"
            with open(os.path.join(self.folder, fn), "w", encoding="utf-8") as fh:
                fh.write(new_scene(fn.replace(".xui", ""), sid_v.get(), cls_v.get()))
            dlg.destroy()
            self._load(SkinSource(self.folder), folder=self.folder)

        ttk.Button(dlg, text="Create", command=go).pack(pady=10)

    def add_control_dlg(self):
        if self.base_root is None or self.current_kind != "xui":
            messagebox.showinfo("Add control", "Open a .xui scene first (not [xur]).")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add control")
        kind_v, id_v = tk.StringVar(value="XuiButton"), tk.StringVar(value="NewButton")
        ttk.Label(dlg, text="Kind").pack(anchor="w", padx=8)
        ttk.Combobox(dlg, textvariable=kind_v, values=CONTROL_KINDS).pack(fill="x", padx=8)
        ttk.Label(dlg, text="Id").pack(anchor="w", padx=8)
        ttk.Entry(dlg, textvariable=id_v).pack(fill="x", padx=8)

        def go():
            kind, cid = kind_v.get(), id_v.get().strip() or "Control"
            try:
                el = ET.fromstring(control_xml(kind, cid))
            except ET.ParseError:
                return
            host = self.base_root
            assert host is not None
            for c in host.children:
                if c.tag in ("XuiScene", "XuiTabScene"):
                    host = c
                    break
            host.children.append(_xui_build(el))
            self.selected_id = cid
            self._reindex_scene()
            self.dirty_lbl.configure(text="● unsaved")
            dlg.destroy()
            self._refresh()
            self.say(f"added {kind} {cid}")

        ttk.Button(dlg, text="Add", command=go).pack(pady=10)

    # -- save / pack / validate ----------------------------------------------
    def save_scene(self):
        if self.base_root is None or self.source is None or self.current_kind != "xui":
            messagebox.showinfo("Save", "Open a .xui scene from a folder first.")
            return
        if self.folder is None:
            messagebox.showinfo("Save", "Opened from .xzp (read-only). Extract first.")
            return
        self._restore_pristine()  # never persist timeline-evaluated values
        xml = ET.tostring(_node_to_etree(self.base_root), encoding="unicode")
        self._refresh()  # re-apply current time for the canvas
        if self.timelines_block:
            if "</XuiTabScene>" in xml:
                xml = xml.replace("</XuiTabScene>", self.timelines_block + "</XuiTabScene>", 1)
            elif "</XuiScene>" in xml:
                xml = xml.replace("</XuiScene>", self.timelines_block + "</XuiScene>", 1)
            else:
                xml += self.timelines_block
        out = os.path.join(self.folder, self.current)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(xml)
        self.say(f"saved {self.current}")
        self.dirty_lbl.configure(text="")

    def apply_skin_info(self):
        if self.source is None or self.folder is None:
            messagebox.showinfo("skin.xml", "Open a skin folder first (.xzp is read-only).")
            return
        try:
            root = ET.fromstring(self.source.read("skin.xml").decode("utf-8", "replace"))
            sk = root.find("./settings/Skin")
            if sk is not None:
                sk.text = self.skin_rows["name"].get()
            for tag, key in (("Author", "author"), ("Version", "version")):
                el = root.find("./settings/" + tag)
                if el is None:
                    el = ET.SubElement(root.find("./settings"), tag)
                el.text = self.skin_rows[key].get()
            with open(os.path.join(self.folder, "skin.xml"), "w", encoding="utf-8") as fh:
                fh.write(ET.tostring(root, encoding="unicode"))
            self.say("skin.xml updated")
            self.dirty_lbl.configure(text="● unsaved")
        except Exception as e:
            messagebox.showerror("skin.xml", str(e))

    def pack_xzp(self):
        folder = self.folder or filedialog.askdirectory(title="Pick skin folder to pack")
        if not folder:
            return
        out = filedialog.asksaveasfilename(title="Save .xzp as", defaultextension=".xzp",
                                           filetypes=[("FSD skins", "*.xzp")])
        if not out:
            return
        count, total = write_xzp(folder, out)
        self.say(f"packed {count} files ({total} bytes) -> {out}")

    def do_validate(self):
        folder = self.folder or (None if self.source is None or self.source.is_xzp
                                 else self.source.path)
        if not folder:
            messagebox.showinfo("Validate", "Open a skin folder first.")
            return
        problems = validate_skin(folder)
        if not problems:
            messagebox.showinfo("Validate", "Skin looks valid.")
            self.say("validate: OK")
        else:
            self.say("validate:\n- " + "\n- ".join(problems))
            messagebox.showwarning("Validate", "\n".join(problems[:20]))


def main():
    Studio().mainloop()


if __name__ == "__main__":
    main()
