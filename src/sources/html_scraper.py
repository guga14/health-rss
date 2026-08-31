from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

from .base import SourceFetcher


class HtmlScraper(SourceFetcher):
    """Scraper for sources that expose articles through HTML pages."""

    def fetch(self) -> list[dict[str, Any]]:
        """Fetch HTML and return normalized article dictionaries."""
        request = Request(
            self.source.url,
            method="GET",
        )

        with urlopen(request, timeout=30) as response:
            html = response.read()

        soup = BeautifulSoup(html, "html.parser")

        return self._parse(soup)

    def _parse(
        self,
        soup: BeautifulSoup,
    ) -> list[dict[str, Any]]:
        """Parse the HTML document using the source parser configuration."""
        parser = self.source.parser

        item_selector = parser.get("item_selector")
        fields = parser.get("fields")

        if not isinstance(item_selector, str) or not item_selector.strip():
            raise ValueError(
                f"Source '{self.source.name}' must define "
                "'parser.item_selector' as a non-empty string."
            )

        if not isinstance(fields, dict) or not fields:
            raise ValueError(
                f"Source '{self.source.name}' must define "
                "'parser.fields'."
            )

        items = soup.select(item_selector)

        articles: list[dict[str, Any]] = []

        for item in items:
            if not isinstance(item, Tag):
                continue

            article = self._extract_fields(
                item,
                fields,
            )

            articles.append(article)

        return articles

    def _extract_fields(
        self,
        item: Tag,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract configured fields from one HTML item."""
        article: dict[str, Any] = {}

        for field_name, field_config in fields.items():
            if not isinstance(field_config, dict):
                raise ValueError(
                    f"Field '{field_name}' in source "
                    f"'{self.source.name}' must be an object."
                )

            selector = field_config.get("selector")

            if not isinstance(selector, str) or not selector.strip():
                raise ValueError(
                    f"Field '{field_name}' in source "
                    f"'{self.source.name}' must define "
                    "'selector' as a non-empty string."
                )

            element = item.select_one(selector)

            if element is None:
                article[field_name] = None
                continue

            attribute = field_config.get("attribute")

            if attribute is not None:
                if not isinstance(attribute, str):
                    raise ValueError(
                        f"Field '{field_name}' in source "
                        f"'{self.source.name}' must define "
                        "'attribute' as a string."
                    )

                article[field_name] = element.get(attribute)
            else:
                article[field_name] = element.get_text(
                    " ",
                    strip=True,
                )

        return article