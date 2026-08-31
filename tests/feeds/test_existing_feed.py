from datetime import datetime, timezone
from pathlib import Path

from src.feeds.existing_feed import ExistingFeedReader


def test_read_returns_empty_list_for_missing_feed(
    tmp_path: Path,
) -> None:
    reader = ExistingFeedReader()

    result = reader.read(
        tmp_path / "missing.xml"
    )

    assert result == []


def test_read_extracts_existing_rss_items(
    tmp_path: Path,
) -> None:
    path = tmp_path / "feed.xml"

    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Health</title>
    <description>Health feed</description>
    <link>https://example.com</link>
    <item>
      <title>Example article</title>
      <link>https://example.com/article</link>
      <guid isPermaLink="false">article-123</guid>
      <pubDate>Mon, 31 Aug 2026 12:30:00 GMT</pubDate>
      <description>Description</description>
      <author>Jane Doe</author>
      <category>Health</category>
      <category>Research</category>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    reader = ExistingFeedReader()

    items = reader.read(path)

    assert len(items) == 1

    item = items[0]

    assert item.guid == "article-123"
    assert item.id == "article-123"
    assert item.title == "Example article"
    assert item.link == "https://example.com/article"
    assert item.description == "Description"
    assert item.author == "Jane Doe"
    assert item.category == [
        "Health",
        "Research",
    ]
    assert item.published == datetime(
        2026,
        8,
        31,
        12,
        30,
        tzinfo=timezone.utc,
    )


def test_read_normalizes_non_utc_pubdate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "feed.xml"

    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Health</title>
    <description>Health feed</description>
    <link>https://example.com</link>
    <item>
      <title>Example article</title>
      <link>https://example.com/article</link>
      <guid isPermaLink="false">article-123</guid>
      <pubDate>Mon, 31 Aug 2026 15:30:00 +0100</pubDate>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    items = ExistingFeedReader().read(path)

    assert items[0].published == datetime(
        2026,
        8,
        31,
        14,
        30,
        tzinfo=timezone.utc,
    )


def test_read_allows_missing_pubdate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "feed.xml"

    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Health</title>
    <description>Health feed</description>
    <link>https://example.com</link>
    <item>
      <title>Example article</title>
      <link>https://example.com/article</link>
      <guid isPermaLink="false">article-123</guid>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    items = ExistingFeedReader().read(path)

    assert len(items) == 1
    assert items[0].published is None


def test_read_skips_item_without_guid(
    tmp_path: Path,
) -> None:
    path = tmp_path / "feed.xml"

    path.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <item>
      <title>No GUID</title>
      <link>https://example.com/article</link>
    </item>
  </channel>
</rss>
""",
        encoding="utf-8",
    )

    items = ExistingFeedReader().read(path)

    assert items == []