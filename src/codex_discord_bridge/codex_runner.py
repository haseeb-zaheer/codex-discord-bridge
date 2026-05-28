from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable, Iterable

UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CodexRunResult:
    session_id: str
    final_message: str
    returncode: int
    log_path: Path
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


ProgressCallback = Callable[[str], Awaitable[None]]


class CodexRunner:
    def __init__(
        self,
        *,
        codex_bin: str,
        sandbox: str,
        approval_policy: str,
        log_dir: Path,
    ) -> None:
        self.codex_bin = codex_bin
        self.sandbox = sandbox
        self.approval_policy = approval_policy
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def start(
        self,
        *,
        cwd: Path,
        prompt: str,
        model: str | None,
    ) -> tuple[asyncio.subprocess.Process, Path]:
        session_hint = uuid.uuid4().hex[:12]
        log_path = self.log_dir / f"codex-{session_hint}.jsonl"
        cmd = build_start_command(
            codex_bin=self.codex_bin,
            cwd=cwd,
            sandbox=self.sandbox,
            approval_policy=self.approval_policy,
            model=model,
            prompt=prompt or "Start a new Codex session in this folder. Reply with a brief status.",
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return proc, log_path

    async def resume(
        self,
        *,
        session_id: str,
        prompt: str,
        model: str | None,
    ) -> tuple[asyncio.subprocess.Process, Path]:
        log_path = self.log_dir / f"codex-{session_id[:12]}-{uuid.uuid4().hex[:8]}.jsonl"
        cmd = build_resume_command(
            codex_bin=self.codex_bin,
            session_id=session_id,
            approval_policy=self.approval_policy,
            model=model,
            prompt=prompt,
        )
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        return proc, log_path

    async def collect(
        self,
        proc: asyncio.subprocess.Process,
        *,
        log_path: Path,
        fallback_session_id: str | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> CodexRunResult:
        raw_lines: list[str] = []
        stderr_task = (
            asyncio.create_task(proc.stderr.read())
            if proc.stderr is not None
            else None
        )
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log_file:
            if proc.stdout is not None:
                while True:
                    raw_line = await proc.stdout.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode(errors="replace").rstrip("\n")
                    raw_lines.append(line)
                    log_file.write(line + "\n")
                    log_file.flush()
                    if on_progress:
                        progress = progress_message_from_line(line)
                        if progress:
                            await on_progress(progress)

            await proc.wait()

        stderr_bytes = await stderr_task if stderr_task is not None else b""
        stderr_text = stderr_bytes.decode(errors="replace").strip()
        session_id = fallback_session_id or _extract_session_id(raw_lines) or uuid.uuid4().hex
        final_message = _extract_final_message(raw_lines)
        if not final_message and stderr_text:
            final_message = stderr_text
        return CodexRunResult(
            session_id=session_id,
            final_message=final_message.strip(),
            returncode=proc.returncode or 0,
            log_path=log_path,
            stderr=stderr_text,
        )


def build_start_command(
    *,
    codex_bin: str,
    cwd: Path,
    sandbox: str,
    approval_policy: str,
    model: str | None,
    prompt: str,
) -> list[str]:
    cmd = [
        codex_bin,
        "exec",
        "-C",
        str(cwd),
        "--sandbox",
        sandbox,
        "-c",
        f'approval_policy="{approval_policy}"',
        "--json",
    ]
    if model:
        cmd.extend(["-m", model])
    cmd.append(prompt)
    return cmd


def build_resume_command(
    *,
    codex_bin: str,
    session_id: str,
    approval_policy: str,
    model: str | None,
    prompt: str,
) -> list[str]:
    cmd = [
        codex_bin,
        "exec",
        "resume",
        "-c",
        f'approval_policy="{approval_policy}"',
        "--json",
    ]
    if model:
        cmd.extend(["-m", model])
    cmd.append(session_id)
    cmd.append(prompt)
    return cmd


def progress_message_from_line(line: str) -> str | None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        return None

    event_type = event.get("type")
    if event_type == "turn.started":
        return "Codex turn started."
    if event_type == "thread.started":
        thread_id = event.get("thread_id")
        return f"Session `{str(thread_id)[:8]}` connected." if thread_id else "Session connected."

    item = event.get("item")
    if not isinstance(item, dict):
        return None

    item_type = item.get("type")
    if item_type == "todo_list":
        return _todo_progress(item)
    if item_type == "command_execution":
        command = item.get("command") or item.get("cmd")
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)
        if isinstance(command, str) and command.strip():
            return f"Running: `{_shorten(command.strip(), 180)}`"
    if item_type == "file_change":
        path = item.get("path") or item.get("file")
        if isinstance(path, str) and path.strip():
            return f"Editing: `{_shorten(path.strip(), 180)}`"
        return "Editing files."
    if item_type == "agent_message":
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return _brief_agent_update(text)

    return None


def _todo_progress(item: dict) -> str | None:
    items = item.get("items")
    if not isinstance(items, list) or not items:
        return None
    completed = sum(1 for todo in items if isinstance(todo, dict) and todo.get("completed"))
    total = len(items)
    first_open = next(
        (
            todo.get("text")
            for todo in items
            if isinstance(todo, dict) and not todo.get("completed") and isinstance(todo.get("text"), str)
        ),
        None,
    )
    if first_open:
        return f"Plan progress: {completed}/{total} done. Next: {_shorten(first_open, 140)}"
    return f"Plan progress: {completed}/{total} done."


def _brief_agent_update(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    first_line = next((line.strip() for line in stripped.splitlines() if line.strip()), "")
    if not first_line:
        return None
    if len(stripped) > 700:
        return f"Codex update: {_shorten(first_line, 180)}"
    return None


def _shorten(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _extract_session_id(lines: Iterable[str]) -> str | None:
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            match = UUID_RE.search(line)
            if match:
                return match.group(0)
            continue
        found = _find_uuid(event)
        if found:
            return found
    return None


def _find_uuid(value: object) -> str | None:
    if isinstance(value, str):
        match = UUID_RE.search(value)
        return match.group(0) if match else None
    if isinstance(value, dict):
        for key in ("session_id", "conversation_id", "id", "thread_id"):
            found = _find_uuid(value.get(key))
            if found:
                return found
        for nested in value.values():
            found = _find_uuid(nested)
            if found:
                return found
    if isinstance(value, list):
        for item in value:
            found = _find_uuid(item)
            if found:
                return found
    return None


def _extract_final_message(lines: Iterable[str]) -> str:
    candidates: list[str] = []
    for line in lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            if line.strip():
                candidates.append(line.strip())
            continue
        text = _event_text(event)
        if text:
            candidates.append(text)
    return candidates[-1] if candidates else ""


def _event_text(event: object) -> str | None:
    if not isinstance(event, dict):
        return None
    for key in ("message", "content", "text", "final_message", "output"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    item = event.get("item")
    if isinstance(item, dict):
        return _event_text(item)
    return None
