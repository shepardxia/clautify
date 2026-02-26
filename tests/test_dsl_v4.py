"""Tests for DSL v4 grammar and executor.

Parser tests verify parse() output shape (no mocks needed).
Executor tests verify resolution and dispatch via session.run().
The session fixture lives in conftest.py.
"""

from unittest.mock import MagicMock

import pytest

from clautify.dsl.executor import DSLError
from clautify.dsl.parser import parse

# ── Stub helpers (executor tests only) ─────────────────────────────


def _stub_track_search(session, name="Heathen", uri="spotify:track:abc123"):
    mock_song = session._mocks["Song"].return_value
    mock_song.query_songs.return_value = {
        "data": {"searchV2": {"tracksV2": {"items": [{"item": {"data": {"name": name, "uri": uri}}}]}}}
    }


def _stub_album_search(session, name="Sunbather", uri="spotify:album:abc123"):
    mock_song = session._mocks["Song"].return_value
    mock_song.query_songs.return_value = {
        "data": {"searchV2": {"albumsV2": {"items": [{"data": {"name": name, "uri": uri}}]}}}
    }


def _stub_artist_search(session, name="Deafheaven", uri="spotify:artist:abc123"):
    mock_artist = session._mocks["Artist"].return_value
    mock_artist.query_artists.return_value = {
        "data": {"searchV2": {"artists": {"items": [{"data": {"profile": {"name": name}, "uri": uri}}]}}}
    }


# ═══════════════════════════════════════════════════════════════════
# Parser — Grammar & command dict shape
# ═══════════════════════════════════════════════════════════════════


class TestParserPlayback:
    """play, pause, resume, skip, seek, queue — verb kind target."""

    @pytest.mark.parametrize(
        "kind, target",
        [
            ("track", "Heathen"),
            ("album", "Sunbather"),
            ("playlist", "Daily Mix"),
        ],
    )
    def test_play_quoted(self, kind, target):
        r = parse(f'play {kind} "{target}"')
        assert r == {"action": "play", "kind": kind, "target": target}

    @pytest.mark.parametrize(
        "kind, bare_id",
        [
            ("track", "6rqhFgbbKwnb9MLmUQDhG6"),
            ("album", "3mH6qwIy9crq0I9YQbOuDf"),
        ],
    )
    def test_play_bare_id(self, kind, bare_id):
        r = parse(f"play {kind} {bare_id}")
        assert r == {"action": "play", "kind": kind, "target": bare_id}

    def test_play_without_kind_rejects(self):
        with pytest.raises(Exception):
            parse('play "Heathen"')

    def test_play_with_context(self):
        r = parse('play track "Heathen" in playlist "My Playlist"')
        assert r["action"] == "play"
        assert r["kind"] == "track"
        assert r["target"] == "Heathen"
        assert r["context_kind"] == "playlist"
        assert r["context"] == "My Playlist"

    def test_play_context_without_kind_rejects(self):
        """Context target must have its kind."""
        with pytest.raises(Exception):
            parse('play track "Heathen" in "My Playlist"')

    def test_play_uri_rejects(self):
        with pytest.raises(Exception):
            parse("play track spotify:track:6rqhFgbbKwnb9MLmUQDhG6")

    @pytest.mark.parametrize(
        "cmd, expected",
        [
            ("pause", {"action": "pause"}),
            ("resume", {"action": "resume"}),
        ],
    )
    def test_simple_actions(self, cmd, expected):
        assert parse(cmd) == expected

    def test_skip_default(self):
        r = parse("skip")
        assert r == {"action": "skip", "n": 1}

    def test_skip_n(self):
        r = parse("skip 3")
        assert r == {"action": "skip", "n": 3}

    def test_seek(self):
        r = parse("seek 30000")
        assert r == {"action": "seek", "position_s": 30000.0}

    def test_queue_single(self):
        r = parse("queue track 6rqhFgbbKwnb9MLmUQDhG6")
        assert r["action"] == "queue"
        assert r["kind"] == "track"

    def test_queue_multiple(self):
        r = parse("queue track 6rqhFgbbKwnb9MLmUQDhG6 2kJwBlKpJPmIGGasmAR1lR")
        assert r["action"] == "queue"
        assert len(r["targets"]) == 2

    def test_queue_without_kind_rejects(self):
        with pytest.raises(Exception):
            parse("queue 6rqhFgbbKwnb9MLmUQDhG6")


class TestParserDiscovery:
    """search, info, recommend — verb kind target."""

    @pytest.mark.parametrize("kind", ["track", "album", "artist", "playlist"])
    def test_search_by_kind(self, kind):
        r = parse(f'search {kind} "deafheaven"')
        assert r["query"] == "search"
        assert r["kind"] == kind
        assert r["terms"] == ["deafheaven"]

    @pytest.mark.parametrize(
        "cmd",
        [
            'search "deafheaven"',
            'search tracks "deafheaven"',
            'search "deafheaven" track',
        ],
        ids=["no-kind", "plural-kind", "kind-after-term"],
    )
    def test_search_rejects_bad_syntax(self, cmd):
        with pytest.raises(Exception):
            parse(cmd)

    def test_info_quoted(self):
        r = parse('info artist "Deafheaven"')
        assert r == {"query": "info", "kind": "artist", "target": "Deafheaven"}

    def test_info_bare_id(self):
        r = parse("info track 6rqhFgbbKwnb9MLmUQDhG6")
        assert r == {"query": "info", "kind": "track", "target": "6rqhFgbbKwnb9MLmUQDhG6"}

    def test_info_without_kind_rejects(self):
        with pytest.raises(Exception):
            parse('info "Deafheaven"')

    def test_recommend(self):
        r = parse('recommend track 5 in playlist "My Playlist"')
        assert r["query"] == "recommend"
        assert r["kind"] == "track"
        assert r["n"] == 5
        assert r["context_kind"] == "playlist"
        assert r["context"] == "My Playlist"

    def test_recommend_old_for_syntax_rejects(self):
        with pytest.raises(Exception):
            parse('recommend track 5 for "My Playlist"')


class TestParserLibrary:
    """library add/remove/list/create/delete kind target."""

    @pytest.mark.parametrize(
        "kind, target",
        [
            ("track", "Heathen"),
            ("artist", "Deafheaven"),
            ("album", "Sunbather"),
            ("playlist", "Daily Mix"),
        ],
    )
    def test_library_add(self, kind, target):
        r = parse(f'library add {kind} "{target}"')
        assert r == {"action": "library_add", "kind": kind, "targets": [target]}

    def test_library_add_bare_id(self):
        r = parse("library add track 6rqhFgbbKwnb9MLmUQDhG6")
        assert r["action"] == "library_add"
        assert r["targets"] == ["6rqhFgbbKwnb9MLmUQDhG6"]

    def test_library_add_multiple_targets(self):
        r = parse('library add track "Heathen" "Dream House"')
        assert r["targets"] == ["Heathen", "Dream House"]

    def test_library_add_to_playlist(self):
        r = parse('library add track "Heathen" in playlist "My Playlist"')
        assert r["action"] == "library_add"
        assert r["kind"] == "track"
        assert r["targets"] == ["Heathen"]
        assert r["context_kind"] == "playlist"
        assert r["context"] == "My Playlist"

    @pytest.mark.parametrize(
        "kind, target",
        [
            ("track", "Heathen"),
            ("artist", "Deafheaven"),
            ("album", "Sunbather"),
            ("playlist", "Daily Mix"),
        ],
    )
    def test_library_remove(self, kind, target):
        r = parse(f'library remove {kind} "{target}"')
        assert r == {"action": "library_remove", "kind": kind, "targets": [target]}

    def test_library_remove_from_playlist(self):
        r = parse('library remove track "Heathen" in playlist "My Playlist"')
        assert r["action"] == "library_remove"
        assert r["kind"] == "track"
        assert r["targets"] == ["Heathen"]
        assert r["context_kind"] == "playlist"
        assert r["context"] == "My Playlist"

    @pytest.mark.parametrize("kind", ["track", "artist", "album", "playlist"])
    def test_library_list(self, kind):
        r = parse(f"library list {kind}")
        assert r == {"query": "library_list", "kind": kind}

    def test_library_create_playlist(self):
        r = parse('library create playlist "New Playlist"')
        assert r == {"action": "library_create", "kind": "playlist", "target": "New Playlist"}

    def test_library_delete_playlist(self):
        r = parse('library delete playlist "Old Playlist"')
        assert r == {"action": "library_delete", "kind": "playlist", "target": "Old Playlist"}


class TestParserStatus:
    """status parses as a simple query."""

    def test_status(self):
        r = parse("status")
        assert r == {"query": "status"}

    def test_status_with_limit(self):
        r = parse("status limit 3")
        assert r == {"query": "status", "limit": 3}


class TestParserStateModifiers:
    """volume, mode, on — standalone or chained."""

    def test_volume_absolute(self):
        r = parse("volume 50")
        assert r == {"action": "set", "volume": 50}

    def test_volume_relative(self):
        r = parse("volume +10")
        assert r == {"action": "set", "volume_rel": 10}

    @pytest.mark.parametrize("mode", ["shuffle", "repeat", "normal"])
    def test_mode(self, mode):
        r = parse(f"mode {mode}")
        assert r == {"action": "set", "mode": mode}

    def test_device_switch(self):
        r = parse('device "MacBook Pro"')
        assert r == {"action": "set", "device": "MacBook Pro"}

    def test_play_with_modifiers(self):
        r = parse('play track "Heathen" volume 50 mode shuffle')
        assert r["action"] == "play"
        assert r["volume"] == 50
        assert r["mode"] == "shuffle"


class TestParserRejectsOldSyntax:
    """Old DSL forms should not parse."""

    @pytest.mark.parametrize(
        "cmd",
        [
            'search "deafheaven" tracks',
            "like spotify:track:abc",
            "follow spotify:artist:abc",
            "save spotify:playlist:abc",
            "now playing",
            "get queue",
            "get devices",
            'add "track" to "playlist"',
            'recommend track 5 for "My Playlist"',
            'play track "X" in "Y"',
        ],
        ids=[
            "plural-search",
            "like",
            "follow",
            "save",
            "now-playing",
            "get-queue",
            "get-devices",
            "add-to",
            "recommend-for",
            "context-without-kind",
        ],
    )
    def test_old_syntax_rejects(self, cmd):
        with pytest.raises(Exception):
            parse(cmd)


# ═══════════════════════════════════════════════════════════════════
# Executor — Resolution & dispatch
# ═══════════════════════════════════════════════════════════════════


class TestResolveQuotedString:
    """Quoted strings should auto-resolve via search API."""

    @pytest.mark.parametrize(
        "kind, cmd, stub",
        [
            ("track", 'play track "Heathen"', "track"),
            ("album", 'play album "Sunbather"', "album"),
        ],
    )
    def test_play_quoted_resolves(self, session, kind, cmd, stub):
        {"track": _stub_track_search, "album": _stub_album_search}[stub](session)
        r = session.run(cmd)
        assert r["status"] == "ok"
        assert r["action"] == "play"

    def test_info_artist_quoted_resolves(self, session):
        _stub_artist_search(session, "Deafheaven", "spotify:artist:4O15Nl")
        mock_artist = session._mocks["Artist"].return_value
        mock_artist.get_artist.return_value = {"name": "Deafheaven"}
        r = session.run('info artist "Deafheaven"')
        assert r["status"] == "ok"
        assert r["query"] == "info"

    def test_play_quoted_no_results_raises(self, session):
        mock_song = session._mocks["Song"].return_value
        mock_song.query_songs.return_value = {"data": {"searchV2": {"tracksV2": {"items": []}}}}
        with pytest.raises(DSLError, match="No results"):
            session.run('play track "xyznonexistent"')


class TestResolveBareId:
    """Bare IDs should be used directly — no search."""

    @pytest.mark.parametrize(
        "cmd",
        [
            "play track 6rqhFgbbKwnb9MLmUQDhG6",
            "play album 3mH6qwIy9crq0I9YQbOuDf",
            "queue track 6rqhFgbbKwnb9MLmUQDhG6",
        ],
        ids=["play-track", "play-album", "queue-track"],
    )
    def test_bare_id_no_search(self, session, cmd):
        r = session.run(cmd)
        assert r["status"] == "ok"
        session._mocks["Song"].return_value.query_songs.assert_not_called()
        session._mocks["Artist"].return_value.query_artists.assert_not_called()


class TestSearchArtistAutoInfo:
    """search artist with exact name match returns info instead of ID list."""

    def test_exact_match_returns_info(self, session):
        _stub_artist_search(session, "Deafheaven", "spotify:artist:4O15Nl")
        mock_artist = session._mocks["Artist"].return_value
        mock_artist.get_artist.return_value = {"data": {"artistUnion": {"profile": {"name": "Deafheaven"}}}}
        r = session.run('search artist "Deafheaven"')
        assert r["query"] == "info"
        assert r["kind"] == "artist"
        mock_artist.get_artist.assert_called_once()

    def test_exact_match_case_insensitive(self, session):
        _stub_artist_search(session, "Deafheaven", "spotify:artist:4O15Nl")
        mock_artist = session._mocks["Artist"].return_value
        mock_artist.get_artist.return_value = {"data": {"artistUnion": {"profile": {"name": "Deafheaven"}}}}
        r = session.run('search artist "deafheaven"')
        assert r["query"] == "info"

    def test_no_exact_match_returns_search(self, session):
        _stub_artist_search(session, "Deafhaven", "spotify:artist:xyz")
        r = session.run('search artist "Deafheaven"')
        assert r["query"] == "search"
        assert r["kind"] == "artist"


class TestLibraryExecution:
    """library add/remove dispatches to correct API."""

    @pytest.mark.parametrize(
        "action, kind, stub_fn, mock_key, method",
        [
            ("add", "track", _stub_track_search, "Song", "like_song"),
            ("remove", "track", _stub_track_search, "Song", "unlike_song"),
            ("add", "artist", _stub_artist_search, "Artist", "follow"),
            ("remove", "artist", _stub_artist_search, "Artist", "unfollow"),
        ],
    )
    def test_library_track_artist(self, session, action, kind, stub_fn, mock_key, method):
        stub_fn(session)
        r = session.run(f'library {action} {kind} "test"')
        assert r["status"] == "ok"
        getattr(session._mocks[mock_key].return_value, method).assert_called_once()

    @pytest.mark.parametrize(
        "action, method",
        [
            ("add", "add_to_library"),
            ("remove", "remove_from_library"),
        ],
    )
    def test_library_playlist(self, session, action, method):
        r = session.run(f"library {action} playlist 37i9dQZF1DXcBWIGoYBM5M")
        assert r["status"] == "ok"
        getattr(session._mocks["PP"].return_value, method).assert_called_once()


class TestStatusQuery:
    """status returns now_playing, queue, devices, history in one call."""

    def test_status_returns_all_sections(self, session):
        r = session.run("status")
        assert r["status"] == "ok"
        assert r["query"] == "status"
        assert "now_playing" in r
        assert "queue" in r
        assert "devices" in r
        assert "history" in r

    def test_status_limit_caps_queue_and_history(self, session):
        r = session.run("status limit 2")
        assert r["status"] == "ok"
        assert r["limit"] == 2
