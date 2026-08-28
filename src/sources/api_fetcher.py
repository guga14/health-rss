#O Fetcher é responsável por obter e extrair informação, mas não por decidir como essa informação se transforma definitivamente num Article.
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .base import SourceFetcher


class ApiFetcher(SourceFetcher):
    """Fetcher for sources that expose an API."""

    def fetch(self) -> list[dict[str, Any]]:
        url = self.source.url

        if self.source.params:
            query = urlencode(self.source.params)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{query}"

        request = Request(
            url,
            headers=self.source.headers,
            method="GET",
        )

        with urlopen(request, timeout=30) as response:
            data = response.read()

        return self._parse_json(data)

    def _parse_json(self, data: bytes) -> list[dict[str, Any]]:
        import json

        payload = json.loads(data)

        parser = self.source.parser

        items_path = parser.get("items_path")
        fields = parser.get("fields", {})

        if not items_path:
            raise ValueError(
                f"Source '{self.source.name}' does not define "
                "'items_path'."
            )

        if not fields:
            raise ValueError(
                f"Source '{self.source.name}' does not define "
                "'fields'."
            )

        items = self._get_nested_value(payload, items_path)

        if not isinstance(items, list):
            raise ValueError(
                f"Expected a list at '{items_path}' for source "
                f"'{self.source.name}'."
            )

        articles: list[dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            article = {
                field_name: self._get_nested_value(item, path)
                for field_name, path in fields.items()
            }

            articles.append(article)

        return articles

    @staticmethod
    def _get_nested_value(data: Any, path: str) -> Any:
        value = data

        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None

        return value