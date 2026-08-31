from datetime import datetime, timezone

from src.processing.cleaner import ArticleCleaner
from src.models.article import Article
from src.models.source import Source


def make_cleaner(
    *,
    fields: dict | None = None,
    source_url: str = "https://example.com/news",
) -> ArticleCleaner:
    if fields is None:
        fields = {
            "title": {
                "path": "title",
            },
            "link": {
                "path": "link",
            },
            "description": {
                "path": "description",
            },
            "published": {
                "path": "published",
            },
            "author": {
                "path": "author",
            },
            "category": {
                "path": "category",
            },
        }

    source = Source(
        id="example",
        name="Example Source",
        url=source_url,
        type="api",
        parser={
            "items_path": "articles",
            "fields": fields,
        },
    )

    return ArticleCleaner(source)


def test_clean_creates_article() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "description": "Example description",
            "published": "2026-08-31T12:30:00+00:00",
            "author": "Jane Doe",
            "category": ["Technology"],
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    assert isinstance(article, Article)
    assert article.title == "Example article"
    assert article.link == "https://example.com/article"
    assert article.description == "Example description"
    assert article.published == datetime(
        2026,
        8,
        31,
        12,
        30,
        tzinfo=timezone.utc,
    )
    assert article.author == "Jane Doe"
    assert article.category == ["Technology"]


def test_clean_normalizes_text_fields() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "  Example article  ",
            "link": "  https://example.com/article  ",
            "description": "  Description  ",
            "published": None,
            "author": "  Jane Doe  ",
            "category": ["  Technology  "],
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    assert article.title == "Example article"
    assert article.link == "https://example.com/article"
    assert article.description == "Description"
    assert article.author == "Jane Doe"
    assert article.category == ["Technology"]


def test_clean_normalizes_relative_link() -> None:
    cleaner = make_cleaner(
        source_url="https://example.com/news/",
    )

    raw_articles = [
        {
            "title": "Example article",
            "link": "../article",
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].link == "https://example.com/article"


def test_clean_allows_missing_published() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published is None


def test_clean_parses_iso_datetime() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": "2026-08-31T12:30:00+00:00",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
        12,
        30,
        tzinfo=timezone.utc,
    )


def test_clean_parses_utc_z_datetime() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": "2026-08-31T12:30:00Z",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
        12,
        30,
        tzinfo=timezone.utc,
    )


def test_clean_uses_configured_date_format() -> None:
    cleaner = make_cleaner(
        fields={
            "title": {
                "path": "title",
            },
            "link": {
                "path": "link",
            },
            "published": {
                "path": "published",
                "date_format": "%d/%m/%Y",
            },
        }
    )

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": "31/08/2026",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
    )


def test_clean_parses_common_date_formats() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": "31/08/2026",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
    )


def test_clean_normalizes_string_category() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "category": "Technology",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].category == ["Technology"]


def test_clean_normalizes_category_list() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "category": [
                "Technology",
                "Science",
                "Technology",
                " ",
                "Science",
            ],
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].category == [
        "Technology",
        "Science",
    ]


def test_clean_missing_optional_fields_uses_defaults() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    assert article.description is None
    assert article.published is None
    assert article.author is None
    assert article.category == []


def test_clean_skips_article_without_title() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "link": "https://example.com/article",
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_with_empty_title() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "   ",
            "link": "https://example.com/article",
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_without_link() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_with_empty_link() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "   ",
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_with_invalid_published_date() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": "not-a-date",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_with_invalid_optional_text() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "description": 123,
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_with_invalid_category() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "category": {
                "name": "Technology",
            },
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_continues_after_invalid_article() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Invalid article",
            "link": "",
        },
        {
            "title": "Valid article",
            "link": "https://example.com/valid",
            "published": None,
        },
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].title == "Valid article"


def test_clean_calculates_id_from_normalized_values() -> None:
    cleaner = make_cleaner(
        source_url="https://example.com/news/",
    )

    raw_articles = [
        {
            "title": "  Example article  ",
            "link": "../article",
            "published": None,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    expected = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    assert article.id == expected.id