from pathlib import Path

from codex_discord_bridge.discord_bot import ProgressMessenger, relative_display


def test_relative_display_root(tmp_path: Path) -> None:
    assert relative_display(tmp_path, tmp_path) == "."


def test_relative_display_child(tmp_path: Path) -> None:
    child = tmp_path / "child"
    child.mkdir()

    assert relative_display(tmp_path, child) == "child"


class FakeChannel:
    def __init__(self) -> None:
        self.messages: list[str] = []

    async def send(self, text: str) -> None:
        self.messages.append(text)


async def test_progress_messenger_sends_important_messages_immediately() -> None:
    channel = FakeChannel()
    messenger = ProgressMessenger(channel, clock=lambda: 0.0)

    await messenger.send("Running: `pytest`")

    assert channel.messages == ["Running: `pytest`"]


async def test_progress_messenger_throttles_non_important_messages() -> None:
    times = iter([0.0, 1.0, 5.0])
    channel = FakeChannel()
    messenger = ProgressMessenger(channel, interval_seconds=4.0, clock=lambda: next(times))

    await messenger.send("Plan progress: 0/2 done.")
    await messenger.send("Plan progress: 1/2 done.")
    await messenger.send("Plan progress: 2/2 done.")

    assert channel.messages == ["Plan progress: 2/2 done."]
