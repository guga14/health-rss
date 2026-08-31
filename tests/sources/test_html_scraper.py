from typing import Any

import pytest
from bs4 import BeautifulSoup

from src.models.source import Source
from src.sources.html_scraper import HtmlScraper


def make_scraper(
    *,
    item_selector: str = "article",
    fields: dict[str, Any],
) -> HtmlScraper:
    source = Source(
        id="example",
        name="Example HTML Source",
        url="https://example.com/news",
        type="html",
        parser={
            "item_selector": item_selector,
            "fields": fields,
        },
    )

    return HtmlScraper(source)


def test_parse_extracts_text_from_selector() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <main>
            <article>
                <h2>Example article</h2>
            </article>
        </main>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "title": "Example article",
        }
    ]


def test_parse_extracts_attribute_when_configured() -> None:
    scraper = make_scraper(
        fields={
            "link": {
                "selector": "h2 a",
                "attribute": "href",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <h2>
                <a href="/news/example">Example article</a>
            </h2>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "link": "/news/example",
        }
    ]


def test_parse_extracts_multiple_fields() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2 a",
            },
            "link": {
                "selector": "h2 a",
                "attribute": "href",
            },
            "description": {
                "selector": "p.summary",
            },
            "published": {
                "selector": "time",
                "attribute": "datetime",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <h2>
                <a href="/news/example">
                    Example article
                </a>
            </h2>
            <p class="summary">
                Example description.
            </p>
            <time datetime="2026-08-31T12:00:00Z">
                31 August 2026
            </time>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "title": "Example article",
            "link": "/news/example",
            "description": "Example description.",
            "published": "2026-08-31T12:00:00Z",
        }
    ]


def test_parse_supports_complex_css_selectors() -> None:
    scraper = make_scraper(
        item_selector="main.news > section.latest article.card",
        fields={
            "title": {
                "selector": "header > h2.title a",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <main class="news">
            <section class="latest">
                <article class="card">
                    <header>
                        <h2 class="title">
                            <a href="/1">First article</a>
                        </h2>
                    </header>
                </article>
                <article class="other">
                    <header>
                        <h2 class="title">
                            <a href="/2">Other article</a>
                        </h2>
                    </header>
                </article>
                <article class="card">
                    <header>
                        <h2 class="title">
                            <a href="/3">Third article</a>
                        </h2>
                    </header>
                </article>
            </section>
        </main>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "title": "First article",
        },
        {
            "title": "Third article",
        },
    ]


def test_parse_returns_none_when_field_selector_matches_nothing() -> None:
    scraper = make_scraper(
        fields={
            "description": {
                "selector": "p.description",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <h2>Example article</h2>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "description": None,
        }
    ]


def test_parse_returns_none_when_attribute_does_not_exist() -> None:
    scraper = make_scraper(
        fields={
            "link": {
                "selector": "a",
                "attribute": "href",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <a>Example article</a>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "link": None,
        }
    ]


def test_parse_uses_first_matching_element_for_field() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <h2>First title</h2>
            <h2>Second title</h2>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "title": "First title",
        }
    ]


def test_parse_strips_and_normalizes_text_whitespace() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <h2>
                Example
                <span>article</span>
            </h2>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "title": "Example article",
        }
    ]


def test_parse_requires_item_selector() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    scraper.source.parser["item_selector"] = None

    soup = BeautifulSoup(
        "<article><h2>Article</h2></article>",
        "html.parser",
    )

    with pytest.raises(
        ValueError,
        match="parser.item_selector",
    ):
        scraper._parse(soup)


def test_parse_requires_fields() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    scraper.source.parser["fields"] = {}

    soup = BeautifulSoup(
        "<article><h2>Article</h2></article>",
        "html.parser",
    )

    with pytest.raises(
        ValueError,
        match="parser.fields",
    ):
        scraper._parse(soup)


def test_extract_fields_requires_field_configuration_to_be_mapping() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    soup = BeautifulSoup(
        "<article><h2>Article</h2></article>",
        "html.parser",
    )

    item = soup.select_one("article")

    assert item is not None

    with pytest.raises(
        ValueError,
        match="must be an object",
    ):
        scraper._extract_fields(
            item,
            {
                "title": "h2",
            },
        )


def test_extract_fields_requires_selector() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    soup = BeautifulSoup(
        "<article><h2>Article</h2></article>",
        "html.parser",
    )

    item = soup.select_one("article")

    assert item is not None

    with pytest.raises(
        ValueError,
        match="must define 'selector'",
    ):
        scraper._extract_fields(
            item,
            {
                "title": {},
            },
        )


def test_extract_fields_requires_attribute_to_be_string() -> None:
    scraper = make_scraper(
        fields={
            "link": {
                "selector": "a",
                "attribute": "href",
            },
        },
    )

    soup = BeautifulSoup(
        '<article><a href="/article">Article</a></article>',
        "html.parser",
    )

    item = soup.select_one("article")

    assert item is not None

    with pytest.raises(
        ValueError,
        match="must define 'attribute' as a string",
    ):
        scraper._extract_fields(
            item,
            {
                "link": {
                    "selector": "a",
                    "attribute": 123,
                },
            },
        )


def test_parse_returns_empty_list_when_no_items_match() -> None:
    scraper = make_scraper(
        fields={
            "title": {
                "selector": "h2",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <main>
            <div>No articles here</div>
        </main>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == []


def test_parse_does_not_normalize_relative_urls() -> None:
    scraper = make_scraper(
        fields={
            "link": {
                "selector": "a",
                "attribute": "href",
            },
        },
    )

    soup = BeautifulSoup(
        """
        <article>
            <a href="../article">Article</a>
        </article>
        """,
        "html.parser",
    )

    articles = scraper._parse(soup)

    assert articles == [
        {
            "link": "../article",
        }
    ]