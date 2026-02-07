# Legal Notice

> **Disclaimer**: This repository and any associated code are provided "as is" without warranty of any kind, either expressed or implied. The author of this repository does not accept any responsibility for the use or misuse of this repository or its contents. The author does not endorse any actions or consequences arising from the use of this repository. Any copies, forks, or re-uploads made by other users are not the responsibility of the author. The repository is solely intended as a Proof Of Concept for educational purposes regarding the use of a service's private API. By using this repository, you acknowledge that the author makes no claims about the accuracy, legality, or safety of the code and accepts no liability for any issues that may arise. More information can be found [HERE](./LEGAL_NOTICE.md).

# SpotAPI + DSL

A command-driven interface for Spotify built on top of [SpotAPI](https://github.com/Aran404/SpotAPI) by **Aran**. Control playback, manage playlists, search, and more using plain-text commands parsed by a Lark grammar.

**Note**: This project is intended solely for educational purposes. Accessing private endpoints without authorization may violate Spotify's terms of service.

## Setup

### 1. Install

```bash
pip install -e ".[websocket,redis,pymongo]"
```

Requires Python 3.10+.

### 2. Get your `sp_dc` cookie

1. Open [open.spotify.com](https://open.spotify.com) in your browser and log in
2. Open DevTools (`F12`) → **Application** → **Cookies** → `https://open.spotify.com`
3. Copy the value of `sp_dc`

### 3. Save it (one-time)

```python
from spotapi.dsl import SpotifySession

SpotifySession.setup("paste_your_sp_dc_here")
# Saved to ~/.config/spotapi/session.json
```

The `sp_dc` cookie typically lasts ~1 year. Re-run `setup()` if it expires.

### 4. Use it

```python
session = SpotifySession.from_config()

session.run('play "Bohemian Rhapsody" volume 70 mode shuffle')
session.run('search "jazz" artists limit 5')
session.run('add spotify:track:abc to spotify:playlist:def')

session.close()
```

Every `run()` call returns `{"status": "ok", ...}` or raises `DSLError`.

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
| `add ... to` | `add spotify:track:abc to spotify:playlist:def` |
| `remove ... from` | `remove spotify:track:abc from spotify:playlist:def` |
| `create playlist` | `create playlist "Road Trip"` |
| `delete playlist` | `delete playlist spotify:playlist:abc` |

**State modifiers** compose with any action (or stand alone):

```
play "jazz" volume 70 mode shuffle on "Kitchen Speaker"
volume 50 mode repeat
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
| `history` | `history limit 10` |
| `recommend` | `recommend 10 for spotify:playlist:abc` |

**Query modifiers**: `limit N` and `offset N` compose with queries only.

### Grammar Rules

- Targets are either Spotify URIs (`spotify:track:abc`) or quoted strings (`"Bohemian Rhapsody"`)
- State modifiers (`volume`, `mode`, `device`/`on`) only compose with actions
- Query modifiers (`limit`, `offset`) only compose with queries
- Mixing them is a parse error

## Low-Level API

The full SpotAPI interface remains available. See the original docs:

- [Artist](./docs/artist.md) · [Album](./docs/album.md) · [Song](./docs/song.md) · [Playlist](./docs/playlist.md) · [Player](./docs/player.md)
- [Login](./docs/login.md) · [Password](./docs/password.md) · [Creator](./docs/creator.md) · [Family](./docs/family.md)
- [Public](./docs/public.md) · [Status](./docs/status.md) · [User](./docs/user.md)

For fresh login with captcha solver (instead of cookie import):

```python
from spotapi import Login, Config, NoopLogger, solver_clients

cfg = Config(solver=solver_clients.Capsolver("YOUR_API_KEY"), logger=NoopLogger())
login = Login(cfg, "PASSWORD", email="EMAIL")
login.login()
session = SpotifySession(login)
```

## Credits

Built on [**SpotAPI**](https://github.com/Aran404/SpotAPI) by **Aran** — a reverse-engineered Spotify Connect API client that requires no Premium and no API key.

## License

This project is licensed under the **GPL 3.0** License. See [LICENSE](https://choosealicense.com/licenses/gpl-3.0/) for details.
