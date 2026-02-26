"""Shared fixtures for clautify tests."""

from unittest.mock import MagicMock, patch

import pytest

from clautify.dsl import SpotifySession


def _mock_player(**overrides):
    p = MagicMock()
    p.state = MagicMock()
    p.active_id = "dev0"
    p.device_id = "dev0"
    dev = MagicMock()
    dev.volume = 32768  # ~50%
    dev.name = "Den"
    dev.device_id = "dev0"
    devices = MagicMock()
    devices.devices = {"dev0": dev}
    p.device_ids = devices
    p.next_songs_in_queue = []
    p.last_songs_played = []
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


@pytest.fixture
def session():
    login = MagicMock()
    with (
        patch("clautify.dsl.executor.Player") as P,
        patch("clautify.dsl.executor.Song") as S,
        patch("clautify.dsl.executor.Artist") as A,
        patch("clautify.dsl.executor.PrivatePlaylist") as PP,
    ):
        P.return_value = _mock_player()
        S.return_value = MagicMock()
        A.return_value = MagicMock()
        PP.return_value = MagicMock()
        s = SpotifySession(login, eager=False)
        s._mocks = {"Player": P, "Song": S, "Artist": A, "PP": PP}
        yield s
