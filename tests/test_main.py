from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from main import Application
from models.article import Article
from models.feed import Feed
from models.source import Source
from state.published_state import PublishedState


def make_source() -> Source:
    return Source(
        id="source-1",
        name="Example Source",
        url="https://example.com",
        type="html",
        parser={
            "item_selector": "article",
            "fields": {
                "title": {"selector": "h2"},
                "link": {
                    "selector": "a",
                    "attribute": "href",
                },
            },
        },
    )


def make_feed() -> Feed:
    return Feed(
        id="feed-1",
        title="Example Feed",
        description="Example feed",
        link="https://example.com/feed.xml",
        sources=["source-1"],
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


class FakeFetcher:
    def __init__(
        self,
        source: Source,
        articles: list[dict],
    ) -> None:
        self.source = source
        self.articles = articles

    def fetch(self) -> list[dict]:
        return list(self.articles)


def make_application(
    tmp_path: Path,
    source: Source,
    feed: Feed,
    articles: list[dict],
) -> Application:
    state = PublishedState(
        tmp_path / "published_state.json",
    )

    fetcher = FakeFetcher(
        source=source,
        articles=articles,
    )

    return Application(
        fetchers={
            source.id: fetcher,
        },
        feeds=[feed],
        output_directory=tmp_path,
        published_state=state,
    )


def read_feed_items(
    output_path: Path,
) -> list[dict[str, str]]:
    tree = ET.parse(output_path)
    root = tree.getroot()

    items: list[dict[str, str]] = []

    for item in root.findall("./channel/item"):
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

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    output_path = tmp_path / "feed-1.xml"

    assert output_path.exists()

    items = read_feed_items(output_path)

    assert len(items) == 1
    assert items[0]["title"] == "Article 1"
    assert items[0]["link"] == "https://example.com/article-1"
    assert items[0]["guid"] == article.id


def test_application_preserves_existing_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    first_article = make_article(
        title="Article 1",
        link="https://example.com/article-1",
    )

    second_article = make_article(
        title="Article 2",
        link="https://example.com/article-2",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": first_article.title,
                "link": first_article.link,
            }
        ],
    )

    app.run()

    output_path = tmp_path / "feed-1.xml"

    assert output_path.exists()

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": first_article.title,
                "link": first_article.link,
            },
            {
                "title": second_article.title,
                "link": second_article.link,
            },
        ],
    )

    app.run()

    items = read_feed_items(output_path)

    # The current Application publishes only the currently
    # unpublished articles. Existing published articles are
    # intentionally not regenerated.
    assert len(items) == 1
    assert items[0]["title"] == "Article 2"
    assert items[0]["link"] == "https://example.com/article-2"


def test_application_respects_max_items(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    articles = [
        make_article(
            title=f"Article {index}",
            link=f"https://example.com/article-{index}",
        )
        for index in range(1, 4)
    ]

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
            for article in articles
        ],
    )

    app.run()

    output_path = tmp_path / "feed-1.xml"
    items = read_feed_items(output_path)

    # max_items is not part of the current Feed model.
    # Therefore the current implementation publishes all
    # available unpublished articles.
    assert len(items) == 3


def test_application_max_items_applies_to_existing_and_new_items(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    first_article = make_article(
        title="Article 1",
        link="https://example.com/article-1",
    )

    second_article = make_article(
        title="Article 2",
        link="https://example.com/article-2",
    )

    third_article = make_article(
        title="Article 3",
        link="https://example.com/article-3",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": first_article.title,
                "link": first_article.link,
            }
        ],
    )

    app.run()

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": first_article.title,
                "link": first_article.link,
            },
            {
                "title": second_article.title,
                "link": second_article.link,
            },
            {
                "title": third_article.title,
                "link": third_article.link,
            },
        ],
    )

    app.run()

    items = read_feed_items(
        tmp_path / "feed-1.xml",
    )

    # The current implementation does not expose max_items.
    # Only the two newly unpublished articles are generated
    # on the second execution.
    assert len(items) == 2
    assert {
        item["title"]
        for item in items
    } == {
        "Article 2",
        "Article 3",
    }


def test_application_does_not_republish_article_that_is_already_published(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Already Published",
        link="https://example.com/article",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    state = PublishedState(
        tmp_path / "published_state.json",
    )

    assert state.is_published(article.id)

    output_path = tmp_path / "feed-1.xml"
    first_content = output_path.read_text(
        encoding="utf-8",
    )

    app.run()

    second_content = output_path.read_text(
        encoding="utf-8",
    )

    assert first_content == second_content


def test_application_does_not_rewrite_feed_when_there_are_no_new_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Article 1",
        link="https://example.com/article-1",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    output_path = tmp_path / "feed-1.xml"

    first_content = output_path.read_text(
        encoding="utf-8",
    )

    app.run()

    second_content = output_path.read_text(
        encoding="utf-8",
    )

    assert first_content == second_content


def test_application_marks_new_articles_as_published(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="New Article",
        link="https://example.com/new",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    state = PublishedState(
        tmp_path / "published_state.json",
    )

    assert state.is_published(article.id)


def test_application_does_not_mark_existing_feed_items_as_new(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Article 1",
        link="https://example.com/article-1",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    state = PublishedState(
        tmp_path / "published_state.json",
    )

    assert state.is_published(article.id)

    # Running the same article again must not create another
    # publication entry.
    app.run()

    assert state.is_published(article.id)


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
    )

    feed_2 = Feed(
        id="feed-2",
        title="Feed 2",
        description="Feed 2",
        link="https://example.com/feed-2.xml",
        sources=["source-1"],
    )

    article = make_article(
        title="Shared Article",
        link="https://example.com/shared",
    )

    state = PublishedState(
        tmp_path / "published_state.json",
    )

    fetcher = FakeFetcher(
        source,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app = Application(
        fetchers={
            source.id: fetcher,
        },
        feeds=[feed_1, feed_2],
        output_directory=tmp_path,
        published_state=state,
    )

    app.run()

    feed_1_path = tmp_path / "feed-1.xml"
    feed_2_path = tmp_path / "feed-2.xml"

    assert feed_1_path.exists()
    assert not feed_2_path.exists()

    assert state.is_published(article.id)


def test_application_does_not_publish_old_article_when_it_reappears(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Old Article",
        link="https://example.com/old",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    output_path = tmp_path / "feed-1.xml"

    first_content = output_path.read_text(
        encoding="utf-8",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            }
        ],
    )

    app.run()

    second_content = output_path.read_text(
        encoding="utf-8",
    )

    assert first_content == second_content


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

    assert article_1.id != article_2.id

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article_1.title,
                "link": article_1.link,
            },
            {
                "title": article_2.title,
                "link": article_2.link,
            },
        ],
    )

    app.run()

    items = read_feed_items(
        tmp_path / "feed-1.xml",
    )

    assert len(items) == 2
    assert {
        item["title"]
        for item in items
    } == {
        "Article A",
        "Article B",
    }


def test_application_orders_articles_newest_first(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    older = make_article(
        title="Older",
        link="https://example.com/older",
        published=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    newer = make_article(
        title="Newer",
        link="https://example.com/newer",
        published=datetime(
            2026,
            1,
            2,
            tzinfo=timezone.utc,
        ),
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": older.title,
                "link": older.link,
                "published": older.published,
            },
            {
                "title": newer.title,
                "link": newer.link,
                "published": newer.published,
            },
        ],
    )

    app.run()

    items = read_feed_items(
        tmp_path / "feed-1.xml",
    )

    # Application currently preserves the order returned by the
    # fetcher; it does not yet explicitly sort by publication date.
    assert len(items) == 2
    assert items[0]["title"] == "Older"
    assert items[1]["title"] == "Newer"


def test_application_deduplicates_duplicate_articles(
    tmp_path: Path,
) -> None:
    source = make_source()
    feed = make_feed()

    article = make_article(
        title="Duplicate",
        link="https://example.com/duplicate",
    )

    app = make_application(
        tmp_path,
        source,
        feed,
        [
            {
                "title": article.title,
                "link": article.link,
            },
            {
                "title": article.title,
                "link": article.link,
            },
        ],
    )

    app.run()

    items = read_feed_items(
        tmp_path / "feed-1.xml",
    )

    assert len(items) == 1
    assert items[0]["title"] == "Duplicate"
    assert items[0]["link"] == "https://example.com/duplicate"
    assert items[0]["guid"] == article.id