#Importa o Feed do modelo e é exclusivamente responsável pela transformação: Feed + Article[] → RSS XML.
from datetime import datetime, timezone
from email.utils import format_datetime
from xml.etree.ElementTree import Element, SubElement, tostring

from ..models.article import Article
from ..models.feed import Feed

class FeedGenerator:
"""Generate RSS feeds from normalized articles."""

```
def generate(
    self,
    feed: Feed,
    articles: list[Article],
) -> str:
    """Generate an RSS 2.0 feed as XML."""

    rss = Element(
        "rss",
        {
            "version": "2.0",
        },
    )

    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = feed.title
    SubElement(channel, "description").text = feed.description
    SubElement(channel, "link").text = feed.link

    for article in articles:
        self._add_article(channel, article)

    return tostring(
        rss,
        encoding="unicode",
        xml_declaration=True,
    )

@staticmethod
def _add_article(
    channel: Element,
    article: Article,
) -> None:
    item = SubElement(channel, "item")

    SubElement(item, "title").text = article.title
    SubElement(item, "link").text = article.link

    # The Article ID is the stable identity of the article.
    # Existing RSS entries can therefore use <guid> as their
    # deduplication key without reconstructing an Article.
    guid = SubElement(
        item,
        "guid",
        {
            "isPermaLink": "false",
        },
    )
    guid.text = article.id

    # Articles without a publication date are valid.
    # In that case simply omit <pubDate>.
    if article.published is not None:
        SubElement(item, "pubDate").text = (
            FeedGenerator._format_date(article.published)
        )

    if article.description:
        SubElement(
            item,
            "description",
        ).text = article.description

    if article.author:
        SubElement(
            item,
            "author",
        ).text = article.author

    for category in article.category:
        SubElement(
            item,
            "category",
        ).text = category

@staticmethod
def _format_date(value: datetime) -> str:
    """Format a normalized UTC datetime for RSS."""

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)

    return format_datetime(
        value,
        usegmt=True,
    )