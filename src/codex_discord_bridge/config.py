from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _parse_user_ids(value: str) -> set[int]:
    ids: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return ids


@dataclass(frozen=True)
class Config:
    discord_token: str
    allowed_user_ids: set[int]
    root: Path
    db_path: Path
    log_dir: Path
    codex_bin: str
    sandbox: str
    approval_policy: str
    default_model: str | None

    @classmethod
    def load(cls, cwd: Path | None = None) -> "Config":
        base = cwd or Path.cwd()
        _load_env_file(base / ".env")

        discord_token_value = os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN")
        if not discord_token_value:
            raise RuntimeError("DISCORD_TOKEN is required")

        allowed_raw = os.environ.get("DISCORD_ALLOWED_USER_IDS", "")
        allowed_user_ids = _parse_user_ids(allowed_raw)
        if not allowed_user_ids:
            raise RuntimeError("DISCORD_ALLOWED_USER_IDS must contain at least one Discord user id")

        root = Path(os.environ.get("CODEX_BRIDGE_ROOT", "~/repositories")).expanduser()
        db_path = Path(os.environ.get("CODEX_BRIDGE_DB", "./codex_bridge.db")).expanduser()
        log_dir = Path(os.environ.get("CODEX_BRIDGE_LOG_DIR", "./logs")).expanduser()
        default_model = os.environ.get("CODEX_DEFAULT_MODEL") or None

        return cls(
            discord_token=discord_token_value,
            allowed_user_ids=allowed_user_ids,
            root=root.resolve(),
            db_path=(base / db_path).resolve() if not db_path.is_absolute() else db_path.resolve(),
            log_dir=(base / log_dir).resolve() if not log_dir.is_absolute() else log_dir.resolve(),
            codex_bin=os.environ.get("CODEX_BIN", "codex"),
            sandbox=os.environ.get("CODEX_SANDBOX", "workspace-write"),
            approval_policy=os.environ.get("CODEX_APPROVAL_POLICY", "never"),
            default_model=default_model,
        )
