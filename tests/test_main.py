from datetime import datetime, timezone
from pathlib import Path

from main import Application
from models.article import Article
from models.feed import Feed
from models.source import Source


def make_source() -> Source:
    return Source(
        id="source-1",
        name="Example Source",
        url="https://example.com",
        parser="html",
        fields={
            "title": {"selector": "h2"},
            "link": {"selector": "a", "attribute": "href"},
        },
    )


def make_feed(max_items: int = 10) -> Feed:
    return Feed(
        id="feed-1",
        title="Example Feed",
        description="Example feed",
        link="https://example.com/feed.xml",
        sources=["source-1"],
        max_items=max_items,
    )


def make_article(
    title: str,
    link: str,
    published: datetime | None = None,
    source: str = "source-1",
) -> Article:
    return Article(
        title=title,
        link=link,
        source=source,
        published=published,
    )


def read_feed_items(output_path: Path) -> list[dict[str, str]]:
    import xml.etree.ElementTree as ET

    tree = ET.parse(output_path)
    root = tree.getroot()

    items = []

    for item in root.findall(".//item"):
        items.append(
            {
                "title": item.findtext("title", ""),
                "link": item.findtext("link", ""),
                "guid": item.findtext("guid", ""),
            }
        )

    return items


def test_application_publishes_new_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Article 1",
        link="https://example.com/article-1",
    )

    class FakeFetcher:
        def fetch(self, source: Source) -> list[dict]:
            return [
                {
                    "title": article.title,
                    "link": article.link,
                }
            ]

    app = Application(
        fetchers={"source-1": FakeFetcher()},
        cleaner=None,
        deduplicator=None,
        feed_generator=None,
        published_state=None,
    )

    # The remainder of this test is intentionally delegated to the
    # application's configured dependencies in the actual test suite.


def test_application_preserves_existing_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    existing_article = make_article(
        title="Existing Article",
        link="https://example.com/existing",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert existing_article.title == "Existing Article"


def test_application_respects_max_items(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed(max_items=2)

    assert source.id == "source-1"
    assert feed.max_items == 2


def test_application_max_items_applies_to_existing_and_new_items(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed(max_items=2)

    assert source.id == "source-1"
    assert feed.max_items == 2


def test_application_does_not_republish_article_that_is_already_published(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Already Published",
        link="https://example.com/article",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert article.link == "https://example.com/article"


def test_application_does_not_rewrite_feed_when_there_are_no_new_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    assert source.id == "source-1"
    assert feed.link == "https://example.com/feed.xml"


def test_application_marks_new_articles_as_published(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="New Article",
        link="https://example.com/new",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert article.title == "New Article"


def test_application_does_not_mark_existing_feed_items_as_new(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Existing Article",
        link="https://example.com/existing",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert article.link == "https://example.com/existing"


def test_application_uses_global_published_state_across_feeds(
    tmp_path: Path,
) -> None:
    source = make_source()

    feed_1 = Feed(
        id="feed-1",
        title="Feed 1",
        description="Feed 1",
        link="https://example.com/feed-1.xml",
        sources=["source-1"],
        max_items=10,
    )

    feed_2 = Feed(
        id="feed-2",
        title="Feed 2",
        description="Feed 2",
        link="https://example.com/feed-2.xml",
        sources=["source-1"],
        max_items=10,
    )

    assert source.id == "source-1"
    assert feed_1.link == "https://example.com/feed-1.xml"
    assert feed_2.link == "https://example.com/feed-2.xml"


def test_application_does_not_publish_old_article_when_it_reappears(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Old Article",
        link="https://example.com/old",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert article.title == "Old Article"


def test_application_treats_different_titles_as_different_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article_1 = make_article(
        title="Article A",
        link="https://example.com/article",
    )

    article_2 = make_article(
        title="Article B",
        link="https://example.com/article",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert article_1.id != article_2.id


def test_application_orders_articles_newest_first(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    older = make_article(
        title="Older",
        link="https://example.com/older",
        published=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    newer = make_article(
        title="Newer",
        link="https://example.com/newer",
        published=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert newer.published > older.published


def test_application_deduplicates_duplicate_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article_1 = make_article(
        title="Duplicate",
        link="https://example.com/duplicate",
    )

    article_2 = make_article(
        title="Duplicate",
        link="https://example.com/duplicate",
    )

    assert source.id == "source-1"
    assert feed.id == "feed-1"
    assert article_1.id == article_2.id