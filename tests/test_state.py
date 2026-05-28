from pathlib import Path

from codex_discord_bridge.state import StateStore


def test_state_store_tracks_active_session(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    cwd = tmp_path / "repo"
    cwd.mkdir()

    store.upsert_session(
        session_id="123e4567-e89b-12d3-a456-426614174000",
        alias="repo-1",
        user_id=1,
        channel_id=2,
        cwd=cwd,
        model=None,
    )
    store.set_active(1, 2, "123e4567-e89b-12d3-a456-426614174000")

    active = store.get_active(1, 2)

    assert active is not None
    assert active.alias == "repo-1"
    assert active.cwd == str(cwd)


def test_state_store_finds_short_id_and_updates_model(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "state.db")
    cwd = tmp_path / "repo"
    cwd.mkdir()
    session_id = "123e4567-e89b-12d3-a456-426614174000"

    store.upsert_session(
        session_id=session_id,
        alias="repo-1",
        user_id=1,
        channel_id=2,
        cwd=cwd,
        model=None,
    )
    store.set_model(session_id, "gpt-5")

    found = store.find_session(1, "123e4567")

    assert found is not None
    assert found.model == "gpt-5"
