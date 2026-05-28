from __future__ import annotations

from pathlib import Path


class PathValidationError(ValueError):
    """Raised when a requested Codex working directory is not allowed."""


def resolve_allowed_folder(root: Path, requested: str) -> Path:
    if not requested or requested.strip() in {".", "/"}:
        raise PathValidationError("Provide a folder under the configured bridge root.")

    raw = Path(requested).expanduser()
    if raw.is_absolute():
        candidate = raw
    else:
        candidate = root / raw

    resolved_root = root.resolve()
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError as exc:
        raise PathValidationError(f"Folder does not exist: {requested}") from exc

    if not resolved.is_dir():
        raise PathValidationError(f"Not a directory: {requested}")

    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PathValidationError(
            f"Folder must be inside {resolved_root}: {requested}"
        ) from exc

    return resolved
