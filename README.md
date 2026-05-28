# Codex Discord Bridge

DM-only Discord bridge for running local Codex CLI sessions on this machine.

## What It Does

- Accepts Discord DMs only from configured user ids.
- Starts Codex in folders under `CODEX_BRIDGE_ROOT`.
- Continues sessions with `codex exec resume`.
- Lets Codex run autonomously inside the selected folder using `workspace-write` and approval policy `never`.
- Stores local session state in SQLite.

## Setup

```bash
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

The Discord bot needs the Message Content intent enabled in the Discord Developer Portal.

## Run Locally

```bash
uv run codex-discord-bridge
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

Any other DM is sent to the active Codex session.

Example:

```text
codex -new example-project inspect the repo and make a plan
```

## systemd User Service

Install and start:

```bash
./scripts/install_user_service.sh
```

Check logs:

```bash
journalctl --user -u codex-discord-bridge -f
```

Restart:

```bash
systemctl --user restart codex-discord-bridge
```

## Safety Notes

This bot is effectively remote control for local Codex. Keep it DM-only, restrict
`DISCORD_ALLOWED_USER_IDS`, and keep `CODEX_BRIDGE_ROOT` narrow.
