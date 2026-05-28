#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="codex-discord-bridge.service"

cd "$REPO_DIR"

if [ ! -f ".env" ]; then
  echo "Missing .env. Copy .env.example to .env and fill it before installing."
  exit 1
fi

if [ ! -d ".venv" ]; then
  uv venv
fi
uv pip install -e '.[dev]'

mkdir -p "$SERVICE_DIR"
sed "s|%h/repositories/codex-discord-bridge|$REPO_DIR|g; s|%h|$HOME|g" \
  "$REPO_DIR/systemd/$SERVICE_NAME" > "$SERVICE_DIR/$SERVICE_NAME"

systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

echo "Started $SERVICE_NAME"
echo "Logs: journalctl --user -u $SERVICE_NAME -f"
