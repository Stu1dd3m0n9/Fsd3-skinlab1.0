from src.xui import (parse_xui, parse_visuals, parse_timelines,
                      eval_timeline, apply_timelines, expand_visuals,
                      build_id_map)


SAMPLE = """<XuiCanvas version="000c">
<Properties><Width>1280.000000</Width><Height>720.000000</Height></Properties>
<XuiTabScene>
<Properties><Id>MainLoop</Id><Width>1280.000000</Width><Height>720.000000</Height></Properties>
<XuiScene>
<Properties><Id>Tab0</Id><Width>256.000000</Width><Height>96.000000</Height>
<Position>400.000000,330.000000,120.000000</Position></Properties>
<XuiControl><Properties><Id>XboxTile</Id><Visual>LoopRingTile</Visual></Properties></XuiControl>
</XuiScene>
<Timelines>
<NamedFrames><NamedFrame><Name>ShowTab0</Name><Time>0</Time></NamedFrame></NamedFrames>
<Timeline><Id>Tab0</Id><TimelineProp>Position</TimelineProp>
<KeyFrame><Time>0</Time><Interpolation>0</Interpolation><Prop>400.000000,330.000000,120.000000</Prop></KeyFrame>
<KeyFrame><Time>16</Time><Interpolation>2</Interpolation><Prop>499.000000,204.000000,40.000000</Prop></KeyFrame>
</Timeline>
</Timelines>
</XuiTabScene>
</XuiCanvas>"""

VISUALS = """<XuiCanvas version="000c">
<Properties><Width>1280.000000</Width><Height>720.000000</Height></Properties>
<XuiVisual><Properties><Id>LoopRingTile</Id><Width>256.000000</Width><Height>96.000000</Height></Properties>
<XuiImage><Properties><Id>TileBackground</Id><Width>256.000000</Width><Height>96.000000</Height>
<ImagePath>Images\\Tile.png</ImagePath></Properties></XuiImage>
</XuiVisual>
</XuiCanvas>"""


def test_parse_scene():
    root = parse_xui(SAMPLE)
    assert root.tag == "XuiCanvas"
    assert any(c.tag == "XuiTabScene" for c in root.children)


def test_visual_expansion():
    root = parse_xui(SAMPLE)
    expand_visuals(root, parse_visuals(VISUALS))

    def walk(n):
        if n.id == "XboxTile":
            found.append(n)
        for c in n.children:
            walk(c)

    found: list = []
    walk(root)
    assert found and len(found[0].children) >= 1


def test_timeline_eval_and_apply():
    ts = parse_timelines(SAMPLE)
    assert len(ts.tracks) == 1 and ts.tracks[0].target_id == "Tab0"
    assert "400" in eval_timeline(ts.tracks[0], 0)
    assert "499" in eval_timeline(ts.tracks[0], 16)
    assert "400" not in eval_timeline(ts.tracks[0], 8).replace("499", "X")
    root = parse_xui(SAMPLE)
    apply_timelines(root, ts, 16.0)

    def find(n, nid):
        if n.id == nid:
            return n
        for c in n.children:
            hit = find(c, nid)
            if hit:
                return hit
        return None

    assert "499" in find(root, "Tab0").props["Position"]


def test_id_map_apply_matches_full_walk():
    import copy
    ts = parse_timelines(SAMPLE)
    a = parse_xui(SAMPLE)
    b = copy.deepcopy(a)
    apply_timelines(a, ts, 8.0)
    apply_timelines(b, ts, 8.0, build_id_map(b))

    def dump(n):
        return (n.id, dict(n.props), [dump(c) for c in n.children])

    assert dump(a) == dump(b)
