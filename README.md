# Codex Discord Bridge

DM-only Discord bot for starting and continuing local Codex CLI sessions from Discord.

This is intended for a private, single-user workflow: you DM your bot, the bot
starts Codex in an allowed local folder, and follow-up DMs continue the active
Codex session.

## What It Does

- Accepts Discord DMs only from configured user ids.
- Starts Codex in folders under `CODEX_BRIDGE_ROOT`.
- Continues sessions with `codex exec resume`.
- Lets Codex run autonomously inside the selected folder using `workspace-write` and approval policy `never`.
- Stores local session state in SQLite.

## Requirements

- Linux host with `systemd --user` if you want the 24/7 service.
- Python 3.11+.
- [`uv`](https://docs.astral.sh/uv/) for environment and package management.
- OpenAI Codex CLI installed and authenticated on the machine.
- A Discord application with a bot token.

## Discord Bot Setup

1. Create an application at <https://discord.com/developers/applications>.
2. Open **Bot** and create/reset the bot token.
3. Enable **Message Content Intent** under privileged gateway intents.
4. Copy your Discord user id:
   - Discord settings -> Advanced -> enable Developer Mode.
   - Right-click your user profile -> Copy User ID.
5. Invite the bot to a private server once so you can DM it.

The bridge ignores server/channel messages. It only responds to DMs from
`DISCORD_ALLOWED_USER_IDS`.

## Installation

```bash
git clone <repo-url>
cd codex-discord-bridge
uv venv
uv pip install -e '.[dev]'
cp .env.example .env
```

Fill `.env`:

```bash
DISCORD_TOKEN=...
DISCORD_ALLOWED_USER_IDS=1234567890
CODEX_BRIDGE_ROOT=/path/to/allowed/workspace
```

Recommended local hardening:

```bash
chmod 600 .env
```

## Run Locally

```bash
uv run codex-discord-bridge
```

## Run 24/7 With systemd

Install and start the user service:

```bash
./scripts/install_user_service.sh
```

Check status:

```bash
systemctl --user status codex-discord-bridge
```

Follow logs:

```bash
journalctl --user -u codex-discord-bridge -f
```

Restart:

```bash
systemctl --user restart codex-discord-bridge
```

## Discord Commands

```text
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
```

Slash aliases:

```text
/plan [topic]
/status
/model <model>
/cancel
/help
```

`/plan` is handled as text-only planning mode for Discord. It asks Codex not to
use terminal-only interactive prompts and to ask follow-up questions directly in
plain text instead.

Any other DM is sent to the active Codex session.

Example:

```text
codex -new example-project inspect the repo and make a plan
```

While Codex is running, the bridge sends concise progress updates such as
session start, plan/todo progress, command execution, and file-edit notices.
The full raw Codex JSONL stream is still saved locally in `logs/`, and the
final Codex response is sent when the turn completes.

## Development

```bash
uv run --extra dev pytest
python3 -m py_compile $(find src -name '*.py' -print)
```

## Safety Notes

This bot is effectively remote control for local Codex. Keep it DM-only,
restrict `DISCORD_ALLOWED_USER_IDS`, keep `CODEX_BRIDGE_ROOT` narrow, and do
not commit `.env`, logs, or the SQLite database.

## Public Repo Workflow

Be careful when preparing changes for this repository. It is public.

- Do not work directly on `main`.
- Use a separate local `develop` branch for active changes.
- Keep `develop` local unless a change has been explicitly approved for publication.
- Before merging into `main`, run tests and perform a security/publication audit.
- Only merge `develop` into `main` after approval.
- After merging, push `main` only when the publish candidate has been reviewed.

Never force-add ignored runtime files such as `.env`, logs, SQLite databases,
local agent notes, virtualenvs, or caches.
