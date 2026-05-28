import pytest

from codex_discord_bridge.commands import CommandKind, parse_command


def test_parse_new_with_prompt() -> None:
    command = parse_command("codex -new haseeb-web/site inspect this")

    assert command.kind is CommandKind.NEW
    assert command.args == ("haseeb-web/site",)
    assert command.prompt == "inspect this"


def test_parse_quoted_folder() -> None:
    command = parse_command('codex -new "folder with spaces" hello')

    assert command.kind is CommandKind.NEW
    assert command.args == ("folder with spaces",)
    assert command.prompt == "hello"


def test_non_command_is_message() -> None:
    command = parse_command("implement the fix")

    assert command.kind is CommandKind.MESSAGE
    assert command.prompt == "implement the fix"


def test_parse_folders_without_prefix() -> None:
    command = parse_command("codex -folders")

    assert command.kind is CommandKind.FOLDERS
    assert command.args == ()


def test_parse_folders_with_prefix() -> None:
    command = parse_command("codex -folders haseeb-web")

    assert command.kind is CommandKind.FOLDERS
    assert command.args == ("haseeb-web",)


def test_parse_rejects_extra_args() -> None:
    with pytest.raises(ValueError):
        parse_command("codex -status now")


def test_parse_folders_rejects_too_many_args() -> None:
    with pytest.raises(ValueError):
        parse_command("codex -folders one two")
