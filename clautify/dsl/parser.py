"""Spotify DSL parser — Lark grammar + transformer → command dict."""

from pathlib import Path
from typing import Any, Dict

from lark import Lark, Token, Transformer

_GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()

_parser = Lark(_GRAMMAR, parser="earley", ambiguity="resolve")


class SpotifyTransformer(Transformer):
    """Transforms a Lark parse tree into a flat command dict."""

    def _cmd(self, action: str, **kwargs: Any) -> Dict[str, Any]:
        return {"action": action, **{k: v for k, v in kwargs.items() if v is not None}}

    def _query(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        return {"query": query, **{k: v for k, v in kwargs.items() if v is not None}}

    # --- terminals ---

    def BARE_ID(self, t: Token) -> str:
        return str(t)

    def ESCAPED_STRING(self, t: Token) -> str:
        return str(t)[1:-1]

    def NUMBER(self, t: Token) -> float:
        return float(t)

    def SIGNED_NUMBER(self, t: Token) -> int:
        return int(t)

    def VOL_DELTA(self, t: Token) -> int:
        return int(t)

    def MODE(self, t: Token) -> str:
        return str(t).lower()

    def KIND_KW(self, t: Token) -> str:
        return str(t).lower()

    def LIB_MUT(self, t: Token) -> str:
        return str(t).lower()

    def kind(self, items: list) -> str:
        return items[0]

    # --- actions ---

    def play(self, items):
        result = self._cmd("play", kind=items[0], target=items[1])
        if len(items) > 2:
            result.update(items[2])  # context dict
        return result

    def pause(self, items):
        return self._cmd("pause")

    def resume(self, items):
        return self._cmd("resume")

    def skip(self, items):
        return self._cmd("skip", n=items[0] if items else 1)

    def seek(self, items):
        return self._cmd("seek", position_s=items[0])

    def queue(self, items):
        return self._cmd("queue", kind=items[0], targets=list(items[1:]))

    def library_mut(self, items):
        lib_action = items[0]  # "add" or "remove"
        kind = items[1]
        targets = [x for x in items[2:] if isinstance(x, str)]
        context = next((x for x in items[2:] if isinstance(x, dict)), None)
        result = self._cmd(f"library_{lib_action}", kind=kind, targets=targets)
        if context:
            result.update(context)
        return result

    def library_create(self, items):
        return self._cmd("library_create", kind="playlist", target=items[0])

    def library_delete(self, items):
        return self._cmd("library_delete", kind="playlist", target=items[0])

    # --- queries ---

    def search(self, items):
        kind = items[0]
        terms = list(items[1:])
        return self._query("search", kind=kind, terms=terms)

    def info(self, items):
        return self._query("info", kind=items[0], target=items[1])

    def recommend(self, items):
        kind = items[0]
        if len(items) == 3:
            result = self._query("recommend", kind=kind, n=int(items[1]))
            result.update(items[2])  # context dict
        else:
            result = self._query("recommend", kind=kind)
            result.update(items[1])  # context dict
        return result

    def status(self, items):
        return self._query("status")

    def context(self, items):
        return {"context_kind": items[0], "context": items[1]}

    def library_list(self, items):
        return self._query("library_list", kind=items[0])

    # --- modifiers (all return (key, value) tuples) ---

    def volume(self, items):
        return ("volume", items[0])

    def volume_rel(self, items):
        return ("volume_rel", items[0])

    def mode(self, items):
        return ("mode", items[0])

    def device(self, items):
        return ("device", items[0])

    def limit(self, items):
        return ("limit", int(items[0]))

    def offset(self, items):
        return ("offset", int(items[0]))

    # --- root ---

    def start(self, items):
        if isinstance(items[0], dict):
            result = items[0]
            modifiers = items[1:]
        else:
            result = {"action": "set"}
            modifiers = items

        for key, val in modifiers:
            result[key] = val

        return result


def parse(command: str) -> Dict[str, Any]:
    """Parse a DSL command string into a command dict."""
    tree = _parser.parse(command)
    return SpotifyTransformer().transform(tree)
