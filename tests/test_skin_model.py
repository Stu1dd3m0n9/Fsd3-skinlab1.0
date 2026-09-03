from src.skin_model import SkinSource


def test_skin_source_lists_xui_and_xur(tmp_path):
    d = tmp_path / "skin"
    d.mkdir()
    (d / "skin.xml").write_text(
        "<skin><settings><Skin>Test</Skin></settings></skin>", encoding="utf-8")
    (d / "main.xui").write_text("<XuiCanvas/>", encoding="utf-8")
    (d / "main.xur").write_bytes(b"XUIB\x00\x00\x00\x05")
    src = SkinSource(str(d))
    assert src.list_xui() == ["main.xui"]
    assert src.list_xur() == ["main.xur"]
    assert src.info()["name"] == "Test"
