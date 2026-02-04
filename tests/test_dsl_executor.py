"""Tests for the DSL executor — mocked SpotAPI classes, no network calls."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from spotapi.dsl.executor import SpotifyExecutor, DSLError


@pytest.fixture
def login():
    return MagicMock()


@pytest.fixture
def executor(login):
    return SpotifyExecutor(login)


# ── Lazy Initialization ──────────────────────────────────────────


class TestLazyInit:
    def test_player_not_created_on_init(self, executor):
        assert executor._player is None

    def test_song_not_created_on_init(self, executor):
        assert executor._song is None

    def test_artist_not_created_on_init(self, executor):
        assert executor._artist is None

    @patch("spotapi.dsl.executor.Player")
    def test_player_created_on_playback(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        executor.execute({"action": "pause"})

        MockPlayer.assert_called_once_with(executor._login)
        assert executor._player is mock_player

    @patch("spotapi.dsl.executor.Player")
    def test_player_created_once(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        executor.execute({"action": "pause"})
        executor.execute({"action": "resume"})

        MockPlayer.assert_called_once()

    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_search_does_not_create_player(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        mock_song.query_songs.return_value = {"data": {"searchV2": {"tracksV2": {"items": []}}}}
        MockSong.return_value = mock_song

        executor.execute({"query": "search", "term": "jazz"})

        assert executor._player is None


# ── Action Dispatch ───────────────────────────────────────────────


class TestActions:
    @patch("spotapi.dsl.executor.Player")
    def test_pause(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "pause"})

        mock_player.pause.assert_called_once()
        assert result["status"] == "ok"
        assert result["action"] == "pause"

    @patch("spotapi.dsl.executor.Player")
    def test_resume(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "resume"})

        mock_player.resume.assert_called_once()
        assert result["status"] == "ok"

    @patch("spotapi.dsl.executor.Player")
    def test_skip_forward(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "skip", "n": 3})

        assert mock_player.skip_next.call_count == 3
        assert result["n"] == 3

    @patch("spotapi.dsl.executor.Player")
    def test_skip_backward(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "skip", "n": -2})

        assert mock_player.skip_prev.call_count == 2

    @patch("spotapi.dsl.executor.Player")
    def test_seek(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "seek", "position_ms": 30000})

        mock_player.seek_to.assert_called_once_with(30000)

    @patch("spotapi.dsl.executor.Player")
    def test_enqueue_uri(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "enqueue", "target": "spotify:track:abc"})

        mock_player.add_to_queue.assert_called_once_with("spotify:track:abc")

    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_like(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        MockSong.return_value = mock_song

        result = executor.execute({"action": "like", "target": "spotify:track:abc123"})

        mock_song.like_song.assert_called_once_with("abc123")
        assert result["status"] == "ok"

    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_unlike(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        MockSong.return_value = mock_song

        result = executor.execute({"action": "unlike", "target": "spotify:track:abc123"})

        mock_song.unlike_song.assert_called_once_with("abc123")

    @patch("spotapi.dsl.executor.Artist")
    def test_follow(self, MockArtist, executor):
        mock_artist = MagicMock()
        MockArtist.return_value = mock_artist

        result = executor.execute({"action": "follow", "target": "spotify:artist:xyz"})

        mock_artist.follow.assert_called_once_with("xyz")

    @patch("spotapi.dsl.executor.Artist")
    def test_unfollow(self, MockArtist, executor):
        mock_artist = MagicMock()
        MockArtist.return_value = mock_artist

        result = executor.execute({"action": "unfollow", "target": "spotify:artist:xyz"})

        mock_artist.unfollow.assert_called_once_with("xyz")


# ── Playlist Actions ──────────────────────────────────────────────


class TestPlaylistActions:
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_save(self, MockPP, executor):
        mock_pp = MagicMock()
        MockPP.return_value = mock_pp

        result = executor.execute({"action": "save", "target": "spotify:playlist:abc123"})

        MockPP.assert_called_with(executor._login, "abc123")
        mock_pp.add_to_library.assert_called_once()

    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_unsave(self, MockPP, executor):
        mock_pp = MagicMock()
        MockPP.return_value = mock_pp

        result = executor.execute({"action": "unsave", "target": "spotify:playlist:abc123"})

        mock_pp.remove_from_library.assert_called_once()

    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_delete_playlist(self, MockPP, executor):
        mock_pp = MagicMock()
        MockPP.return_value = mock_pp

        result = executor.execute({"action": "playlist_delete", "target": "spotify:playlist:abc"})

        mock_pp.delete_playlist.assert_called_once()

    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_playlist_add(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        MockSong.return_value = mock_song

        result = executor.execute({
            "action": "playlist_add",
            "track": "spotify:track:abc",
            "playlist": "spotify:playlist:def",
        })

        mock_song.add_song_to_playlist.assert_called_once_with("abc")

    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_playlist_remove(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        MockSong.return_value = mock_song

        result = executor.execute({
            "action": "playlist_remove",
            "track": "spotify:track:abc",
            "playlist": "spotify:playlist:def",
        })

        mock_song.remove_song_from_playlist.assert_called_once_with(song_id="abc")

    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_create_playlist(self, MockPP, executor):
        mock_pp = MagicMock()
        mock_pp.create_playlist.return_value = "new_playlist_id"
        MockPP.return_value = mock_pp

        result = executor.execute({"action": "playlist_create", "name": "Road Trip"})

        mock_pp.create_playlist.assert_called_once_with("Road Trip")
        assert result["playlist_id"] == "new_playlist_id"


# ── State Modifiers ───────────────────────────────────────────────


class TestStateModifiers:
    @patch("spotapi.dsl.executor.Player")
    def test_volume_after_action(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        executor.execute({"action": "pause", "volume": 0.7})

        mock_player.pause.assert_called_once()
        mock_player.set_volume.assert_called_once_with(0.7)

    @patch("spotapi.dsl.executor.Player")
    def test_mode_shuffle(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        executor.execute({"action": "set", "mode": "shuffle"})

        mock_player.set_shuffle.assert_called_once_with(True)
        mock_player.repeat_track.assert_called_once_with(False)

    @patch("spotapi.dsl.executor.Player")
    def test_mode_repeat(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        executor.execute({"action": "set", "mode": "repeat"})

        mock_player.set_shuffle.assert_called_once_with(False)
        mock_player.repeat_track.assert_called_once_with(True)

    @patch("spotapi.dsl.executor.Player")
    def test_mode_normal(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        executor.execute({"action": "set", "mode": "normal"})

        mock_player.set_shuffle.assert_called_once_with(False)
        mock_player.repeat_track.assert_called_once_with(False)

    @patch("spotapi.dsl.executor.Player")
    def test_device_transfer(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.device_id = "origin_device"
        MockPlayer.return_value = mock_player

        executor.execute({"action": "set", "device": "Living Room"})

        mock_player.transfer_player.assert_called_once_with("origin_device", "Living Room")

    @patch("spotapi.dsl.executor.Player")
    def test_standalone_volume(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "set", "volume": 0.5})

        mock_player.set_volume.assert_called_once_with(0.5)
        assert result["volume"] == 0.5


# ── Compound Operations ──────────────────────────────────────────


class TestCompoundOps:
    @patch("spotapi.dsl.executor.Player")
    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_play_string_searches_and_plays(self, MockPP, MockSong, MockPlayer, executor):
        mock_song = MagicMock()
        mock_song.query_songs.return_value = {
            "data": {
                "searchV2": {
                    "tracksV2": {
                        "items": [
                            {"item": {"data": {"uri": "spotify:track:found123"}}}
                        ]
                    }
                }
            }
        }
        MockSong.return_value = mock_song

        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "play", "target": "jazz"})

        mock_song.query_songs.assert_called_once_with("jazz", limit=1)
        mock_player.add_to_queue.assert_called_once_with("spotify:track:found123")
        mock_player.skip_next.assert_called_once()
        assert result["resolved_uri"] == "spotify:track:found123"

    @patch("spotapi.dsl.executor.Player")
    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_play_string_no_results(self, MockPP, MockSong, MockPlayer, executor):
        mock_song = MagicMock()
        mock_song.query_songs.return_value = {
            "data": {"searchV2": {"tracksV2": {"items": []}}}
        }
        MockSong.return_value = mock_song
        MockPlayer.return_value = MagicMock()

        with pytest.raises(DSLError, match="No results"):
            executor.execute({"action": "play", "target": "nonexistent song xyz"})

    @patch("spotapi.dsl.executor.Player")
    def test_play_uri_no_context(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "play", "target": "spotify:track:abc"})

        mock_player.add_to_queue.assert_called_once_with("spotify:track:abc")
        mock_player.skip_next.assert_called_once()

    @patch("spotapi.dsl.executor.Player")
    def test_play_uri_with_context(self, MockPlayer, executor):
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({
            "action": "play",
            "target": "spotify:track:abc",
            "context": "spotify:playlist:def",
        })

        mock_player.play_track.assert_called_once_with("spotify:track:abc", "spotify:playlist:def")


# ── Query Dispatch ────────────────────────────────────────────────


class TestQueries:
    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_search_tracks(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        mock_song.query_songs.return_value = {"data": "results"}
        MockSong.return_value = mock_song

        result = executor.execute({"query": "search", "term": "jazz", "limit": 5})

        mock_song.query_songs.assert_called_once_with("jazz", limit=5, offset=0)
        assert result["data"] == {"data": "results"}

    @patch("spotapi.dsl.executor.Artist")
    def test_search_artists(self, MockArtist, executor):
        mock_artist = MagicMock()
        mock_artist.query_artists.return_value = {"data": "artist_results"}
        MockArtist.return_value = mock_artist

        result = executor.execute({"query": "search", "term": "jazz", "type": "artists"})

        mock_artist.query_artists.assert_called_once_with("jazz", limit=10, offset=0)

    @patch("spotapi.dsl.executor.Player")
    def test_now_playing(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.state = {"track": "test"}
        MockPlayer.return_value = mock_player

        result = executor.execute({"query": "now_playing"})

        assert result["query"] == "now_playing"
        assert result["data"] == {"track": "test"}

    @patch("spotapi.dsl.executor.Player")
    def test_get_queue(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.next_songs_in_queue = ["song1", "song2"]
        MockPlayer.return_value = mock_player

        result = executor.execute({"query": "get_queue"})

        assert result["data"] == ["song1", "song2"]

    @patch("spotapi.dsl.executor.Player")
    def test_get_devices(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.device_ids = {"device1": "info"}
        MockPlayer.return_value = mock_player

        result = executor.execute({"query": "get_devices"})

        assert result["data"] == {"device1": "info"}

    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_library(self, MockPP, executor):
        mock_pp = MagicMock()
        mock_pp.get_library.return_value = {"items": []}
        MockPP.return_value = mock_pp

        result = executor.execute({"query": "library"})

        mock_pp.get_library.assert_called_once_with(50)

    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_recommend(self, MockPP, executor):
        mock_pp = MagicMock()
        mock_pp.recommended_songs.return_value = {"tracks": []}
        MockPP.return_value = mock_pp

        result = executor.execute({
            "query": "recommend",
            "target": "spotify:playlist:abc",
            "n": 5,
        })

        mock_pp.recommended_songs.assert_called_once_with(num_songs=5)

    @patch("spotapi.dsl.executor.Player")
    def test_history_with_limit(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.last_songs_played = ["a", "b", "c", "d", "e"]
        MockPlayer.return_value = mock_player

        result = executor.execute({"query": "history", "limit": 3})

        assert result["data"] == ["a", "b", "c"]

    @patch("spotapi.dsl.executor.Player")
    def test_history_no_limit(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.last_songs_played = ["a", "b", "c"]
        MockPlayer.return_value = mock_player

        result = executor.execute({"query": "history"})

        assert result["data"] == ["a", "b", "c"]


class TestInfoQuery:
    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_info_track(self, MockPP, MockSong, executor):
        mock_song = MagicMock()
        mock_song.get_track_info.return_value = {"name": "Bohemian Rhapsody"}
        MockSong.return_value = mock_song

        result = executor.execute({"query": "info", "target": "spotify:track:abc123"})

        mock_song.get_track_info.assert_called_once_with("abc123")
        assert result["data"] == {"name": "Bohemian Rhapsody"}

    @patch("spotapi.dsl.executor.Artist")
    def test_info_artist(self, MockArtist, executor):
        mock_artist = MagicMock()
        mock_artist.get_artist.return_value = {"name": "Queen"}
        MockArtist.return_value = mock_artist

        result = executor.execute({"query": "info", "target": "spotify:artist:xyz"})

        mock_artist.get_artist.assert_called_once_with("xyz")
        assert result["data"] == {"name": "Queen"}

    @patch("spotapi.dsl.executor.PublicAlbum")
    def test_info_album(self, MockAlbum, executor):
        mock_album = MagicMock()
        mock_album.get_album_info.return_value = {"name": "A Night at the Opera"}
        MockAlbum.return_value = mock_album

        result = executor.execute({"query": "info", "target": "spotify:album:abc"})

        MockAlbum.assert_called_once_with("abc")
        mock_album.get_album_info.assert_called_once()

    @patch("spotapi.playlist.PublicPlaylist")
    def test_info_playlist(self, MockPubPL, executor):
        mock_pl = MagicMock()
        mock_pl.get_playlist_info.return_value = {"name": "Road Trip"}
        MockPubPL.return_value = mock_pl

        result = executor.execute({"query": "info", "target": "spotify:playlist:abc"})

        MockPubPL.assert_called_once_with("abc")
        mock_pl.get_playlist_info.assert_called_once()

    def test_info_requires_uri(self, executor):
        with pytest.raises(DSLError, match="info requires a Spotify URI"):
            executor.execute({"query": "info", "target": "some string"})

    def test_info_unknown_kind(self, executor):
        with pytest.raises(DSLError, match="Cannot get info"):
            executor.execute({"query": "info", "target": "spotify:show:abc"})


# ── Enqueue with String ──────────────────────────────────────────


class TestEnqueueString:
    @patch("spotapi.dsl.executor.Player")
    @patch("spotapi.dsl.executor.Song")
    @patch("spotapi.dsl.executor.PrivatePlaylist")
    def test_enqueue_string_resolves(self, MockPP, MockSong, MockPlayer, executor):
        mock_song = MagicMock()
        mock_song.query_songs.return_value = {
            "data": {
                "searchV2": {
                    "tracksV2": {
                        "items": [
                            {"item": {"data": {"uri": "spotify:track:resolved"}}}
                        ]
                    }
                }
            }
        }
        MockSong.return_value = mock_song

        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        result = executor.execute({"action": "enqueue", "target": "stairway to heaven"})

        mock_song.query_songs.assert_called_once_with("stairway to heaven", limit=1)
        mock_player.add_to_queue.assert_called_once_with("spotify:track:resolved")


# ── End-to-End (Parser → Executor) ──────────────────────────────


class TestEndToEnd:
    """Integration tests: command string → parser → executor → result."""

    @patch("spotapi.dsl.executor.Player")
    def test_pause_e2e(self, MockPlayer, executor):
        from spotapi.dsl.parser import parse
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        cmd = parse("pause")
        result = executor.execute(cmd)

        mock_player.pause.assert_called_once()
        assert result["status"] == "ok"

    @patch("spotapi.dsl.executor.Artist")
    def test_search_e2e(self, MockArtist, executor):
        from spotapi.dsl.parser import parse
        mock_artist = MagicMock()
        mock_artist.query_artists.return_value = {"data": "results"}
        MockArtist.return_value = mock_artist

        cmd = parse('search "jazz" artists limit 5')
        result = executor.execute(cmd)

        mock_artist.query_artists.assert_called_once_with("jazz", limit=5, offset=0)
        assert result["query"] == "search"
        assert result["type"] == "artists"

    @patch("spotapi.dsl.executor.Player")
    def test_volume_mode_e2e(self, MockPlayer, executor):
        from spotapi.dsl.parser import parse
        mock_player = MagicMock()
        MockPlayer.return_value = mock_player

        cmd = parse("volume 0.7 mode shuffle")
        result = executor.execute(cmd)

        mock_player.set_volume.assert_called_once_with(0.7)
        mock_player.set_shuffle.assert_called_once_with(True)
        assert result["action"] == "set"


# ── Error Wrapping ────────────────────────────────────────────────


class TestErrorWrapping:
    def test_unknown_action(self, executor):
        with pytest.raises(DSLError, match="Unknown action"):
            executor.execute({"action": "explode"})

    def test_unknown_query(self, executor):
        with pytest.raises(DSLError, match="Unknown query"):
            executor.execute({"query": "explode"})

    def test_no_action_or_query(self, executor):
        with pytest.raises(DSLError, match="no action or query"):
            executor.execute({"foo": "bar"})

    @patch("spotapi.dsl.executor.Player")
    def test_spotapi_exception_wrapped(self, MockPlayer, executor):
        mock_player = MagicMock()
        mock_player.pause.side_effect = RuntimeError("connection lost")
        MockPlayer.return_value = mock_player

        with pytest.raises(DSLError, match="connection lost"):
            executor.execute({"action": "pause"})
