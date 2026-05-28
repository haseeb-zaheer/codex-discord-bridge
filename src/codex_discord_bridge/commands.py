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

Any other DM is sent to the active Codex session."""


def parse_command(content: str) -> Command:
    text = content.strip()
    if not text:
        return Command(CommandKind.MESSAGE, prompt="")

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
