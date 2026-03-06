"""Generic Spotify API pagination helper."""

from collections.abc import Generator
from typing import Any, Callable

from clautify.utils.strings import deep_get


def paginate(
    query_fn: Callable[[int, int], Any],
    total_path: str,
    items_path: str,
    upper_limit: int,
) -> Generator[Any, None, None]:
    """Generic pagination over Spotify API queries.

    Args:
        query_fn: ``(limit, offset) -> response_dict``. Callers bind any
            extra args (e.g. search term) via a lambda.
        total_path: Dot-separated key path to total count in the response
            (e.g. ``"data.searchV2.tracksV2.totalCount"``).
        items_path: Dot-separated key path to items in the response
            (e.g. ``"data.searchV2.tracksV2.items"``).
        upper_limit: Page size per request.
    """
    total_keys = total_path.split(".")
    items_keys = items_path.split(".")

    first = query_fn(upper_limit, 0)
    total_count = deep_get(first, *total_keys) or 0
    yield deep_get(first, *items_keys)

    if total_count <= upper_limit:
        return

    offset = upper_limit
    while offset < total_count:
        page = query_fn(upper_limit, offset)
        yield deep_get(page, *items_keys)
        offset += upper_limit
