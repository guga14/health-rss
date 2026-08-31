import logging
from datetime import datetime
from typing import Any
from urllib.parse import urljoin

from ..models.article import Article
from ..models.source import Source


logger = logging.getLogger(__name__)


class ArticleCleaner:
    """Convert extracted source data into normalized Article objects."""

    def __init__(self, source: Source) -> None:
        self.source = source

    def clean(self, raw_articles: list[dict[str, Any]]) -> list[Article]:
        """Clean and normalize extracted articles."""
        articles: list[Article] = []

        for raw_article in raw_articles:
            try:
                article = self._clean_article(raw_article)
            except (TypeError, ValueError, KeyError) as exc:
                logger.warning(
                    "Skipping invalid article from source '%s': %s",
                    self.source.name,
                    exc,
                )
                continue

            articles.append(article)

        return articles

    def _clean_article(self, raw: dict[str, Any]) -> Article:
        title = self._clean_required_text(raw, "title")
        link = self._clean_link(raw)

        description = self._clean_optional_text(
            raw.get("description")
        )

        published = self._clean_date(
            raw,
            "published",
            required=False,
        )

        author = self._clean_optional_text(
            raw.get("author")
        )

        category = self._clean_categories(
            raw.get("category")
        )

        return Article(
            title=title,
            link=link,
            published=published,
            source=self.source.name,
            description=description,
            author=author,
            category=category,
        )

    def _clean_required_text(
        self,
        raw: dict[str, Any],
        field: str,
    ) -> str:
        value = raw.get(field)

        if not isinstance(value, str):
            raise ValueError(
                f"Field '{field}' is missing or is not text."
            )

        value = value.strip()

        if not value:
            raise ValueError(
                f"Field '{field}' is empty."
            )

        return value

    @staticmethod
    def _clean_optional_text(value: Any) -> str | None:
        if value is None:
            return None

        if not isinstance(value, str):
            raise ValueError(
                "Optional text field is not text."
            )

        value = value.strip()

        return value or None

    def _clean_link(self, raw: dict[str, Any]) -> str:
        link = self._clean_required_text(raw, "link")

        absolute_link = urljoin(
            self.source.url,
            link,
        )

        if not absolute_link:
            raise ValueError(
                "Field 'link' could not be normalized."
            )

        return absolute_link

    def _clean_date(
        self,
        raw: dict[str, Any],
        field: str,
        *,
        required: bool,
    ) -> datetime | None:
        value = raw.get(field)

        if value is None or value == "":
            if required:
                raise ValueError(
                    f"Field '{field}' is missing."
                )

            return None

        if isinstance(value, datetime):
            return value

        if not isinstance(value, str):
            raise ValueError(
                f"Field '{field}' is not a supported date value."
            )

        value = value.strip()

        if not value:
            if required:
                raise ValueError(
                    f"Field '{field}' is empty."
                )

            return None

        field_config = self._get_field_config(field)
        date_format = field_config.get("date_format")

        if date_format:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                )
            except ValueError as exc:
                raise ValueError(
                    f"Field '{field}' does not match date format "
                    f"'{date_format}'."
                ) from exc

        return self._parse_common_date(
            value,
            field,
        )

    @staticmethod
    def _parse_common_date(
        value: str,
        field: str,
    ) -> datetime:
        normalized = value.replace(
            "Z",
            "+00:00",
        )

        try:
            return datetime.fromisoformat(
                normalized,
            )
        except ValueError:
            pass

        common_formats = (
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%d/%m/%Y",
            "%d-%m-%Y",
            "%B %d, %Y",
            "%d %B %Y",
            "%b %d, %Y",
            "%d %b %Y",
        )

        for date_format in common_formats:
            try:
                return datetime.strptime(
                    value,
                    date_format,
                )
            except ValueError:
                continue

        raise ValueError(
            f"Could not parse date in field '{field}': {value!r}"
        )

    @staticmethod
    def _clean_categories(
        value: Any,
    ) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            raise ValueError(
                "Field 'category' must be text or a list."
            )

        categories: list[str] = []
        seen: set[str] = set()

        for category in values:
            if not isinstance(category, str):
                raise ValueError(
                    "Category values must be text."
                )

            category = category.strip()

            if not category or category in seen:
                continue

            categories.append(category)
            seen.add(category)

        return categories

    def _get_field_config(
        self,
        field: str,
    ) -> dict[str, Any]:
        fields = self.source.parser.get(
            "fields",
            {}
        )

        config = fields.get(
            field,
            {}
        )

        if not isinstance(config, dict):
            return {}

        return config