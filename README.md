# Legal Notice

> **Disclaimer**: This repository and any associated code are provided "as is" without warranty of any kind, either expressed or implied. The author of this repository does not accept any responsibility for the use or misuse of this repository or its contents. The author does not endorse any actions or consequences arising from the use of this repository. Any copies, forks, or re-uploads made by other users are not the responsibility of the author. The repository is solely intended as a Proof Of Concept for educational purposes regarding the use of a service's private API. By using this repository, you acknowledge that the author makes no claims about the accuracy, legality, or safety of the code and accepts no liability for any issues that may arise. More information can be found [HERE](./LEGAL_NOTICE.md).

# SpotAPI + DSL

A command-driven interface for Spotify built on top of [SpotAPI](https://github.com/Aran404/SpotAPI) by **Aran**. Control playback, manage playlists, search, and more using plain-text commands parsed by a Lark grammar.

**Note**: This project is intended solely for educational purposes. Accessing private endpoints without authorization may violate Spotify's terms of service.

## Quick Start

```python
from spotapi.dsl import SpotifySession
from spotapi.login import Login

login = Login.from_cookies(cookie_dump, cfg)
session = SpotifySession(login)

# Playback
session.run('play "Bohemian Rhapsody" volume 0.7 mode shuffle')
session.run('skip 2')
session.run('pause')

# Search & discovery
result = session.run('search "jazz" artists limit 5')
result = session.run('info spotify:artist:1dfeR4HaWDbWqFHLkxsg1d')
result = session.run('recommend 10 for spotify:playlist:37i9dQZF1DXcBWIGoYBM5M')

# Playlist management
session.run('create playlist "Road Trip"')
session.run('add spotify:track:4uLU6hMCjMI75M1A2tKUQC to spotify:playlist:abc123')
session.run('like spotify:track:4uLU6hMCjMI75M1A2tKUQC')

# Standalone state changes
session.run('volume 0.5')
session.run('mode repeat')
session.run('device "Kitchen Speaker"')

session.close()
```

Every `run()` call returns a dict with `"status": "ok"` plus command-specific data, or raises `DSLError` on failure.

## Command Reference

### Actions (mutate state)

| Command | Example |
|---------|---------|
| `play` | `play "Bohemian Rhapsody"` / `play spotify:track:abc in spotify:playlist:def` |
| `pause` / `resume` | `pause` |
| `skip` | `skip 3` / `skip -1` (backwards) |
| `seek` | `seek 30000` (ms) |
| `queue` | `queue "Stairway to Heaven"` |
| `like` / `unlike` | `like spotify:track:abc` |
| `follow` / `unfollow` | `follow spotify:artist:abc` |
| `save` / `unsave` | `save spotify:playlist:abc` |
| `add … to` | `add spotify:track:abc to spotify:playlist:def` |
| `remove … from` | `remove spotify:track:abc from spotify:playlist:def` |
| `create playlist` | `create playlist "Road Trip"` |
| `delete playlist` | `delete playlist spotify:playlist:abc` |

**State modifiers** compose with any action (or stand alone):

```
play "jazz" volume 0.7 mode shuffle on "Kitchen Speaker"
volume 0.5 mode repeat
```

### Queries (read state)

| Command | Example |
|---------|---------|
| `search` | `search "jazz" artists limit 5 offset 10` |
| `now playing` | `now playing` |
| `get queue` | `get queue` |
| `get devices` | `get devices` |
| `library` | `library playlists limit 20` |
| `info` | `info spotify:track:abc` |
| `history` | `history` |
| `recommend` | `recommend 10 for spotify:playlist:abc` |

**Query modifiers**: `limit N` and `offset N` compose with queries only.

### Grammar Rules

- Targets are either Spotify URIs (`spotify:track:abc`) or quoted strings (`"Bohemian Rhapsody"`)
- State modifiers (`volume`, `mode`, `device`/`on`) only compose with actions
- Query modifiers (`limit`, `offset`) only compose with queries
- Mixing them is a parse error — `search "jazz" volume 0.5` will fail

## Architecture

```
"play 'jazz' volume 0.7"
        │
        ▼
   ┌─────────┐
   │ grammar  │  grammar.lark — Lark Earley parser
   │  .lark   │
   └────┬─────┘
        │  parse tree
        ▼
   ┌─────────┐
   │ parser   │  SpotifyTransformer → flat dict
   │  .py     │  {"action":"play","target":"jazz","volume":0.7}
   └────┬─────┘
        │  command dict
        ▼
   ┌──────────┐
   │ executor  │  Dispatches to SpotAPI classes
   │  .py      │  Player, Song, Artist, Playlist (lazy init)
   └────┬──────┘
        │  result dict
        ▼
   {"status":"ok","action":"play","resolved_uri":"spotify:track:..."}
```

- **Player** (WebSocket + threads) is only created on the first playback command
- **Song** and **Artist** are lazily initialized on first use
- Quoted string targets trigger an automatic search → resolve to URI
- All SpotAPI exceptions are wrapped in `DSLError` with the original command attached

## Installation

```bash
pip install -e ".[websocket,redis,pymongo]"
```

Requires Python 3.10+ (uses `match` statements).

## Low-Level API

The full SpotAPI interface remains available for direct use. See the original docs:

- [Artist](./docs/artist.md) · [Album](./docs/album.md) · [Song](./docs/song.md) · [Playlist](./docs/playlist.md) · [Player](./docs/player.md)
- [Login](./docs/login.md) · [Password](./docs/password.md) · [Creator](./docs/creator.md) · [Family](./docs/family.md)
- [Public](./docs/public.md) · [Status](./docs/status.md) · [User](./docs/user.md)

### Cookie-based Authentication

```python
from spotapi import Login, Config, NoopLogger, solver_clients

cfg = Config(
    solver=solver_clients.Capsolver("YOUR_API_KEY"),
    logger=NoopLogger(),
)

instance = Login(cfg, "YOUR_PASSWORD", email="YOUR_EMAIL")
instance.login()
```

Or import cookies directly — see [upstream SpotAPI](https://github.com/Aran404/SpotAPI) for full details.

## Credits

Built on [**SpotAPI**](https://github.com/Aran404/SpotAPI) by **Aran** — a reverse-engineered Spotify Connect API client that requires no Premium and no API key.

## License

This project is licensed under the **GPL 3.0** License. See [LICENSE](https://choosealicense.com/licenses/gpl-3.0/) for details.
