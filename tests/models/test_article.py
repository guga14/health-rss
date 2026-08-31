from datetime import datetime, timezone
from hashlib import sha256

from src.models.article import Article


def test_id_is_sha256_of_source_link_and_title() -> None:
    article = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    expected_identity = (
        "Example Source|https://example.com/article|Example article"
    )
    expected_id = sha256(
        expected_identity.encode("utf-8")
    ).hexdigest()

    assert article.id == expected_id


def test_id_is_stable_for_same_source_link_and_title() -> None:
    article_1 = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    article_2 = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    assert article_1.id == article_2.id


def test_id_changes_when_title_changes() -> None:
    article_1 = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    article_2 = Article(
        title="Another article",
        link="https://example.com/article",
        source="Example Source",
    )

    assert article_1.id != article_2.id


def test_id_changes_when_link_changes() -> None:
    article_1 = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    article_2 = Article(
        title="Example article",
        link="https://example.com/another-article",
        source="Example Source",
    )

    assert article_1.id != article_2.id


def test_id_changes_when_source_changes() -> None:
    article_1 = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    article_2 = Article(
        title="Example article",
        link="https://example.com/article",
        source="Another Source",
    )

    assert article_1.id != article_2.id


def test_optional_fields_have_expected_defaults() -> None:
    article = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    assert article.published is None
    assert article.description is None
    assert article.author is None
    assert article.category == []


def test_published_accepts_datetime() -> None:
    published = datetime(
        2026,
        8,
        31,
        12,
        30,
        tzinfo=timezone.utc,
    )

    article = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
        published=published,
    )

    assert article.published == published


def test_category_is_not_shared_between_articles() -> None:
    article_1 = Article(
        title="Article 1",
        link="https://example.com/1",
        source="Example Source",
    )

    article_2 = Article(
        title="Article 2",
        link="https://example.com/2",
        source="Example Source",
    )

    article_1.category.append("technology")

    assert article_1.category == ["technology"]
    assert article_2.category == []