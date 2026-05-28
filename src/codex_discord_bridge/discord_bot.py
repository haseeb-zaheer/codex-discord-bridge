from __future__ import annotations

import asyncio
import time
from pathlib import Path

import discord

from .codex_runner import CodexRunner
from .commands import Command, CommandKind, HELP_TEXT, parse_command
from .config import Config
from .paths import PathValidationError, resolve_allowed_folder
from .state import Session, StateStore

DISCORD_LIMIT = 2000
BRIDGE_LIMIT = 1800


class CodexDiscordBot(discord.Client):
    def __init__(self, config: Config, store: StateStore, runner: CodexRunner) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.config = config
        self.store = store
        self.runner = runner
        self._locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._active_processes: dict[tuple[int, int], asyncio.subprocess.Process] = {}

    async def on_ready(self) -> None:
        print(f"Codex Discord bridge ready as {self.user}")

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user or message.author.bot:
            return
        if message.guild is not None:
            return
        if message.author.id not in self.config.allowed_user_ids:
            return

        try:
            command = parse_command(message.content)
        except ValueError as exc:
            await send_chunks(message.channel, f"{exc}\n\n{HELP_TEXT}")
            return

        key = (message.author.id, message.channel.id)
        if command.kind is CommandKind.CANCEL:
            await self._cancel(message, key)
            return

        lock = self._locks.setdefault(key, asyncio.Lock())
        if lock.locked():
            await message.channel.send("A Codex turn is already running. Send `codex -cancel` to stop it.")
            return

        async with lock:
            await self._handle(message, command, key)

    async def _handle(
        self,
        message: discord.Message,
        command: Command,
        key: tuple[int, int],
    ) -> None:
        if command.kind is CommandKind.HELP:
            await send_chunks(message.channel, HELP_TEXT)
            return
        if command.kind is CommandKind.NEW:
            await self._new_session(message, command, key)
            return
        if command.kind is CommandKind.MESSAGE:
            await self._send_to_active(message, command.prompt, key)
            return
        if command.kind is CommandKind.LIST:
            await self._list_sessions(message)
            return
        if command.kind is CommandKind.USE:
            await self._use_session(message, command.args[0])
            return
        if command.kind is CommandKind.STOP:
            await self._stop_session(message, command.args[0])
            return
        if command.kind is CommandKind.STATUS:
            await self._status(message)
            return
        if command.kind is CommandKind.CWD:
            await self._cwd(message)
            return
        if command.kind is CommandKind.MODEL:
            await self._model(message, command.args[0])
            return
        if command.kind is CommandKind.RETRY:
            await self._retry(message, key)
            return
        if command.kind is CommandKind.FOLDERS:
            await self._folders(message, command)
            return

    async def _new_session(
        self,
        message: discord.Message,
        command: Command,
        key: tuple[int, int],
    ) -> None:
        try:
            cwd = resolve_allowed_folder(self.config.root, command.args[0])
        except PathValidationError as exc:
            await message.channel.send(str(exc))
            return

        prompt = command.prompt or "Start a new Codex session here. Inspect the folder briefly and report status."
        model = self.config.default_model
        alias = make_alias(cwd)
        await message.channel.send(f"Starting Codex in `{cwd}`...")
        result = await self._run_new(message, key, cwd, prompt, model)
        self.store.upsert_session(
            session_id=result.session_id,
            alias=alias,
            user_id=message.author.id,
            channel_id=message.channel.id,
            cwd=cwd,
            model=model,
            status="idle" if result.ok else "error",
            last_prompt=prompt,
            last_error=None if result.ok else result.stderr or result.final_message,
            log_path=result.log_path,
        )
        self.store.set_active(message.author.id, message.channel.id, result.session_id)
        header = f"Active session `{short_id(result.session_id)}` as `{alias}`."
        await send_chunks(message.channel, format_result(header, result.final_message, result.log_path, result.ok))

    async def _send_to_active(
        self,
        message: discord.Message,
        prompt: str,
        key: tuple[int, int],
    ) -> None:
        if not prompt:
            await send_chunks(message.channel, HELP_TEXT)
            return
        session = self.store.get_active(message.author.id, message.channel.id)
        if not session:
            await message.channel.send("No active session. Start one with `codex -new <folder>`.")
            return
        result = await self._run_resume(message, key, session, prompt)
        self.store.upsert_session(
            session_id=session.id,
            alias=session.alias,
            user_id=session.user_id,
            channel_id=session.channel_id,
            cwd=Path(session.cwd),
            model=session.model,
            status="idle" if result.ok else "error",
            last_prompt=prompt,
            last_error=None if result.ok else result.stderr or result.final_message,
            log_path=result.log_path,
        )
        await send_chunks(message.channel, format_result("", result.final_message, result.log_path, result.ok))

    async def _run_new(self, message: discord.Message, key: tuple[int, int], cwd: Path, prompt: str, model: str | None):
        proc, log_path = await self.runner.start(cwd=cwd, prompt=prompt, model=model)
        self._active_processes[key] = proc
        try:
            return await self.runner.collect(proc, log_path=log_path)
        finally:
            self._active_processes.pop(key, None)

    async def _run_resume(
        self,
        message: discord.Message,
        key: tuple[int, int],
        session: Session,
        prompt: str,
    ):
        self.store.set_status(session.id, "running")
        proc, log_path = await self.runner.resume(
            session_id=session.id,
            prompt=prompt,
            model=session.model,
        )
        self._active_processes[key] = proc
        try:
            return await self.runner.collect(proc, log_path=log_path, fallback_session_id=session.id)
        finally:
            self._active_processes.pop(key, None)

    async def _list_sessions(self, message: discord.Message) -> None:
        sessions = self.store.list_sessions(message.author.id)
        if not sessions:
            await message.channel.send("No sessions yet.")
            return
        lines = ["Recent Codex sessions:"]
        for session in sessions:
            marker = "*"
            lines.append(
                f"{marker} `{short_id(session.id)}` `{session.alias}` {session.status} `{session.cwd}`"
            )
        await send_chunks(message.channel, "\n".join(lines))

    async def _use_session(self, message: discord.Message, identifier: str) -> None:
        session = self.store.find_session(message.author.id, identifier)
        if not session:
            await message.channel.send(f"No session found for `{identifier}`.")
            return
        self.store.set_active(message.author.id, message.channel.id, session.id)
        await message.channel.send(f"Active session is now `{short_id(session.id)}` in `{session.cwd}`.")

    async def _stop_session(self, message: discord.Message, identifier: str) -> None:
        session = self.store.find_session(message.author.id, identifier)
        if not session:
            await message.channel.send(f"No session found for `{identifier}`.")
            return
        self.store.set_status(session.id, "stopped")
        await message.channel.send(f"Marked `{short_id(session.id)}` stopped.")

    async def _status(self, message: discord.Message) -> None:
        session = self.store.get_active(message.author.id, message.channel.id)
        if not session:
            await message.channel.send("No active session.")
            return
        await message.channel.send(
            f"Active `{short_id(session.id)}` `{session.alias}`: {session.status}\n"
            f"CWD: `{session.cwd}`\n"
            f"Model: `{session.model or 'default'}`"
        )

    async def _cwd(self, message: discord.Message) -> None:
        session = self.store.get_active(message.author.id, message.channel.id)
        await message.channel.send(f"`{session.cwd}`" if session else "No active session.")

    async def _model(self, message: discord.Message, model: str) -> None:
        session = self.store.get_active(message.author.id, message.channel.id)
        if not session:
            await message.channel.send("No active session.")
            return
        self.store.set_model(session.id, model)
        await message.channel.send(f"Model for `{short_id(session.id)}` set to `{model}`.")

    async def _retry(self, message: discord.Message, key: tuple[int, int]) -> None:
        session = self.store.get_active(message.author.id, message.channel.id)
        if not session or not session.last_prompt:
            await message.channel.send("No previous prompt to retry.")
            return
        await self._send_to_active(message, session.last_prompt, key)

    async def _folders(self, message: discord.Message, command: Command) -> None:
        prefix = command.args[0] if command.args else ""
        try:
            base = self.config.root if not prefix else resolve_allowed_folder(self.config.root, prefix)
        except PathValidationError as exc:
            await message.channel.send(str(exc))
            return

        folders = sorted(path for path in base.iterdir() if path.is_dir())
        if not folders:
            await message.channel.send(f"No folders found under `{relative_display(self.config.root, base)}`.")
            return

        lines = [f"Folders under `{relative_display(self.config.root, base)}`:"]
        for folder in folders[:50]:
            lines.append(f"`{relative_display(self.config.root, folder)}`")
        if len(folders) > 50:
            lines.append(f"...and {len(folders) - 50} more. Narrow with `codex -folders <prefix>`.")
        await send_chunks(message.channel, "\n".join(lines))

    async def _cancel(self, message: discord.Message, key: tuple[int, int]) -> None:
        proc = self._active_processes.get(key)
        if not proc:
            await message.channel.send("No Codex process is currently running.")
            return
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
        session = self.store.get_active(message.author.id, message.channel.id)
        if session:
            self.store.set_status(session.id, "cancelled")
        await message.channel.send("Cancelled the running Codex process.")


async def send_chunks(channel: discord.abc.Messageable, text: str) -> None:
    if not text:
        text = "(no output)"
    while text:
        chunk = text[:BRIDGE_LIMIT]
        text = text[BRIDGE_LIMIT:]
        await channel.send(chunk)


def format_result(header: str, body: str, log_path: Path, ok: bool) -> str:
    status = "" if ok else "Codex exited with an error.\n"
    pieces = [part for part in [header, status + (body or "(no output)")] if part]
    result = "\n\n".join(pieces)
    if len(result) > 3500:
        result = result[:3500] + f"\n\nOutput truncated. Full log: `{log_path}`"
    return result


def make_alias(cwd: Path) -> str:
    return f"{cwd.name}-{int(time.time())}"


def short_id(session_id: str) -> str:
    return session_id[:8]


def relative_display(root: Path, path: Path) -> str:
    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError:
        return str(path)
    return "." if str(relative) == "." else str(relative)
