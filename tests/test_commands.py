import pytest

from codex_discord_bridge.commands import CommandKind, PLAN_PROMPT_PREFIX, parse_command


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


def test_parse_slash_plan_as_text_only_prompt() -> None:
    command = parse_command("/plan add retry limits")

    assert command.kind is CommandKind.MESSAGE
    assert command.prompt.startswith(PLAN_PROMPT_PREFIX)
    assert "add retry limits" in command.prompt
    assert "Do not use interactive UI prompts" in command.prompt


def test_parse_slash_status_as_bridge_status() -> None:
    command = parse_command("/status")

    assert command.kind is CommandKind.STATUS


def test_parse_slash_model_as_bridge_model() -> None:
    command = parse_command("/model gpt-5")

    assert command.kind is CommandKind.MODEL
    assert command.args == ("gpt-5",)


def test_unknown_slash_command_is_message() -> None:
    command = parse_command("/unknown keep going")

    assert command.kind is CommandKind.MESSAGE
    assert command.prompt == "/unknown keep going"
