#Importa o Feed do modelo e é exclusivamente responsável pela transformação: Feed + Article[] → RSS XML.
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import Protocol
from xml.etree.ElementTree import Element, SubElement, tostring

from models.feed import Feed


class FeedItem(Protocol):
    """Fields required to render an item in an RSS feed."""

    id: str
    title: str
    link: str
    published: datetime | None
    description: str | None
    author: str | None
    category: list[str]


class FeedGenerator:
    """Generate RSS feeds from feed items."""

    def generate(
        self,
        feed: Feed,
        articles: list[FeedItem],
    ) -> str:
        """Generate an RSS 2.0 feed as XML."""

        rss = Element(
            "rss",
            {
                "version": "2.0",
            },
        )

        channel = SubElement(
            rss,
            "channel",
        )

        SubElement(
            channel,
            "title",
        ).text = feed.title

        SubElement(
            channel,
            "description",
        ).text = feed.description

        SubElement(
            channel,
            "link",
        ).text = feed.link

        for article in articles:
            self._add_article(
                channel,
                article,
            )

        return tostring(
            rss,
            encoding="unicode",
            xml_declaration=True,
        )

    @staticmethod
    def _add_article(
        channel: Element,
        article: FeedItem,
    ) -> None:
        item = SubElement(
            channel,
            "item",
        )

        SubElement(
            item,
            "title",
        ).text = article.title

        SubElement(
            item,
            "link",
        ).text = article.link

        guid = SubElement(
            item,
            "guid",
            {
                "isPermaLink": "false",
            },
        )

        guid.text = article.id

        if article.published is not None:
            SubElement(
                item,
                "pubDate",
            ).text = FeedGenerator._format_date(
                article.published
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
    def _format_date(
        value: datetime,
    ) -> str:
        """Format a datetime as an RFC 2822 UTC date for RSS."""

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=timezone.utc,
            )
        else:
            value = value.astimezone(
                timezone.utc,
            )

        return format_datetime(
            value,
            usegmt=True,
        )