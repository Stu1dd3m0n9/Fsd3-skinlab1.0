import struct

from src.xur import parse_xur


def _fake_xur() -> bytes:
    strs = ["XuiCanvas", "XuiButton", "MyButton", "Hello",
            "Images\\Btn.png", "XuiText", "Title"]
    blob = b"XUIB" + struct.pack(">I", 5) + b"STRN" + struct.pack(">I", 0)
    for s in strs:
        blob += s.encode("utf-16-le") + b"\x00\x00"
    return blob


def test_parse_xur_strings_and_controls():
    info = parse_xur(_fake_xur())
    assert info["version"] == 5
    assert "XuiButton" in info["strings"]
    classes = [c["class"] for c in info["controls"]]
    assert "XuiButton" in classes and "XuiText" in classes
    btn = next(c for c in info["controls"] if c["class"] == "XuiButton")
    assert btn["id"] == "MyButton"
    assert any("Btn.png" in p for p in info["images"])


def test_parse_xur_rejects_bad_magic():
    import pytest
    with pytest.raises(ValueError):
        parse_xur(b"NOPE" + b"\x00" * 16)
