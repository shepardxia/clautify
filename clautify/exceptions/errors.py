__all__ = [
    "ParentException",
    "LoginError",
    "UserError",
    "PlaylistError",
    "SaverError",
    "SongError",
    "ArtistError",
    "BaseClientError",
    "RequestError",
    "WebSocketError",
    "PlayerError",
    "AlbumError",
]


class ParentException(Exception):
    def __init__(self, message: str, error: str | None = None) -> None:
        super().__init__(message)
        self.error = error


# Login.py exceptions
class LoginError(ParentException):
    pass


# User.py exceptions
class UserError(ParentException):
    pass


# Playlist.py exceptions
class PlaylistError(ParentException):
    pass


# Saver.py exceptions
class SaverError(ParentException):
    pass


# Song.py exceptions
class SongError(ParentException):
    pass


# Artist.py exceptions
class ArtistError(ParentException):
    pass


# client.py exceptions
class BaseClientError(ParentException):
    pass


# request.py exceptions
class RequestError(ParentException):
    pass


# websocket.py exceptions
class WebSocketError(ParentException):
    pass


# player.py exceptions
class PlayerError(ParentException):
    pass


# album.py exceptions
class AlbumError(ParentException):
    pass
