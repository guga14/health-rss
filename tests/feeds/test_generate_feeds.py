from datetime import datetime, timezone
from xml.etree.ElementTree import fromstring

from src.feeds.generate_feeds import FeedGenerator
from src.models.article import Article
from src.models.feed import Feed


def make_feed() -> Feed:
    return Feed(
        id="health",
        title="Health",
        description="Health feed",
        link="https://example.com/health",
    )


def test_generate_writes_article_guid() -> None:
    article = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    xml = FeedGenerator().generate(
        make_feed(),
        [article],
    )

    root = fromstring(xml)

    guid = root.find("./channel/item/guid")

    assert guid is not None
    assert guid.text == article.id
    assert guid.attrib["isPermaLink"] == "false"


def test_generate_omits_pubdate_when_article_has_no_date() -> None:
    article = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
    )

    xml = FeedGenerator().generate(
        make_feed(),
        [article],
    )

    root = fromstring(xml)

    pub_date = root.find(
        "./channel/item/pubDate"
    )

    assert pub_date is None


def test_generate_formats_date_as_utc() -> None:
    article = Article(
        title="Example article",
        link="https://example.com/article",
        source="Example Source",
        published=datetime(
            2026,
            8,
            31,
            15,
            30,
            tzinfo=timezone.utc,
        ),
    )

    xml = FeedGenerator().generate(
        make_feed(),
        [article],
    )

    root = fromstring(xml)

    pub_date = root.find(
        "./channel/item/pubDate"
    )

    assert pub_date is not None
    assert pub_date.text == (
        "Mon, 31 Aug 2026 15:30:00 GMT"
    )