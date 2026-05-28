from pathlib import Path

from codex_discord_bridge.discord_bot import relative_display


def test_relative_display_root(tmp_path: Path) -> None:
    assert relative_display(tmp_path, tmp_path) == "."


def test_relative_display_child(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()

    assert relative_display(tmp_path, child) == "child"
