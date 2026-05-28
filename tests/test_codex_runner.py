from pathlib import Path

from codex_discord_bridge.codex_runner import (
    _extract_final_message,
    _extract_session_id,
    build_resume_command,
    build_start_command,
    progress_message_from_line,
)


def test_extract_session_id_from_nested_json() -> None:
    lines = [
        '{"type":"session.started","session_id":"123e4567-e89b-12d3-a456-426614174000"}',
    ]

    assert _extract_session_id(lines) == "123e4567-e89b-12d3-a456-426614174000"


def test_extract_final_message_prefers_last_text_event() -> None:
    lines = [
        '{"type":"event","message":"thinking"}',
        '{"type":"final","content":"done"}',
    ]

    assert _extract_final_message(lines) == "done"


def test_build_start_command_uses_config_approval_policy() -> None:
    command = build_start_command(
        codex_bin="codex",
        cwd=Path("/tmp/repo"),
        sandbox="workspace-write",
        approval_policy="never",
        model=None,
        prompt="hello",
    )

    assert "--ask-for-approval" not in command
    assert command == [
        "codex",
        "exec",
        "-C",
        "/tmp/repo",
        "--sandbox",
        "workspace-write",
        "-c",
        'approval_policy="never"',
        "--json",
        "hello",
    ]


def test_build_resume_command_places_options_before_prompt() -> None:
    command = build_resume_command(
        codex_bin="codex",
        session_id="123e4567-e89b-12d3-a456-426614174000",
        approval_policy="never",
        model="gpt-5",
        prompt="continue",
    )

    assert command == [
        "codex",
        "exec",
        "resume",
        "-c",
        'approval_policy="never"',
        "--json",
        "-m",
        "gpt-5",
        "123e4567-e89b-12d3-a456-426614174000",
        "continue",
    ]


def test_progress_message_from_turn_started() -> None:
    assert progress_message_from_line('{"type":"turn.started"}') == "Codex turn started."


def test_progress_message_from_todo_list() -> None:
    line = (
        '{"type":"item.started","item":{"type":"todo_list","items":['
        '{"text":"Read files","completed":true},'
        '{"text":"Run tests","completed":false}]}}'
    )

    assert progress_message_from_line(line) == "Plan progress: 1/2 done. Next: Run tests"


def test_progress_message_from_large_agent_message() -> None:
    line = '{"type":"item.completed","item":{"type":"agent_message","text":"' + ("hello " * 200) + '"}}'

    assert progress_message_from_line(line) == "Codex update: hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello hello..."
