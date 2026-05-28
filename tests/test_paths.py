from pathlib import Path

import pytest

from codex_discord_bridge.paths import PathValidationError, resolve_allowed_folder


def test_resolves_child_folder(tmp_path: Path) -> None:
    child = tmp_path / "repo"
    child.mkdir()

    assert resolve_allowed_folder(tmp_path, "repo") == child.resolve()


def test_rejects_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(PathValidationError):
        resolve_allowed_folder(tmp_path, "missing")


def test_rejects_traversal(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-for-codex-bridge-test"
    outside.mkdir(exist_ok=True)

    with pytest.raises(PathValidationError):
        resolve_allowed_folder(tmp_path, f"../{outside.name}")


def test_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-symlink-codex-bridge-test"
    outside.mkdir(exist_ok=True)
    link = tmp_path / "link"
    link.symlink_to(outside, target_is_directory=True)

    with pytest.raises(PathValidationError):
        resolve_allowed_folder(tmp_path, "link")
