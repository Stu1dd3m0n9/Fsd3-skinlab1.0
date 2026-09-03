import os

from src.xzp import write_xzp, read_xzp


def test_xzp_roundtrip(tmp_path):
    skin = tmp_path / "skin"
    (skin / "Settings").mkdir(parents=True)
    (skin / "skin.xml").write_text("<skin/>", encoding="utf-8")
    (skin / "main.xui").write_text("<XuiCanvas/>", encoding="utf-8")
    (skin / "main.xur").write_bytes(b"XUIB\x00\x00\x00\x05data")
    (skin / "Settings" / "MenuSettings.xml").write_text("<x/>", encoding="utf-8")
    out = str(tmp_path / "out.xzp")
    count, total = write_xzp(str(skin), out)
    assert count == 4 and total == os.path.getsize(out)
    files = read_xzp(out)
    assert "skin.xml" in files
    assert "main.xur" in files
    assert files["main.xui"] == b"<XuiCanvas/>"
