from src.creator import create_skin, validate_skin, new_scene


def test_create_and_validate(tmp_path):
    dest = str(tmp_path / "MySkin")
    create_skin(dest, "MySkin", "Me", "1.0")
    problems = validate_skin(dest)
    assert not any("missing skin.xml" in p for p in problems)
    assert not any("no scenes" in p for p in problems)
    assert any("background missing" in p for p in problems)


def test_new_scene_template():
    xml = new_scene("Settings", "SettingsMain", "ScnOptionsMain")
    assert "SettingsMain" in xml and "1280.000000" in xml
