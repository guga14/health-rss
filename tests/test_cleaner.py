from datetime import datetime, timezone

from src.models.source import Source
from src.processing.cleaner import ArticleCleaner


def make_cleaner(
    fields: dict | None = None,
) -> ArticleCleaner:
    if fields is None:
        fields = {
            "title": {
                "path": "title",
            },
            "link": {
                "path": "link",
            },
            "published": {
                "path": "published",
            },
            "description": {
                "path": "description",
            },
            "author": {
                "path": "author",
            },
            "category": {
                "path": "category",
            },
        }

    source = Source(
        id="source-1",
        name="Example Source",
        url="https://example.com",
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
            "published": "2026-08-31T10:00:00+00:00",
            "description": "Example description",
            "author": "John Doe",
            "category": "Health",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    assert article.title == "Example article"
    assert article.link == "https://example.com/article"
    assert article.published == datetime(
        2026,
        8,
        31,
        10,
        0,
        tzinfo=timezone.utc,
    )
    assert article.source == "Example Source"
    assert article.description == "Example description"
    assert article.author == "John Doe"
    assert article.category == ["Health"]


def test_clean_normalizes_text_fields() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "  Example article  ",
            "link": "  https://example.com/article  ",
            "description": "  Example description  ",
            "author": "  John Doe  ",
            "category": "  Health  ",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    assert article.title == "Example article"
    assert article.link == "https://example.com/article"
    assert article.description == "Example description"
    assert article.author == "John Doe"
    assert article.category == ["Health"]


def test_clean_normalizes_relative_link() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "/article",
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
            "published": "2026-08-31T10:30:00+01:00",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
        9,
        30,
        tzinfo=timezone.utc,
    )


def test_clean_parses_utc_z_datetime() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": "2026-08-31T10:30:00Z",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
        10,
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
        tzinfo=timezone.utc,
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
        tzinfo=timezone.utc,
    )


def test_clean_normalizes_string_category() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "category": "Health",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].category == ["Health"]


def test_clean_normalizes_category_list() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "category": [
                "Health",
                "Science",
                "Health",
                "  Medicine  ",
            ],
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].category == [
        "Health",
        "Science",
        "Medicine",
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
    assert article.author is None
    assert article.category == []
    assert article.published is None


def test_clean_skips_article_without_title() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "link": "https://example.com/article",
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
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_skips_article_without_link() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
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
            "category": 123,
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert articles == []


def test_clean_continues_after_invalid_article() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Invalid article",
            "link": "https://example.com/invalid",
            "published": "not-a-date",
        },
        {
            "title": "Valid article",
            "link": "https://example.com/valid",
        },
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].title == "Valid article"


def test_clean_calculates_id_from_normalized_values() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "  Example article  ",
            "link": "/article",
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1

    article = articles[0]

    assert article.title == "Example article"
    assert article.link == "https://example.com/article"
    assert article.id == (
        "c19b90f3f17009d7d2025932bfea72ac3a3ca5186e0e11abd10d540e99df7fef"
    )


def test_clean_normalizes_naive_datetime_to_utc() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": datetime(
                2026,
                8,
                31,
                10,
                30,
            ),
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
        10,
        30,
        tzinfo=timezone.utc,
    )


def test_clean_normalizes_aware_datetime_to_utc() -> None:
    cleaner = make_cleaner()

    raw_articles = [
        {
            "title": "Example article",
            "link": "https://example.com/article",
            "published": datetime(
                2026,
                8,
                31,
                11,
                30,
                tzinfo=timezone.utc,
            ),
        }
    ]

    articles = cleaner.clean(raw_articles)

    assert len(articles) == 1
    assert articles[0].published == datetime(
        2026,
        8,
        31,
        11,
        30,
        tzinfo=timezone.utc,
    )
    assert articles[0].published.tzinfo == timezone.utc