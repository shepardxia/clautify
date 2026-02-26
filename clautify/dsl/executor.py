"""Spotify DSL executor — dispatches parsed command dicts to SpotAPI classes."""

import re
from typing import Any, Dict, Optional

from clautify.album import PublicAlbum
from clautify.artist import Artist
from clautify.exceptions import WebSocketError
from clautify.login import Login
from clautify.player import Player
from clautify.playlist import PrivatePlaylist
from clautify.song import Song
from clautify.utils.strings import extract_spotify_id as _extract_id


class DSLError(Exception):
    """Raised when a DSL command fails."""

    def __init__(self, message: str, command: Optional[Dict[str, Any]] = None):
        self.command = command
        super().__init__(message)


def _deep_get(data: Any, *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dicts by key path, returning default on any miss."""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key)
        else:
            return default
        if data is None:
            return default
    return data


_BARE_ID_RE = re.compile(r"^[a-zA-Z0-9]{22}$")


def _is_bare_id(target: str) -> bool:
    return bool(_BARE_ID_RE.match(target))


# --- search section paths (Spotify API response structure) ---

_SEARCH_SECTION_PATH = {
    "track": ("data", "searchV2", "tracksV2", "items"),
    "album": ("data", "searchV2", "albumsV2", "items"),
    "playlist": ("data", "searchV2", "playlists", "items"),
}

# --- library filter strings for Spotify API ---

_LIBRARY_FILTERS = {
    "playlist": ["Playlists"],
    "artist": ["Artists"],
    "album": ["Albums"],
    "track": [],
}


class SpotifyExecutor:
    """Dispatches parsed DSL command dicts to SpotAPI class methods.

    Lazily initializes heavy resources (Player requires WebSocket + threads).
    No name cache — quoted strings auto-resolve via search, bare IDs used directly.
    """

    def __init__(self, login: Login, eager: bool = True, max_volume: float = 1.0):
        self._login = login
        self._player: Optional[Player] = None
        self._song: Optional[Song] = None
        self._artist: Optional[Artist] = None
        self._max_volume = max(0.0, min(1.0, max_volume))
        if eager:
            _ = self.player

    # --- lazy properties ---

    @property
    def player(self) -> Player:
        if self._player is None:
            self._player = Player(self._login)
        return self._player

    def _reset_player(self) -> None:
        """Tear down a stale Player so the next access creates a fresh one."""
        if self._player is not None:
            try:
                self._player.ws.close()
            except Exception:
                pass
            self._player = None

    @property
    def song(self) -> Song:
        if self._song is None:
            sentinel = PrivatePlaylist(self._login, "__sentinel__")
            self._song = Song(playlist=sentinel)
        return self._song

    @property
    def artist(self) -> Artist:
        if self._artist is None:
            self._artist = Artist(login=self._login)
        return self._artist

    def close(self) -> None:
        """Clean up resources (WebSocket, threads) if Player was created."""
        if self._player is not None:
            try:
                self._player.ws.close()
            except Exception:
                pass

    # --- target resolution ---

    def _resolve_target(self, kind: str, target: str, cmd: Dict[str, Any]) -> str:
        """Resolve a target to a full spotify URI.

        Bare IDs (22-char alphanumeric) are used directly.
        Quoted strings trigger a search and use the top result.
        """
        if _is_bare_id(target):
            return f"spotify:{kind}:{target}"
        return self._search_and_resolve(kind, target, cmd)

    def _search_and_resolve(self, kind: str, name: str, cmd: Dict[str, Any]) -> str:
        """Search Spotify for name, return top result URI."""
        if kind == "artist":
            raw = self.artist.query_artists(name, limit=1)
            items = _deep_get(raw, "data", "searchV2", "artists", "items", default=[])
            if not items:
                raise DSLError(f'No results for "{name}"', command=cmd)
            uri = _deep_get(items[0], "data", "uri")
        else:
            raw = self.song.query_songs(name, limit=1)
            section = self._extract_search_section(raw, kind)
            if not isinstance(section, list) or not section:
                raise DSLError(f'No results for "{name}"', command=cmd)
            if kind == "track":
                uri = _deep_get(section[0], "item", "data", "uri")
            else:
                uri = _deep_get(section[0], "data", "uri")

        if not uri:
            raise DSLError(f'No results for "{name}"', command=cmd)
        return uri

    def _extract_search_section(self, raw: Dict[str, Any], kind: str) -> Any:
        """Extract a specific section from searchDesktop results."""
        path = _SEARCH_SECTION_PATH.get(kind)
        if not path:
            return raw
        result = raw
        for key in path:
            if isinstance(result, dict):
                result = result.get(key, {})
            else:
                return raw
        return result

    def _resolve_device_id(self, name: str) -> str:
        """Resolve a friendly device name to a device ID (case-insensitive)."""
        devices = self.player.device_ids
        name_lower = name.lower()
        for device in devices.devices.values():
            if device.name.lower() == name_lower:
                return device.device_id
        available = [d.name for d in devices.devices.values()]
        raise DSLError(f"Device '{name}' not found. Available: {available}")

    # --- main dispatch ---

    def execute(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a parsed command dict and return the result."""
        try:
            return self._execute_once(cmd)
        except (WebSocketError, DSLError) as first:
            inner = first.__cause__ if isinstance(first, DSLError) else first
            if not isinstance(inner, WebSocketError) and not isinstance(first, WebSocketError):
                raise
            self._reset_player()
            try:
                return self._execute_once(cmd)
            except DSLError:
                raise
            except Exception as e:
                raise DSLError(f"{type(e).__name__}: {e}", command=cmd) from e

    def _execute_once(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if "action" in cmd:
                result = self._dispatch_action(cmd)
            elif "query" in cmd:
                result = self._dispatch_query(cmd)
            else:
                raise DSLError("Invalid command: no action or query key", command=cmd)
            return result
        except DSLError:
            raise
        except Exception as e:
            detail = getattr(e, "error", None)
            msg = f"{type(e).__name__}: {e}"
            if detail:
                msg = f"{msg} ({detail})"
            raise DSLError(msg, command=cmd) from e

    # --- action dispatch ---

    def _dispatch_action(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        action = cmd["action"]

        if action in ("pause", "resume"):
            getattr(self.player, action)()
            result = {"status": "ok", "action": action}

        elif action == "set":
            result = {"status": "ok", "action": "set"}
            for k in ("volume", "volume_rel", "mode", "device"):
                if k in cmd:
                    result[k] = cmd[k]

        else:
            handler = getattr(self, f"_action_{action}", None)
            if handler is None:
                raise DSLError(f"Unknown action: {action}", command=cmd)
            result = handler(cmd)

        self._apply_state_modifiers(cmd)

        if "volume" in cmd and "volume" in result:
            result["volume"] = min(cmd["volume"], self._max_volume * 100)

        return result

    def _apply_state_modifiers(self, cmd: Dict[str, Any]) -> None:
        if "volume" in cmd:
            vol = cmd["volume"]
            if not (0 <= vol <= 100):
                raise DSLError(f"Volume must be 0-100, got {vol}")
            normalized = min(vol / 100, self._max_volume)
            self.player.set_volume(normalized)
        if "volume_rel" in cmd:
            delta = cmd["volume_rel"]
            devices = self.player.device_ids
            dev = devices.devices.get(self.player.active_id)
            if dev is None:
                raise DSLError("Cannot determine current volume for relative adjustment")
            current = dev.volume / 65535
            new_vol = max(0.0, min(self._max_volume, current + delta / 100))
            self.player.set_volume(new_vol)
        if "mode" in cmd:
            mode = cmd["mode"]
            self.player.set_shuffle(mode == "shuffle")
            self.player.repeat_track(mode == "repeat")
        if "device" in cmd:
            device_id = self._resolve_device_id(cmd["device"])
            self.player.transfer_player(self.player.device_id, device_id)

    # --- action handlers ---

    def _action_play(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        kind = cmd["kind"]
        target = cmd["target"]
        context = cmd.get("context")
        context_kind = cmd.get("context_kind")

        uri = self._resolve_target(kind, target, cmd)

        if context:
            context_uri = self._resolve_target(context_kind, context, cmd)
            self.player.play_track(uri, context_uri)
            result = {
                "status": "ok",
                "action": "play",
                "kind": kind,
                "target": target,
                "context_kind": context_kind,
                "context": context,
            }
        else:
            self.player.play_context(uri)
            result = {"status": "ok", "action": "play", "kind": kind, "target": target}

        if uri != target:
            result["resolved_uri"] = uri
        return result

    def _action_skip(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        n = cmd.get("n", 1)
        fn = self.player.skip_next if n >= 0 else self.player.skip_prev
        for _ in range(abs(n)):
            fn()
        return {"status": "ok", "action": "skip", "n": n}

    def _action_seek(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        position_s = int(cmd["position_s"])
        self.player.seek_to(position_s * 1000)
        return {"status": "ok", "action": "seek", "position_s": position_s}

    def _action_queue(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        kind = cmd["kind"]
        if kind != "track":
            raise DSLError(f"Queue only supports tracks — use play for {kind}s", command=cmd)
        targets = cmd["targets"]
        queued = []
        for target in targets:
            uri = self._resolve_target(kind, target, cmd)
            self.player.add_to_queue(uri)
            queued.append(target)
        return {"status": "ok", "action": "queue", "kind": kind, "targets": queued}

    def _action_library_add(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        kind = cmd["kind"]
        targets = cmd["targets"]
        context = cmd.get("context")
        context_kind = cmd.get("context_kind")

        for target in targets:
            uri = self._resolve_target(kind, target, cmd)
            bare_id = _extract_id(uri, kind)

            if context:
                playlist_uri = self._resolve_target(context_kind, context, cmd)
                pl = PrivatePlaylist(self._login, _extract_id(playlist_uri, "playlist"))
                Song(playlist=pl).add_song_to_playlist(bare_id)
            elif kind == "track":
                self.song.like_song(bare_id)
            elif kind == "artist":
                self.artist.follow(bare_id)
            elif kind == "playlist":
                PrivatePlaylist(self._login, bare_id).add_to_library()
            elif kind == "album":
                raise DSLError("Album library management not yet supported", command=cmd)

        return {"status": "ok", "action": "library_add", "kind": kind, "targets": targets}

    def _action_library_remove(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        kind = cmd["kind"]
        targets = cmd["targets"]
        context = cmd.get("context")
        context_kind = cmd.get("context_kind")

        for target in targets:
            uri = self._resolve_target(kind, target, cmd)
            bare_id = _extract_id(uri, kind)

            if context:
                playlist_uri = self._resolve_target(context_kind, context, cmd)
                pl = PrivatePlaylist(self._login, _extract_id(playlist_uri, "playlist"))
                Song(playlist=pl).remove_song_from_playlist(song_id=bare_id)
            elif kind == "track":
                self.song.unlike_song(bare_id)
            elif kind == "artist":
                self.artist.unfollow(bare_id)
            elif kind == "playlist":
                PrivatePlaylist(self._login, bare_id).remove_from_library()
            elif kind == "album":
                raise DSLError("Album library management not yet supported", command=cmd)

        return {"status": "ok", "action": "library_remove", "kind": kind, "targets": targets}

    def _action_library_create(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        name = cmd["target"]
        playlist_id = PrivatePlaylist(self._login).create_playlist(name)
        return {
            "status": "ok",
            "action": "library_create",
            "kind": "playlist",
            "target": name,
            "playlist_id": playlist_id,
        }

    def _action_library_delete(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        target = cmd["target"]
        uri = self._resolve_target("playlist", target, cmd)
        PrivatePlaylist(self._login, _extract_id(uri, "playlist")).delete_playlist()
        return {"status": "ok", "action": "library_delete", "kind": "playlist", "target": target}

    # --- query dispatch ---

    def _dispatch_query(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        query = cmd["query"]
        handler = getattr(self, f"_query_{query}", None)
        if handler is None:
            raise DSLError(f"Unknown query: {query}", command=cmd)
        return handler(cmd)

    def _query_search(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        terms = cmd["terms"]
        kind = cmd["kind"]
        limit = cmd.get("limit", 10)
        offset = cmd.get("offset", 0)

        all_results = []
        for term in terms:
            if kind == "artist":
                raw = self.artist.query_artists(term, limit=limit, offset=offset)
                try:
                    items = raw["data"]["searchV2"]["artists"]["items"]
                    all_results.extend(items)
                except (KeyError, TypeError):
                    pass
            else:
                raw = self.song.query_songs(term, limit=limit, offset=offset)
                results = self._extract_search_section(raw, kind)
                if isinstance(results, list):
                    all_results.extend(results)

        # Auto-promote: exact artist match → return info instead of ID list
        if kind == "artist" and len(terms) == 1 and all_results:
            first_name = _deep_get(all_results[0], "data", "profile", "name", default="")
            if first_name.lower() == terms[0].lower():
                uri = _deep_get(all_results[0], "data", "uri", default="")
                if uri:
                    bare_id = _extract_id(uri, "artist")
                    data = self.artist.get_artist(bare_id)
                    return {"status": "ok", "query": "info", "kind": "artist", "target": first_name, "data": data}

        return {"status": "ok", "query": "search", "kind": kind, "terms": terms, "data": all_results}

    def _query_status(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        limit = cmd.get("limit", 5)
        return {
            "status": "ok",
            "query": "status",
            "limit": limit,
            "now_playing": self.player.state,
            "queue": self.player.next_songs_in_queue[:limit],
            "devices": self.player.device_ids,
            "history": self.player.last_songs_played[:limit],
        }

    def _query_info(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        kind = cmd["kind"]
        target = cmd["target"]
        uri = self._resolve_target(kind, target, cmd)
        bare_id = _extract_id(uri, kind)
        limit = cmd.get("limit", 25)
        offset = cmd.get("offset", 0)

        if kind == "track":
            data = self.song.get_track_info(bare_id)
        elif kind == "artist":
            data = self.artist.get_artist(bare_id)
        elif kind == "album":
            data = PublicAlbum(bare_id).get_album_info(limit=limit, offset=offset)
        elif kind == "playlist":
            from clautify.playlist import PublicPlaylist

            data = PublicPlaylist(bare_id).get_playlist_info(limit=limit, offset=offset)
        else:
            raise DSLError(f"Cannot get info for kind: {kind}", command=cmd)

        return {"status": "ok", "query": "info", "kind": kind, "target": target, "data": data}

    def _query_library_list(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        kind = cmd["kind"]
        filters = _LIBRARY_FILTERS.get(kind, [])
        limit = cmd.get("limit", 50)
        offset = cmd.get("offset", 0)
        data = PrivatePlaylist(self._login).get_library(limit, offset=offset, filters=filters)
        return {"status": "ok", "query": "library_list", "kind": kind, "data": data, "limit": limit}

    def _query_recommend(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        context = cmd["context"]
        context_kind = cmd["context_kind"]
        kind = cmd["kind"]
        n = cmd.get("n", 20)
        uri = self._resolve_target(context_kind, context, cmd)
        data = PrivatePlaylist(self._login, _extract_id(uri, "playlist")).recommended_songs(num_songs=n)
        return {"status": "ok", "query": "recommend", "kind": kind, "context": context, "n": n, "data": data}
