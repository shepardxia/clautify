from __future__ import annotations

from collections.abc import Generator, Mapping
from typing import Any, Literal

from clautify.client import BaseClient
from clautify.exceptions import ArtistError
from clautify.http.request import TLSClient
from clautify.login import Login
from clautify.types.annotations import enforce
from clautify.utils.pagination import paginate
from clautify.utils.strings import extract_spotify_id

__all__ = ["Artist", "ArtistError"]


@enforce
class Artist:
    """
    A class that represents an artist in the Spotify catalog.

    Parameters
    ----------
    login : Optional[Login], optional
        A logged in Login object. This is required for certain methods.
        If not provided, some methods will raise a ValueError.
    client : TLSClient, optional
        A TLSClient used for making requests to the API.
        If not provided, a default one will be used.
    """

    __slots__ = (
        "_login",
        "base",
    )

    def __init__(
        self,
        login: Login | None = None,
        *,
        client: TLSClient = TLSClient("chrome_120", "", auto_retries=3),
        language: str = "en",
    ) -> None:
        if login and not login.logged_in:
            raise ValueError("Must be logged in")

        self._login: bool = bool(login)
        self.base = BaseClient(client=login.client if (login is not None) else client, language=language)

    def query_artists(self, query: str, /, limit: int = 10, *, offset: int = 0) -> Mapping[str, Any]:
        """Searches for an artist in the Spotify catalog"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = self.base.graphql_params(
            "searchArtists",
            {
                "searchTerm": query,
                "offset": offset,
                "limit": limit,
                "numberOfTopResults": 5,
                "includeAudiobooks": True,
                "includePreReleases": False,
            },
        )
        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not get artists", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise ArtistError("Invalid JSON")

        return resp.response

    def get_artist(self, artist_id: str, /, *, locale_code: str = "en") -> Mapping[str, Any]:
        """Gets an artist by ID"""
        artist_id = extract_spotify_id(artist_id, "artist")

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = self.base.graphql_params(
            "queryArtistOverview",
            {
                "uri": f"spotify:artist:{artist_id}",
                "locale": locale_code,
            },
        )
        resp = self.base.client.get(url, params=params, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not get artist by ID", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise ArtistError("Invalid JSON response")

        return resp.response

    def paginate_artists(self, query: str, /) -> Generator[Mapping[str, Any], None, None]:
        """Generator that fetches artists in chunks."""
        return paginate(
            lambda limit, offset: self.query_artists(query, limit=limit, offset=offset),
            "data.searchV2.artists.totalCount",
            "data.searchV2.artists.items",
            upper_limit=100,
        )

    def _do_follow(
        self,
        artist_id: str,
        /,
        *,
        action: Literal["addToLibrary", "removeFromLibrary"] = "addToLibrary",
    ) -> None:
        if not self._login:
            raise ValueError("Must be logged in")

        artist_id = extract_spotify_id(artist_id, "artist")

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = self.base.graphql_payload(
            action,
            {
                "uris": [f"spotify:artist:{artist_id}"],
            },
        )
        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not follow artist", error=resp.error.string)

    def follow(self, artist_id: str, /) -> None:
        """Follow an artist"""
        return self._do_follow(artist_id)

    def unfollow(self, artist_id: str, /) -> None:
        """Unfollow an artist"""
        return self._do_follow(artist_id, action="removeFromLibrary")
