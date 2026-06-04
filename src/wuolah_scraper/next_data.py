from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable


class _NextDataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._inside_next_data = False
        self._buffer: list[str] = []
        self.next_data_raw = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == 'script' and attrs_dict.get('id') == '__NEXT_DATA__':
            self._inside_next_data = True
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag == 'script' and self._inside_next_data:
            self.next_data_raw = ''.join(self._buffer)
            self._inside_next_data = False

    def handle_data(self, data: str) -> None:
        if self._inside_next_data:
            self._buffer.append(data)


def parse_next_data_from_html(html: str) -> dict[str, Any]:
    parser = _NextDataParser()
    parser.feed(html)
    if not parser.next_data_raw:
        raise ValueError('Could not find __NEXT_DATA__ in HTML')
    return json.loads(parser.next_data_raw)


def iter_queries(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    return list(
        next_data
        .get('props', {})
        .get('pageProps', {})
        .get('dehydratedState', {})
        .get('queries', [])
    )


def find_queries(next_data: dict[str, Any], predicate: Callable[[dict[str, Any]], bool]) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for query in iter_queries(next_data):
        query_key = query.get('queryKey')
        if not isinstance(query_key, list) or not query_key:
            continue
        head = query_key[0]
        if isinstance(head, dict) and predicate(head):
            matches.append(query)
    return matches


def first_query_data(next_data: dict[str, Any], predicate: Callable[[dict[str, Any]], bool]) -> Any:
    matches = find_queries(next_data, predicate)
    if not matches:
        return None
    return matches[0].get('state', {}).get('data')


def save_json(path: str | Path, payload: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_slug(value: str) -> str:
    value = value.strip().strip('/')
    value = value.replace('/', '__')
    value = re.sub(r'[^a-zA-Z0-9_.-]+', '-', value)
    return value.strip('-') or 'root'
