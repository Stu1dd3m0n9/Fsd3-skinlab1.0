# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""XUI scene parser with Visual expansion + Timeline playback.

Covers the subset FSD3 skins use: XuiCanvas / XuiScene / XuiTabScene /
XuiGroup / XuiControl, XuiButton / XuiNavButton, XuiText / XuiTextPresenter,
XuiImage, XuiList / XuiListBox, XuiSlider / XuiEdit, XuiVisual (shared
visuals in skin.xui), XuiFigure (vector polygons), Timelines.

Interpolation 0 = hold, anything else = smooth lerp between keyframes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import xml.etree.ElementTree as ET

PROP_KEYS = (
    "Id", "Width", "Height", "Position", "Opacity", "Text", "TextColor",
    "PointSize", "ImagePath", "Visual", "ClassOverride", "SizeMode",
    "ClipChildren", "TextStyle", "DropShadowColor", "DefaultFocus",
)


@dataclass
class Node:
    tag: str
    props: dict = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    figure: dict | None = None

    @property
    def id(self) -> str:
        return self.props.get("Id", "")


def _props(el: ET.Element) -> dict:
    out: dict = {}
    p = el.find("Properties")
    if p is None:
        return out
    for k in PROP_KEYS:
        e = p.find(k)
        if e is not None and e.text is not None:
            out[k] = e.text.strip()
    return out


def _parse_figure(el: ET.Element) -> dict | None:
    p = el.find("Properties")
    if p is None:
        return None
    d: dict = {"Id": "", "points": [], "fill": None, "stroke": None}
    e = p.find("Id")
    if e is not None and e.text:
        d["Id"] = e.text.strip()
    for tag in ("Fill", "Stroke"):
        sub = p.find(tag)
        if sub is not None:
            pp = sub.find("Properties")
            if pp is not None:
                for c in list(pp):
                    if c.tag in ("FillColor", "StrokeColor") and c.text:
                        d["fill" if tag == "Fill" else "stroke"] = c.text.strip()
    pts = p.find("Points")
    if pts is not None and pts.text:
        try:
            nums = [float(t) for t in pts.text.replace(",", " ").split()]
        except ValueError:
            nums = []
        for i in range(0, len(nums) - 1, 4):
            if i + 2 < len(nums):
                d["points"].append((nums[i + 1], nums[i + 2]))
        if not d["points"] and len(nums) >= 2:
            d["points"] = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]
    return d


def _build(el: ET.Element) -> Node:
    node = Node(tag=el.tag, props=_props(el))
    for child in el:
        if child.tag == "Properties":
            continue
        if child.tag == "XuiFigure":
            fig = _parse_figure(child)
            if fig:
                node.children.append(Node(tag="XuiFigure", props={"Id": fig["Id"]}, figure=fig))
            continue
        if child.tag in ("Timelines", "Timeline", "NamedFrames", "NamedFrame", "KeyFrame"):
            continue
        node.children.append(_build(child))
    return node


def parse_xui(text: str) -> Node:
    return _build(ET.fromstring(text))


def parse_visuals(skin_xui_text: str) -> dict[str, Node]:
    root = ET.fromstring(skin_xui_text)
    out: dict[str, Node] = {}
    for vis in root.findall("XuiVisual"):
        node = _build(vis)
        vid = node.props.get("Id", "")
        if vid:
            out[vid] = node
    return out


@dataclass
class KeyFrame:
    time: float
    prop: str
    interp: int = 0


@dataclass
class Timeline:
    target_id: str
    prop: str
    keys: list[KeyFrame] = field(default_factory=list)


@dataclass
class TimelineSet:
    frames: list[tuple[str, float]] = field(default_factory=list)
    tracks: list[Timeline] = field(default_factory=list)

    @property
    def duration(self) -> float:
        m = 0.0
        for t in self.tracks:
            for k in t.keys:
                m = max(m, k.time)
        for _n, tm in self.frames:
            m = max(m, tm)
        return m


def parse_timelines(text: str) -> TimelineSet:
    ts = TimelineSet()
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return ts
    for nf in root.findall(".//NamedFrame"):
        name = nf.findtext("Name") or ""
        try:
            tm = float(nf.findtext("Time") or 0)
        except ValueError:
            tm = 0.0
        if name:
            ts.frames.append((name, tm))
    for tl in root.findall(".//Timeline"):
        tid = tl.findtext("Id") or ""
        tprop = tl.findtext("TimelineProp") or ""
        if not tid or not tprop:
            continue
        track = Timeline(target_id=tid, prop=tprop)
        for kf in tl.findall("KeyFrame"):
            try:
                tm = float(kf.findtext("Time") or 0)
            except ValueError:
                tm = 0.0
            try:
                interp = int(float(kf.findtext("Interpolation") or 0))
            except ValueError:
                interp = 0
            track.keys.append(KeyFrame(time=tm, prop=(kf.findtext("Prop") or "").strip(),
                                       interp=interp))
        track.keys.sort(key=lambda k: k.time)
        ts.tracks.append(track)
    ts.frames.sort(key=lambda f: f[1])
    return ts


def _lerp(a: float, b: float, t: float) -> float:
    s = t * t * (3 - 2 * t)
    return a + (b - a) * s


def eval_timeline(track: Timeline, time: float) -> str:
    keys = track.keys
    if not keys:
        return ""
    if time <= keys[0].time:
        return keys[0].prop
    for i in range(len(keys) - 1):
        a, b = keys[i], keys[i + 1]
        if a.time <= time <= b.time:
            if a.interp == 0 and b.interp == 0:
                return a.prop
            try:
                av = [float(x) for x in a.prop.split(",")]
                bv = [float(x) for x in b.prop.split(",")]
            except ValueError:
                return a.prop
            span = (b.time - a.time) or 1.0
            t = (time - a.time) / span
            n = max(len(av), len(bv))
            av += [av[-1]] * (n - len(av))
            bv += [bv[-1]] * (n - len(bv))
            return ",".join(f"{_lerp(x, y, t):.3f}" for x, y in zip(av, bv))
    return keys[-1].prop


def build_id_map(root: Node) -> dict[str, list[Node]]:
    """Map control Id -> nodes. Build ONCE per scene; reuse every frame."""
    by_id: dict[str, list[Node]] = {}
    stack = [root]
    while stack:
        n = stack.pop()
        if n.id:
            by_id.setdefault(n.id, []).append(n)
        stack.extend(n.children)
    return by_id


def apply_timelines(root: Node, ts: TimelineSet, time: float,
                    by_id: dict[str, list[Node]] | None = None) -> None:
    if not ts.tracks:
        return
    if by_id is None:
        by_id = build_id_map(root)
    for track in ts.tracks:
        val = eval_timeline(track, time)
        for node in by_id.get(track.target_id, []):
            node.props[track.prop] = val


def expand_visuals(root: Node, visuals: dict[str, Node], depth: int = 0) -> None:
    if depth > 4:
        return
    for node in list(root.children):
        expand_visuals(node, visuals, depth + 1)
    vis = root.props.get("Visual", "")
    if vis and vis in visuals:
        for child in visuals[vis].children:
            root.children.append(_clone(child))


def _clone(node: Node) -> Node:
    return Node(tag=node.tag, props=dict(node.props),
                children=[_clone(c) for c in node.children],
                figure=dict(node.figure) if node.figure else None)
