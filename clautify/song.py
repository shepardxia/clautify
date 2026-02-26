from collections.abc import Generator, Iterable, Mapping
from typing import Any, List, Tuple

from clautify.client import BaseClient
from clautify.exceptions import SongError
from clautify.http.request import TLSClient
from clautify.playlist import PrivatePlaylist, PublicPlaylist
from clautify.types.annotations import enforce
from clautify.utils.pagination import paginate
from clautify.utils.strings import extract_spotify_id

__all__ = ["Song", "SongError"]


@enforce
class Song:
    """
    Extends the PrivatePlaylist class with methods that can only be used while logged in.
    These methods interact with songs and tend to be used in the context of a playlist.

    Parameters
    ----------
    playlist (Optional[str]): The Spotify URI of the playlist.
    client (Optional[TLSClient]): An instance of TLSClient to use for requests
    """

    __slots__ = (
        "playlist",
        "base",
    )

    def __init__(
        self,
        playlist: PrivatePlaylist | None = None,
        *,
        client: TLSClient = TLSClient("chrome_120", "", auto_retries=3),
        language: str = "en",
    ) -> None:
        self.playlist = playlist
        self.base = BaseClient(client=playlist.login.client if playlist else client, language=language)

    def get_track_info(self, track_id: str) -> Mapping[str, Any]:
        """
        Gets information about a specific song.
        """
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = self.base.graphql_params("getTrack", {"uri": f"spotify:track:{track_id}"})
        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise SongError("Could not get song info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise SongError("Invalid JSON")

        return resp.response

    def query_songs(self, query: str, /, limit: int = 10, *, offset: int = 0) -> Mapping[str, Any]:
        """
        Searches for songs in the Spotify catalog.
        NOTE: Returns the raw result unlike paginate_songs which only returns the songs.
        """
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = self.base.graphql_params(
            "searchDesktop",
            {
                "searchTerm": query,
                "offset": offset,
                "limit": limit,
                "numberOfTopResults": 5,
                "includeAudiobooks": True,
                "includeArtistHasConcertsField": False,
                "includePreReleases": True,
                "includeLocalConcertsField": False,
            },
        )
        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise SongError("Could not get songs", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise SongError("Invalid JSON")

        return resp.response

    def paginate_songs(self, query: str, /) -> Generator[Mapping[str, Any], None, None]:
        """Generator that fetches songs in chunks."""
        return paginate(
            lambda limit, offset: self.query_songs(query, limit=limit, offset=offset),
            "data.searchV2.tracksV2.totalCount",
            "data.searchV2.tracksV2.items",
            upper_limit=100,
        )

    def add_songs_to_playlist(self, song_ids: List[str], /) -> None:
        """Adds multiple songs to the playlist"""
        # This can be a bit slow when adding 500+ songs, maybe we should add a batch processing
        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = self.base.graphql_payload(
            "addToPlaylist",
            {
                "uris": [f"spotify:track:{song_id}" for song_id in song_ids],
                "playlistUri": f"spotify:playlist:{self.playlist.playlist_id}",
                "newPosition": {"moveType": "BOTTOM_OF_PLAYLIST", "fromUid": None},
            },
        )
        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not add songs to playlist", error=resp.error.string)

    def add_song_to_playlist(self, song_id: str, /) -> None:
        """Adds a song to the playlist"""
        self.add_songs_to_playlist([extract_spotify_id(song_id, "track")])

    def _stage_remove_song(self, uids: List[str]) -> None:
        # If None, something internal went wrong
        assert self.playlist is not None, "Playlist not set"

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = self.base.graphql_payload(
            "removeFromPlaylist",
            {
                "playlistUri": f"spotify:playlist:{self.playlist.playlist_id}",
                "uids": uids,
            },
        )
        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not remove song from playlist", error=resp.error.string)

    @staticmethod
    def parse_playlist_items(
        items: Iterable[Mapping[str, Any]],
        *,
        song_id: str | None = None,
        song_name: str | None = None,
        all_instances: bool = False,
    ) -> Tuple[List[str], bool]:
        uids: List[str] = []
        for item in items:
            is_song_id = song_id and song_id in item["itemV2"]["data"]["uri"]
            is_song_name = song_name and song_name.lower() in str(item["itemV2"]["data"]["name"]).lower()

            if is_song_id or is_song_name:
                uids.append(item["uid"])

                if all_instances:
                    return uids, True

        return uids, False

    def remove_song_from_playlist(
        self,
        *,
        all_instances: bool = False,
        uid: str | None = None,
        song_id: str | None = None,
        song_name: str | None = None,
    ) -> None:
        """
        Removes a song from the playlist.
        If all_instances is True, only song_name can be used.
        """
        if song_id:
            song_id = extract_spotify_id(song_id, "track")

        if not (song_id or song_name or uid):
            raise ValueError("Must provide either song_id or song_name or uid")

        if all_instances and song_id:
            raise ValueError("Cannot provide both song_id and all_instances")

        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        playlist = PublicPlaylist(self.playlist.playlist_id).paginate_playlist()

        uids: List[str] = []
        if not uid:
            for playlist_chunk in playlist:
                items = playlist_chunk["items"]
                extended_uids, stop = Song.parse_playlist_items(
                    items,
                    song_id=song_id,
                    song_name=song_name,
                    all_instances=all_instances,
                )
                uids.extend(extended_uids)

                if stop:
                    playlist.close()
                    break
        else:
            uids.append(uid)

        if len(uids) == 0:
            raise SongError("Song not found in playlist")

        self._stage_remove_song(uids)

    def like_song(self, song_id: str, /) -> None:
        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        song_id = extract_spotify_id(song_id, "track")

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = self.base.graphql_payload(
            "addToLibrary",
            {
                "libraryItemUris": [f"spotify:track:{song_id}"],
            },
        )
        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not like song", error=resp.error.string)

    def unlike_song(self, song_id: str, /) -> None:
        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        song_id = extract_spotify_id(song_id, "track")

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = self.base.graphql_payload(
            "removeFromLibrary",
            {
                "libraryItemUris": [f"spotify:track:{song_id}"],
            },
        )
        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not unlike song", error=resp.error.string)
