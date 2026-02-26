from __future__ import annotations

from collections.abc import Generator, Mapping
from typing import Any

from clautify.client import BaseClient
from clautify.exceptions import AlbumError
from clautify.http.request import TLSClient
from clautify.types.annotations import enforce
from clautify.utils.pagination import paginate
from clautify.utils.strings import extract_spotify_id

__all__ = ["PublicAlbum", "AlbumError"]


@enforce
class PublicAlbum:
    """
    Allows you to get all public information on an album.

    Parameters
    ----------
    album (str): The Spotify URI of the album.
    client (TLSClient): An instance of TLSClient to use for requests.
    """

    __slots__ = (
        "base",
        "album_id",
        "album_link",
    )

    def __init__(
        self,
        album: str,
        /,
        *,
        client: TLSClient = TLSClient("chrome_120", "", auto_retries=3),
        language: str = "en",
    ) -> None:
        self.base = BaseClient(client=client, language=language)
        self.album_id = extract_spotify_id(album, "album")
        self.album_link = f"https://open.spotify.com/album/{self.album_id}"

    def get_album_info(self, limit: int = 25, *, offset: int = 0) -> Mapping[str, Any]:
        """Gets the public public information"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = self.base.graphql_params(
            "getAlbum",
            {
                "locale": "",
                "uri": f"spotify:album:{self.album_id}",
                "offset": offset,
                "limit": limit,
            },
        )
        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise AlbumError("Could not get album info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise AlbumError("Invalid JSON")

        return resp.response

    def paginate_album(self) -> Generator[Mapping[str, Any], None, None]:
        """Generator that fetches album tracks in chunks."""
        return paginate(
            lambda limit, offset: self.get_album_info(limit=limit, offset=offset),
            "data.albumUnion.tracksV2.totalCount",
            "data.albumUnion.tracksV2.items",
            upper_limit=343,
        )
