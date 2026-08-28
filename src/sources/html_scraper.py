from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup


from .base import SourceFetcher


class HtmlScraper(SourceFetcher):
    """Scraper for sources that expose articles through HTML pages."""

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
            html = response.read()

        soup = BeautifulSoup(html, "html.parser")

        return self._parse(soup)

    def _parse(self, soup: BeautifulSoup) -> list[dict[str, Any]]:
        parser = self.source.parser

        item_selector = parser.get("item_selector")
        fields = parser.get("fields", {})

        if not item_selector:
            raise ValueError(
                f"Source '{self.source.name}' does not define "
                "'item_selector'."
            )

        if not fields:
            raise ValueError(
                f"Source '{self.source.name}' does not define "
                "'fields'."
            )

        items = soup.select(item_selector)

        articles: list[dict[str, Any]] = []

        for item in items:
            article: dict[str, Any] = {}

            for field_name, field_config in fields.items():
                if not isinstance(field_config, dict):
                    raise ValueError(
                        f"Invalid configuration for field '{field_name}' "
                        f"in source '{self.source.name}'."
                    )

                selector = field_config.get("selector")

                if not selector:
                    raise ValueError(
                        f"Field '{field_name}' in source "
                        f"'{self.source.name}' does not define 'selector'."
                    )

                element = item.select_one(selector)

                if element is None:
                    article[field_name] = None
                    continue

                attribute = field_config.get("attribute")

                if attribute:
                    article[field_name] = element.get(attribute)
                else:
                    article[field_name] = element.get_text(
                        " ",
                        strip=True,
                    )

            articles.append(article)

        return articles