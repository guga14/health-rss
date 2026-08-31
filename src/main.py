from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from feeds.existing_feed import ExistingFeedItem, ExistingFeedReader
from feeds.generate_feeds import FeedGenerator
from models.article import Article
from models.feed import Feed
from output.file_output import FileOutput
from processing.cleaner import ArticleCleaner
from processing.deduplicator import ArticleDeduplicator
from sources.base import SourceFetcher
from state.published_state import PublishedState


class Application:
    """Orchestrate the health-rss processing pipeline."""

    def __init__(
        self,
        fetchers: dict[str, SourceFetcher],
        feeds: list[Feed],
        output_directory: str | Path,
        published_state: PublishedState,
    ) -> None:
        self.fetchers = fetchers
        self.feeds = feeds
        self.output_directory = Path(output_directory)
        self.published_state = published_state

        self.deduplicator = ArticleDeduplicator()
        self.existing_feed_reader = ExistingFeedReader()
        self.feed_generator = FeedGenerator()
        self.output = FileOutput()

    def run(self) -> None:
        """Execute the complete RSS generation pipeline."""

        articles_by_source = self._fetch_articles()

        for feed in self.feeds:
            articles = self._articles_for_feed(
                feed,
                articles_by_source,
            )

            if not articles:
                continue

            articles = self.deduplicator.deduplicate(
                articles
            )

            article_ids = [
                article.id
                for article in articles
            ]

            unpublished_ids = set(
                self.published_state.unpublished(
                    article_ids
                )
            )

            new_articles = [
                article
                for article in articles
                if article.id in unpublished_ids
            ]

            # If this feed has no new articles, leave the existing
            # RSS untouched. This avoids unnecessary parsing,
            # generation and disk writes.
            if not new_articles:
                continue

            output_path = (
                self.output_directory
                / f"{feed.id}.xml"
            )

            existing_items = self.existing_feed_reader.read(
                output_path
            )

            items = self._merge_feed_items(
                existing_items,
                new_articles,
            )

            items = self._sort_feed_items(
                items
            )

            items = items[:feed.max_items]

            xml = self.feed_generator.generate(
                feed,
                items,
            )

            self.output.write(
                output_path,
                xml,
            )

            # Only mark the newly published articles.
            # Existing RSS items were already published previously.
            self.published_state.mark_published(
                article.id
                for article in new_articles
            )

    def _fetch_articles(
        self,
    ) -> dict[str, list[Article]]:
        """Fetch and clean articles grouped by source."""

        articles_by_source: dict[
            str,
            list[Article],
        ] = {}

        for source_id, fetcher in self.fetchers.items():
            raw_articles = fetcher.fetch()

            cleaner = ArticleCleaner(
                fetcher.source
            )

            articles_by_source[source_id] = cleaner.clean(
                raw_articles
            )

        return articles_by_source

    @staticmethod
    def _articles_for_feed(
        feed: Feed,
        articles_by_source: dict[str, list[Article]],
    ) -> list[Article]:
        """Collect articles belonging to the feed's sources."""

        articles: list[Article] = []

        for source_id in feed.sources:
            articles.extend(
                articles_by_source.get(
                    source_id,
                    [],
                )
            )

        return articles

    @staticmethod
    def _merge_feed_items(
        existing_items: list[ExistingFeedItem],
        new_articles: list[Article],
    ) -> list[ExistingFeedItem | Article]:
        """
        Merge existing RSS items with newly discovered articles.

        New articles take precedence if the same GUID is already present
        in the existing RSS. This keeps the current Article representation
        intact while ensuring that the latest article data is published.
        """

        merged: dict[
            str,
            ExistingFeedItem | Article,
        ] = {}

        for item in existing_items:
            merged[item.id] = item

        for article in new_articles:
            merged[article.id] = article

        return list(merged.values())

    @staticmethod
    def _sort_feed_items(
        items: Iterable[ExistingFeedItem | Article],
    ) -> list[ExistingFeedItem | Article]:
        """Sort feed items from newest to oldest."""

        minimum = datetime.min.replace(
            tzinfo=timezone.utc,
        )

        return sorted(
            items,
            key=lambda item: (
                item.published
                if item.published is not None
                else minimum
            ),
            reverse=True,
        )