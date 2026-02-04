"""Spotify DSL — session-based command interface.

Usage:
    from spotapi.dsl import SpotifySession
    from spotapi.login import Login

    login = Login.from_cookies(cookie_dump, cfg)
    session = SpotifySession(login)

    result = session.run('play "Bohemian Rhapsody" volume 0.7 mode shuffle')
    result = session.run('search "jazz" artists limit 5')
    result = session.run('add spotify:track:abc to "Road Trip"')

    session.close()
"""

from typing import Any, Dict

from spotapi.dsl.parser import parse
from spotapi.dsl.executor import SpotifyExecutor, DSLError
from spotapi.login import Login

__all__ = ["SpotifySession", "parse", "DSLError"]


class SpotifySession:
    """Session-based DSL entry point for Spotify commands.

    Holds a Login and lazily initializes SpotAPI classes as needed.
    Player (heavyweight — WebSocket + threads) is only created on
    first playback command.
    """

    def __init__(self, login: Login):
        self._executor = SpotifyExecutor(login)

    def run(self, command: str) -> Dict[str, Any]:
        """Parse and execute a DSL command string.

        Returns a result dict with a "status" key ("ok" on success)
        plus command-specific data.

        Raises DSLError on parse or execution failure.
        """
        try:
            parsed = parse(command)
        except Exception as e:
            raise DSLError(f"Parse error: {e}") from e

        return self._executor.execute(parsed)

    def close(self) -> None:
        """Clean up resources (WebSocket, threads)."""
        self._executor.close()
