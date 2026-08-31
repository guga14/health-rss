from pathlib import Path

from .feeds.generate_feeds import FeedGenerator
from .models.feed import Feed
from .output.file_output import FileOutput
from .processing.cleaner import ArticleCleaner
from .processing.deduplicator import ArticleDeduplicator
from .sources.base import SourceFetcher
from .state.published_state import PublishedState


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

            articles = self.deduplicator.deduplicate(articles)

            article_ids = [article.id for article in articles]
            unpublished_ids = set(
                self.published_state.unpublished(article_ids)
            )

            articles = [
                article
                for article in articles
                if article.id in unpublished_ids
            ]

            if not articles:
                continue

            xml = self.feed_generator.generate(
                feed,
                articles,
            )

            output_path = (
                self.output_directory / f"{feed.id}.xml"
            )

            self.output.write(
                output_path,
                xml,
            )

            self.published_state.mark_published(
                article.id for article in articles
            )

    def _fetch_articles(self) -> dict[str, list]:
        """Fetch and clean articles grouped by source."""
        articles_by_source = {}

        for source_id, fetcher in self.fetchers.items():
            raw_articles = fetcher.fetch()

            cleaner = ArticleCleaner(fetcher.source)

            articles_by_source[source_id] = cleaner.clean(
                raw_articles
            )

        return articles_by_source

    @staticmethod
    def _articles_for_feed(
        feed: Feed,
        articles_by_source: dict[str, list],
    ) -> list:
        """Collect articles belonging to the feed's sources."""
        articles = []

        for source_id in feed.sources:
            articles.extend(
                articles_by_source.get(source_id, [])
            )

        return articles