#O Fetcher é responsável por obter e extrair informação, mas não por decidir como essa informação se transforma definitivamente num Article.
import json
from typing import Any
from urllib.request import Request, urlopen

from .base import SourceFetcher


class ApiFetcher(SourceFetcher):
    """Fetcher for sources that expose a JSON API."""

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch JSON data and return normalized article dictionaries."""
        request = Request(
            self.source.url,
            method="GET",
        )

        with urlopen(request, timeout=30) as response:
            data = response.read()

        return self._parse_json(data)

    def _parse_json(self, data: bytes) -> list[dict[str, Any]]:
        """Parse the JSON response and extract article data."""
        payload = json.loads(data)

        parser = self.source.parser
        items_path = parser.get("items_path")
        fields = parser.get("fields")

        if not isinstance(items_path, str):
            raise ValueError(
                f"Source '{self.source.name}' must define "
                "'parser.items_path' as a string."
            )

        if not isinstance(fields, dict) or not fields:
            raise ValueError(
                f"Source '{self.source.name}' must define "
                "'parser.fields'."
            )

        if items_path:
            items = self._get_nested_value(payload, items_path)
        else:
            items = payload

        if not isinstance(items, list):
            raise ValueError(
                f"Expected a list at '{items_path}' for source "
                f"'{self.source.name}'."
            )

        articles: list[dict[str, Any]] = []

        for item in items:
            if not isinstance(item, dict):
                continue

            articles.append(
                self._extract_fields(item, fields)
            )

        return articles

    def _extract_fields(
        self,
        item: dict[str, Any],
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract configured fields from one API item."""
        article: dict[str, Any] = {}

        for field_name, field_config in fields.items():
            if not isinstance(field_config, dict):
                raise ValueError(
                    f"Field '{field_name}' in source "
                    f"'{self.source.name}' must be an object."
                )

            path = field_config.get("path")

            if not isinstance(path, str):
                raise ValueError(
                    f"Field '{field_name}' in source "
                    f"'{self.source.name}' must define "
                    "'path' as a string."
                )

            article[field_name] = self._get_nested_value(
                item,
                path,
            )

        return article

    @staticmethod
    def _get_nested_value(
        data: Any,
        path: str,
    ) -> Any:
        """
        Resolve a dotted path in nested dictionaries or lists.

        Examples:
            "title"
            "article.title"
            "authors.0.name"
        """
        if path == "":
            return data

        value = data

        for part in path.split("."):
            if isinstance(value, dict):
                value = value.get(part)

            elif isinstance(value, list):
                try:
                    index = int(part)
                except ValueError:
                    return None

                if index < 0 or index >= len(value):
                    return None

                value = value[index]

            else:
                return None

        return value