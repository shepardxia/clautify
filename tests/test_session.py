"""Session-level tests: error handling, WS reconnect, setup/config.

Resolution, dispatch, and parser shape are tested in test_dsl_v4.py.
The session fixture lives in conftest.py.
"""

from unittest.mock import MagicMock

import pytest

from clautify.dsl import SpotifySession
from clautify.dsl.executor import DSLError
from clautify.exceptions import WebSocketError

# ── Smoke tests ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "cmd, expected_action",
    [
        ("pause", "pause"),
        ("resume", "resume"),
        ("skip 3", "skip"),
        ("queue track 6rqhFgbbKwnb9MLmUQDhG6", "queue"),
    ],
)
def test_simple_actions(session, cmd, expected_action):
    r = session.run(cmd)
    assert r["status"] == "ok"
    assert r["action"] == expected_action


def test_play_with_context(session):
    mock_song = session._mocks["Song"].return_value
    mock_song.query_songs.return_value = {
        "data": {
            "searchV2": {"playlists": {"items": [{"data": {"name": "My Playlist", "uri": "spotify:playlist:pl123"}}]}}
        }
    }
    r = session.run('play track 6rqhFgbbKwnb9MLmUQDhG6 in playlist "My Playlist"')
    assert r["status"] == "ok"
    assert r["context"] == "My Playlist"


# ── State modifiers ─────────────────────────────────────────────────


def test_volume(session):
    r = session.run("volume 70")
    assert r["status"] == "ok"
    assert r["volume"] == 70.0


def test_volume_out_of_range(session):
    with pytest.raises(DSLError, match="Volume must be 0-100"):
        session.run("volume 150")


def test_mode(session):
    r = session.run("mode shuffle")
    assert r["status"] == "ok"
    assert r["mode"] == "shuffle"


def test_device_transfer(session):
    r = session.run('device "Den"')
    assert r["status"] == "ok"
    assert r["device"] == "Den"


def test_device_not_found(session):
    with pytest.raises(DSLError, match="not found"):
        session.run('device "Garage"')


# ── Queries ─────────────────────────────────────────────────────────


def test_search(session):
    mock_song = session._mocks["Song"].return_value
    mock_song.query_songs.return_value = {"data": {"searchV2": {"tracksV2": {"items": []}}}}
    r = session.run('search track "jazz"')
    assert r["status"] == "ok"
    assert r["query"] == "search"
    assert r["kind"] == "track"


# ── Error handling ──────────────────────────────────────────────────


def test_invalid_command(session):
    with pytest.raises(DSLError, match="Invalid command"):
        session.run("explode everything")


def test_unknown_action(session):
    with pytest.raises(DSLError, match="Unknown action"):
        session._executor.execute({"action": "explode"})


def test_exception_wraps_as_dsl_error(session):
    player = session._mocks["Player"].return_value
    player.pause.side_effect = RuntimeError("connection lost")
    with pytest.raises(DSLError, match="connection lost"):
        session.run("pause")


# ── WebSocket reconnect ────────────────────────────────────────────


def test_ws_error_retries_and_succeeds(session):
    player = session._mocks["Player"].return_value
    call_count = 0

    def pause_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise WebSocketError("disconnected")

    player.pause.side_effect = pause_side_effect
    r = session.run("pause")
    assert r["status"] == "ok"
    assert call_count == 2  # first failed, second succeeded


def test_ws_error_both_attempts_raises(session):
    player = session._mocks["Player"].return_value
    player.pause.side_effect = WebSocketError("dead")
    with pytest.raises(DSLError):
        session.run("pause")


def test_non_ws_error_no_retry(session):
    player = session._mocks["Player"].return_value
    player.pause.side_effect = DSLError("bad state")
    with pytest.raises(DSLError, match="bad state"):
        session.run("pause")


# ── Session setup ───────────────────────────────────────────────────


def test_setup_creates_file(tmp_path):
    import json

    dest = tmp_path / "session.json"
    SpotifySession.setup("FAKE_SP_DC", path=dest)
    assert dest.exists()
    assert json.loads(dest.read_text())["cookies"]["sp_dc"] == "FAKE_SP_DC"


def test_setup_empty_raises():
    with pytest.raises(DSLError, match="sp_dc cookie value is required"):
        SpotifySession.setup("")


def test_from_config_missing_file(tmp_path):
    with pytest.raises(DSLError, match="No session file found"):
        SpotifySession.from_config(path=tmp_path / "nope.json")
