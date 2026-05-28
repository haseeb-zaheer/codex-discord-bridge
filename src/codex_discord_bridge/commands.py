from __future__ import annotations

import shlex
from dataclasses import dataclass
from enum import Enum


class CommandKind(str, Enum):
    NEW = "new"
    LIST = "list"
    USE = "use"
    STOP = "stop"
    STATUS = "status"
    CWD = "cwd"
    MODEL = "model"
    CANCEL = "cancel"
    RETRY = "retry"
    FOLDERS = "folders"
    HELP = "help"
    MESSAGE = "message"


@dataclass(frozen=True)
class Command:
    kind: CommandKind
    args: tuple[str, ...] = ()
    prompt: str = ""


HELP_TEXT = """Codex bridge commands:
codex -new <folder> [initial prompt]
codex -list
codex -use <session-id-or-alias>
codex -stop <session-id-or-alias>
codex -status
codex -cwd
codex -model <model>
codex -cancel
codex -retry
codex -folders [prefix]
codex -help

Slash aliases:
/plan [topic]
/status
/model <model>
/cancel
/help

Any other DM is sent to the active Codex session."""

PLAN_PROMPT_PREFIX = """Enter text-only planning mode for Discord.

Important constraints:
- Do not edit files or run mutating commands yet.
- Do not use interactive UI prompts, numbered choice widgets, or terminal-only controls.
- If you need input, ask the questions directly in plain text and wait for my next Discord message.
- Produce a concrete implementation plan that can be executed later.

Planning request:"""


def parse_command(content: str) -> Command:
    text = content.strip()
    if not text:
        return Command(CommandKind.MESSAGE, prompt="")

    if text.startswith("/"):
        return _parse_slash_command(text)

    if not text.lower().startswith("codex "):
        return Command(CommandKind.MESSAGE, prompt=text)

    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"Could not parse command: {exc}") from exc

    if len(parts) == 1:
        return Command(CommandKind.HELP)

    flag = parts[1].lower()
    rest = tuple(parts[2:])

    mapping = {
        "-new": CommandKind.NEW,
        "-list": CommandKind.LIST,
        "-use": CommandKind.USE,
        "-stop": CommandKind.STOP,
        "-status": CommandKind.STATUS,
        "-cwd": CommandKind.CWD,
        "-model": CommandKind.MODEL,
        "-cancel": CommandKind.CANCEL,
        "-retry": CommandKind.RETRY,
        "-folders": CommandKind.FOLDERS,
        "-help": CommandKind.HELP,
        "--help": CommandKind.HELP,
    }
    kind = mapping.get(flag)
    if kind is None:
        return Command(CommandKind.MESSAGE, prompt=text)

    if kind is CommandKind.NEW:
        if not rest:
            raise ValueError("Usage: codex -new <folder> [initial prompt]")
        folder = rest[0]
        prompt = " ".join(rest[1:]).strip()
        return Command(kind, args=(folder,), prompt=prompt)

    if kind in {CommandKind.USE, CommandKind.STOP, CommandKind.MODEL}:
        if len(rest) != 1:
            raise ValueError(f"Usage: codex {flag} <value>")
        return Command(kind, args=(rest[0],))

    if kind is CommandKind.FOLDERS:
        if len(rest) > 1:
            raise ValueError("Usage: codex -folders [prefix]")
        return Command(kind, args=rest)

    if rest:
        raise ValueError(f"codex {flag} does not accept extra arguments")

    return Command(kind)


def _parse_slash_command(text: str) -> Command:
    try:
        parts = shlex.split(text)
    except ValueError as exc:
        raise ValueError(f"Could not parse command: {exc}") from exc

    command = parts[0].lower()
    rest = tuple(parts[1:])

    if command == "/plan":
        topic = " ".join(rest).strip() or "Make a plan for the current task."
        return Command(CommandKind.MESSAGE, prompt=f"{PLAN_PROMPT_PREFIX}\n{topic}")
    if command == "/status":
        if rest:
            raise ValueError("Usage: /status")
        return Command(CommandKind.STATUS)
    if command == "/model":
        if len(rest) != 1:
            raise ValueError("Usage: /model <model>")
        return Command(CommandKind.MODEL, args=(rest[0],))
    if command == "/cancel":
        if rest:
            raise ValueError("Usage: /cancel")
        return Command(CommandKind.CANCEL)
    if command == "/help":
        if rest:
            raise ValueError("Usage: /help")
        return Command(CommandKind.HELP)

    return Command(CommandKind.MESSAGE, prompt=text)
