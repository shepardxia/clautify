# clautify

A DSL-driven Spotify controller. One command string does what used to take five API calls.

Built on [SpotAPI](https://github.com/Aran404/SpotAPI) by **Aran** — a reverse-engineered Spotify Connect client that requires no Premium and no API key. We added a Lark grammar DSL, stripped unused modules, and renamed the package.

**Note**: This project is intended solely for educational purposes. Accessing private endpoints without authorization may violate Spotify's terms of service.

## Setup

### 1. Install

```bash
pip install -e .
```

Requires Python 3.10+.

### 2. Get your `sp_dc` cookie

1. Open [open.spotify.com](https://open.spotify.com) in your browser and log in
2. Open DevTools (`F12`) → **Application** → **Cookies** → `https://open.spotify.com`
3. Copy the value of `sp_dc`

### 3. Save it (one-time)

```python
from clautify.dsl import SpotifySession

SpotifySession.setup("paste_your_sp_dc_here")
# Saved to ~/.config/clautify/session.json
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
- Quoted strings are auto-resolved via search — no need to look up URIs first
- State modifiers (`volume`, `mode`, `device`/`on`) only compose with actions
- Query modifiers (`limit`, `offset`) only compose with queries
- Mixing them is a parse error

## Credits

Built on [**SpotAPI**](https://github.com/Aran404/SpotAPI) by **Aran** — reverse-engineered Spotify Connect API client. Original codebase provided the HTTP layer, login, player, and all Spotify endpoint wrappers. We added the Lark DSL layer and stripped unused modules.

## License

This project is licensed under the **GPL 3.0** License. See [LICENSE](https://choosealicense.com/licenses/gpl-3.0/) for details.
