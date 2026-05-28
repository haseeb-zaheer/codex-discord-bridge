from __future__ import annotations

from .codex_runner import CodexRunner
from .config import Config
from .discord_bot import CodexDiscordBot
from .state import StateStore


def main() -> None:
    config = Config.load()
    store = StateStore(config.db_path)
    runner = CodexRunner(
        codex_bin=config.codex_bin,
        sandbox=config.sandbox,
        approval_policy=config.approval_policy,
        log_dir=config.log_dir,
    )
    bot = CodexDiscordBot(config, store, runner)
    bot.run(config.discord_token)


if __name__ == "__main__":
    main()
