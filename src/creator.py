# Copyright (c) 2026 StoicDemon - MIT License, see LICENSE.
"""Skin creation: scaffold, scene templates, save, validate."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

SKIN_XML_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<skin>
  <fonts>
    <font default="true" file="Font\\arial.ttf" name="SkinFont"></font>
  </fonts>
  <settings>
    <Skin Min='2' Max='9999'>{name}</Skin>
    <Author>{author}</Author>
    <Version>{version}</Version>
    <displayFPS>FALSE</displayFPS>
  </settings>
  <Backgrounds>
    <default>{default_bg}</default>
{backgrounds}  </Backgrounds>
</skin>
"""

SCENE_TEMPLATE = """<XuiCanvas version="000c">
<Properties>
<Width>1280.000000</Width>
<Height>720.000000</Height>
</Properties>
<XuiScene>
<Properties>
<Id>{scene_id}</Id>
<Width>1280.000000</Width>
<Height>720.000000</Height>
<ClassOverride>{class_override}</ClassOverride>
</Properties>
{body}</XuiScene>
</XuiCanvas>
"""

VISUALS_TEMPLATE = """<XuiCanvas version="000c">
<Properties>
<Width>1280.000000</Width>
<Height>720.000000</Height>
</Properties>
<XuiVisual>
<Properties>
<Id>Button_Simple</Id>
<Width>12.000000</Width>
<Height>44.000000</Height>
</Properties>
</XuiVisual>
<XuiVisual>
<Properties>
<Id>RowSelected</Id>
<Width>460.000000</Width>
<Height>44.000000</Height>
</Properties>
<XuiImage>
<Properties>
<Id>RowBackground</Id>
<Width>460.000000</Width>
<Height>44.000000</Height>
<SizeMode>4</SizeMode>
<ImagePath>{row_image}</ImagePath>
</Properties>
</XuiImage>
</XuiVisual>
</XuiCanvas>
"""


def _f(v) -> str:
    return f"{float(v):.6f}"


def control_xml(kind: str, cid: str, x: float = 60, y: float = 110,
                w: float = 380, h: float = 40, text: str = "",
                color: str = "0xffffffff", size: int = 15,
                image: str = "", visual: str = "") -> str:
    pos = f"<Position>{_f(x)},{_f(y)},0.000000</Position>"
    wh = f"<Width>{_f(w)}</Width>\n<Height>{_f(h)}</Height>"
    head = f"<{kind}>\n<Properties>\n<Id>{cid}</Id>\n{wh}\n{pos}\n"
    tail = "</Properties>\n</" + kind + ">\n"
    if kind in ("XuiText", "XuiTextPresenter"):
        return (head + f"<Text>{text}</Text>\n<TextColor>{color}</TextColor>\n"
                f"<PointSize>{_f(size)}</PointSize>\n" + tail)
    if kind == "XuiImage":
        return head + f"<SizeMode>4</SizeMode>\n<ImagePath>{image}</ImagePath>\n" + tail
    if kind in ("XuiButton", "XuiNavButton"):
        vis = f"<Visual>{visual}</Visual>\n" if visual else ""
        return head + vis + f"<Text>{text or cid}</Text>\n" + tail
    if kind in ("XuiList", "XuiListBox"):
        return head + "<ClipChildren>true</ClipChildren>\n" + tail
    return head + tail


CONTROL_KINDS = ["XuiButton", "XuiText", "XuiImage", "XuiList",
                 "XuiSlider", "XuiEdit", "XuiControl", "XuiGroup"]


def create_skin(folder: str, name: str = "MySkin", author: str = "",
                version: str = "1.0",
                backgrounds: list[tuple[str, str]] | None = None) -> str:
    os.makedirs(folder, exist_ok=True)
    os.makedirs(os.path.join(folder, "Images"), exist_ok=True)
    backgrounds = backgrounds or [("Default", "Images\\Background.png")]
    bg_xml = "".join(f'    <background label="{l}">{p}</background>\n' for l, p in backgrounds)
    with open(os.path.join(folder, "skin.xml"), "w", encoding="utf-8") as fh:
        fh.write(SKIN_XML_TEMPLATE.format(name=name, author=author, version=version,
                                          default_bg=backgrounds[0][1], backgrounds=bg_xml))
    with open(os.path.join(folder, "skin.xui"), "w", encoding="utf-8") as fh:
        fh.write(VISUALS_TEMPLATE.format(row_image="Images\\RowSelected.png"))
    body = (control_xml("XuiText", "Title", 60, 40, 600, 44, name, "0xfff2f2f2", 30)
            + control_xml("XuiList", "GameList", 60, 110, 560, 480)
            + control_xml("XuiButton", "Back", 60, 610, 200, 40, "Back"))
    with open(os.path.join(folder, "main.xui"), "w", encoding="utf-8") as fh:
        fh.write(SCENE_TEMPLATE.format(scene_id="Main", class_override="ScnMain", body=body))
    return os.path.abspath(folder)


def new_scene(title: str = "Scene", scene_id: str = "Main",
              class_override: str = "ScnMain") -> str:
    body = (control_xml("XuiText", "Title", 60, 40, 600, 44, title, "0xfff2f2f2", 28)
            + control_xml("XuiList", "SettingList", 60, 110, 560, 480)
            + control_xml("XuiButton", "Back", 60, 610, 200, 40, "Back"))
    return SCENE_TEMPLATE.format(scene_id=scene_id, class_override=class_override, body=body)


def validate_skin(folder: str) -> list[str]:
    problems: list[str] = []
    sx = os.path.join(folder, "skin.xml")
    if not os.path.isfile(sx):
        return ["missing skin.xml"]
    try:
        root = ET.parse(sx).getroot()
        sk = root.find("./settings/Skin")
        if sk is None or not (sk.text or "").strip():
            problems.append("skin.xml: <Skin> name is empty")
        for bg in root.findall("./Backgrounds/background"):
            p = (bg.text or "").strip()
            if p and not os.path.isfile(os.path.join(folder, p.replace("\\", os.sep))):
                problems.append(f"background missing: {p} (label={bg.get('label','')})")
    except ET.ParseError as e:
        problems.append(f"skin.xml parse error: {e}")
    xui = [f for f in os.listdir(folder) if f.lower().endswith(".xui")]
    xur = [f for f in os.listdir(folder) if f.lower().endswith(".xur")]
    if not xui and not xur:
        problems.append("no scenes (need .xui source or .xur compiled)")
    elif not xui:
        problems.append(f".xur-only skin ({len(xur)} scenes): decompile to .xui for full render")
    for fn in xui:
        try:
            root = ET.parse(os.path.join(folder, fn)).getroot()
        except ET.ParseError as e:
            problems.append(f"{fn}: XML error: {e}")
            continue
        for img in root.findall(".//ImagePath"):
            p = (img.text or "").strip()
            if p and not os.path.isfile(os.path.join(folder, p.replace("\\", os.sep))):
                problems.append(f"{fn}: image missing: {p}")
    return problems
