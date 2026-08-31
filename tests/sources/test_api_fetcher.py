from typing import Any

import pytest

from src.models.source import Source
from src.sources.api_fetcher import ApiFetcher


def make_fetcher(
    *,
    items_path: str,
    fields: dict[str, Any],
) -> ApiFetcher:
    source = Source(
        id="example",
        name="Example API",
        url="https://example.com/api",
        type="api",
        parser={
            "items_path": items_path,
            "fields": fields,
        },
    )

    return ApiFetcher(source)


def test_parse_json_extracts_fields_from_nested_items() -> None:
    fetcher = make_fetcher(
        items_path="data.results",
        fields={
            "title": {
                "path": "title",
            },
            "link": {
                "path": "url",
            },
        },
    )

    data = b"""
    {
        "data": {
            "results": [
                {
                    "title": "Article 1",
                    "url": "https://example.com/1"
                },
                {
                    "title": "Article 2",
                    "url": "https://example.com/2"
                }
            ]
        }
    }
    """

    articles = fetcher._parse_json(data)

    assert articles == [
        {
            "title": "Article 1",
            "link": "https://example.com/1",
        },
        {
            "title": "Article 2",
            "link": "https://example.com/2",
        },
    ]


def test_parse_json_accepts_array_at_root() -> None:
    fetcher = make_fetcher(
        items_path="",
        fields={
            "title": {
                "path": "title",
            },
            "link": {
                "path": "url",
            },
        },
    )

    data = b"""
    [
        {
            "title": "Article 1",
            "url": "https://example.com/1"
        },
        {
            "title": "Article 2",
            "url": "https://example.com/2"
        }
    ]
    """

    articles = fetcher._parse_json(data)

    assert articles == [
        {
            "title": "Article 1",
            "link": "https://example.com/1",
        },
        {
            "title": "Article 2",
            "link": "https://example.com/2",
        },
    ]


def test_parse_json_supports_nested_field_paths() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "content.title",
            },
            "link": {
                "path": "content.links.canonical",
            },
        },
    )

    data = b"""
    {
        "articles": [
            {
                "content": {
                    "title": "Nested title",
                    "links": {
                        "canonical": "https://example.com/article"
                    }
                }
            }
        ]
    }
    """

    articles = fetcher._parse_json(data)

    assert articles == [
        {
            "title": "Nested title",
            "link": "https://example.com/article",
        }
    ]


def test_parse_json_supports_list_indexes_in_paths() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "author": {
                "path": "authors.0.name",
            },
            "title": {
                "path": "title",
            },
        },
    )

    data = b"""
    {
        "articles": [
            {
                "title": "Article",
                "authors": [
                    {
                        "name": "Jane Doe"
                    }
                ]
            }
        ]
    }
    """

    articles = fetcher._parse_json(data)

    assert articles == [
        {
            "author": "Jane Doe",
            "title": "Article",
        }
    ]


def test_parse_json_returns_none_for_missing_field_path() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "missing.title",
            },
        },
    )

    data = b"""
    {
        "articles": [
            {
                "title": "Article"
            }
        ]
    }
    """

    articles = fetcher._parse_json(data)

    assert articles == [
        {
            "title": None,
        }
    ]


def test_parse_json_skips_non_object_items() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "title",
            },
        },
    )

    data = b"""
    {
        "articles": [
            {
                "title": "Valid article"
            },
            "invalid item",
            123,
            null
        ]
    }
    """

    articles = fetcher._parse_json(data)

    assert articles == [
        {
            "title": "Valid article",
        }
    ]


def test_parse_json_requires_items_path() -> None:
    source = Source(
        id="example",
        name="Example API",
        url="https://example.com/api",
        type="api",
        parser={
            "fields": {
                "title": {
                    "path": "title",
                },
            },
        },
    )

    fetcher = ApiFetcher(source)

    with pytest.raises(
        ValueError,
        match="parser.items_path",
    ):
        fetcher._parse_json(b'[]')


def test_parse_json_requires_items_path_to_be_string() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "title",
            },
        },
    )

    fetcher.source.parser["items_path"] = None

    with pytest.raises(
        ValueError,
        match="parser.items_path",
    ):
        fetcher._parse_json(b'[]')


def test_parse_json_requires_fields() -> None:
    source = Source(
        id="example",
        name="Example API",
        url="https://example.com/api",
        type="api",
        parser={
            "items_path": "articles",
            "fields": {
                "title": {
                    "path": "title",
                },
            },
        },
    )

    fetcher = ApiFetcher(source)

    fetcher.source.parser["fields"] = {}

    with pytest.raises(
        ValueError,
        match="parser.fields",
    ):
        fetcher._parse_json(
            b'{"articles": []}'
        )


def test_parse_json_requires_items_path_to_resolve_to_list() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "title",
            },
        },
    )

    data = b"""
    {
        "articles": {
            "title": "Not a list"
        }
    }
    """

    with pytest.raises(
        ValueError,
        match="Expected a list",
    ):
        fetcher._parse_json(data)


def test_extract_fields_requires_field_configuration_to_be_mapping() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "title",
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="must be an object",
    ):
        fetcher._extract_fields(
            {"title": "Article"},
            {"title": "title"},
        )


def test_extract_fields_requires_path() -> None:
    fetcher = make_fetcher(
        items_path="articles",
        fields={
            "title": {
                "path": "title",
            },
        },
    )

    with pytest.raises(
        ValueError,
        match="must define 'path'",
    ):
        fetcher._extract_fields(
            {"title": "Article"},
            {"title": {}},
        )


def test_get_nested_value_supports_empty_path() -> None:
    value = {
        "title": "Article",
    }

    assert (
        fetcher_value(value, "")
        == value
    )


def test_get_nested_value_returns_none_for_missing_path() -> None:
    value = {
        "article": {
            "title": "Article",
        },
    }

    assert (
        fetcher_value(value, "article.missing")
        is None
    )


def test_get_nested_value_returns_none_for_invalid_list_index() -> None:
    value = {
        "authors": [
            {
                "name": "Jane Doe",
            }
        ],
    }

    assert (
        fetcher_value(value, "authors.5.name")
        is None
    )


def test_get_nested_value_returns_none_for_non_numeric_list_index() -> None:
    value = {
        "authors": [
            {
                "name": "Jane Doe",
            }
        ],
    }

    assert (
        fetcher_value(value, "authors.first.name")
        is None
    )


def fetcher_value(
    data: Any,
    path: str,
) -> Any:
    return ApiFetcher._get_nested_value(
        data,
        path,
    )