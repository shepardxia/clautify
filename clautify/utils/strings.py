import ast
import os
import random
import re
from typing import Dict, List, Tuple

from bs4 import BeautifulSoup

__all__ = [
    "extract_spotify_id",
    "random_hex_string",
    "parse_json_string",
    "random_nonce",
]


def extract_spotify_id(identifier: str, kind: str) -> str:
    """Extract bare Spotify ID from a URI, URL, or pass through a bare ID.

    Handles:
    - ``spotify:track:abc123`` → ``abc123``
    - ``https://open.spotify.com/track/abc123`` → ``abc123``
    - ``abc123`` → ``abc123``
    """
    prefix = f"spotify:{kind}:"
    if identifier.startswith(prefix):
        return identifier[len(prefix) :]
    if f"{kind}/" in identifier:
        return identifier.split(f"{kind}/")[-1].split("?")[0]
    if f"{kind}:" in identifier:
        return identifier.split(f"{kind}:")[-1]
    return identifier


def extract_mappings(js_code: str) -> Tuple[Dict[int, str], Dict[int, str]]:
    pattern = r"\{\d+:\"[^\"]+\"(?:,\d+:\"[^\"]+\")*\}"
    matches = re.findall(pattern, js_code)

    if len(matches) < 2:
        raise ValueError("Could not find both mappings in the JS code.")

    mapping1 = ast.literal_eval(matches[3])
    mapping2 = ast.literal_eval(matches[4])

    return mapping1, mapping2


def combine_chunks(name_map: Dict[int, str], hash_map: Dict[int, str]) -> List[str]:
    combined: List[str] = []
    for key in name_map:
        if key in hash_map:
            filename = f"{name_map[key]}.{hash_map[key]}.js"
            combined.append(filename)
    return combined


def extract_js_links(html_content: str) -> List[str]:
    """Extracts all JavaScript links from a given HTML content."""
    soup = BeautifulSoup(html_content, "html.parser")
    js_links = []

    for script_tag in soup.find_all("script", src=True):
        src = script_tag["src"]
        if src.endswith(".js"):
            js_links.append(str(src))

    return js_links


def random_hex_string(length: int):
    """Used by Spotify internally"""
    num_bytes = (length + 1) // 2
    random_bytes = os.urandom(num_bytes)
    hex_string = random_bytes.hex()
    return hex_string[:length]


def parse_json_string(b: str, s: str) -> str:
    start_index = b.find(f'{s}":"')
    if start_index == -1:
        raise ValueError(f'Substring "{s}":" not found in JSON string')

    value_start_index = start_index + len(s) + 3
    value_end_index = b.find('"', value_start_index)
    if value_end_index == -1:
        raise ValueError(f'Closing double quote not found after "{s}":"')

    return b[value_start_index:value_end_index]


def random_nonce() -> str:
    return "".join(str(random.getrandbits(32)) for _ in range(2))
