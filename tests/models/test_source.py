import pytest

from src.models.source import Source


def make_source(
    *,
    parser: dict,
    source_type: str = "api",
) -> Source:
    return Source(
        id="example",
        name="Example Source",
        url="https://example.com",
        type=source_type,
        parser=parser,
    )


def test_source_accepts_valid_parser() -> None:
    source = make_source(
        parser={
            "items_path": "articles",
            "fields": {
                "title": {
                    "path": "title",
                },
                "link": {
                    "path": "url",
                },
            },
        }
    )

    assert source.id == "example"
    assert source.name == "Example Source"
    assert source.url == "https://example.com"
    assert source.type == "api"
    assert source.parser["items_path"] == "articles"


def test_source_accepts_html_parser() -> None:
    source = make_source(
        source_type="html",
        parser={
            "item_selector": "article",
            "fields": {
                "title": {
                    "selector": "h2",
                },
                "link": {
                    "selector": "a",
                    "attribute": "href",
                },
            },
        },
    )

    assert source.type == "html"


def test_source_requires_fields() -> None:
    with pytest.raises(
        ValueError,
        match="parser.fields",
    ):
        make_source(
            parser={
                "items_path": "articles",
            }
        )


def test_source_requires_fields_to_be_a_mapping() -> None:
    with pytest.raises(
        ValueError,
        match="parser.fields",
    ):
        make_source(
            parser={
                "fields": [],
            }
        )


def test_source_requires_at_least_one_field() -> None:
    with pytest.raises(
        ValueError,
        match="parser.fields",
    ):
        make_source(
            parser={
                "fields": {},
            }
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "id",
        "guid",
        "content",
        "image",
        "random_field",
    ],
)
def test_source_rejects_unsupported_fields(
    field_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="unsupported fields",
    ):
        make_source(
            parser={
                "fields": {
                    field_name: {
                        "path": "value",
                    },
                },
            }
        )


@pytest.mark.parametrize(
    "field_name",
    [
        "title",
        "link",
        "description",
        "published",
        "author",
        "category",
    ],
)
def test_source_accepts_all_allowed_fields(
    field_name: str,
) -> None:
    source = make_source(
        parser={
            "fields": {
                field_name: {
                    "path": "value",
                },
            },
        }
    )

    assert field_name in source.parser["fields"]


def test_source_requires_each_field_configuration_to_be_a_mapping() -> None:
    with pytest.raises(
        ValueError,
        match="must be a mapping",
    ):
        make_source(
            parser={
                "fields": {
                    "title": "title",
                },
            }
        )


def test_source_allows_parser_specific_options() -> None:
    source = make_source(
        parser={
            "items_path": "data.items",
            "fields": {
                "title": {
                    "path": "title",
                },
            },
            "future_option": {
                "some_value": True,
            },
        }
    )

    assert source.parser["future_option"] == {
        "some_value": True,
    }


def test_source_allows_field_specific_options() -> None:
    source = make_source(
        parser={
            "fields": {
                "published": {
                    "path": "published_at",
                    "date_format": "%Y-%m-%d",
                },
            },
        }
    )

    assert (
        source.parser["fields"]["published"]["date_format"]
        == "%Y-%m-%d"
    )