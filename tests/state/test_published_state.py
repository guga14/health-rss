import json
from pathlib import Path

import pytest

from src.state.published_state import PublishedState


def make_state(tmp_path: Path) -> PublishedState:
    state_path = tmp_path / "published.json"
    return PublishedState(state_path)


def test_empty_state_when_file_does_not_exist(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    assert state.is_published("article-1") is False


def test_mark_published_stores_article_id(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    assert state.is_published("article-1") is True


def test_unpublished_article_is_not_seen(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    assert state.is_published("article-2") is False


def test_mark_published_accepts_multiple_ids(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(
        [
            "article-1",
            "article-2",
            "article-3",
        ]
    )

    assert state.is_published("article-1") is True
    assert state.is_published("article-2") is True
    assert state.is_published("article-3") is True


def test_mark_published_writes_single_state_file(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(
        [
            "article-1",
            "article-2",
            "article-3",
        ]
    )

    assert state.path.exists()

    with state.path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    assert set(data) == {
        "article-1",
        "article-2",
        "article-3",
    }


def test_state_contains_timestamp_for_each_article(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    with state.path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    assert "article-1" in data
    assert isinstance(data["article-1"], str)
    assert data["article-1"]


def test_state_is_persisted_between_instances(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    new_state = make_state(tmp_path)

    assert new_state.is_published("article-1") is True


def test_existing_published_ids_are_preserved(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(
        [
            "article-1",
            "article-2",
        ]
    )

    state.mark_published(["article-3"])

    assert state.is_published("article-1") is True
    assert state.is_published("article-2") is True
    assert state.is_published("article-3") is True


def test_mark_published_is_idempotent(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])
    state.mark_published(["article-1"])

    assert state.is_published("article-1") is True


def test_duplicate_ids_in_single_call_are_accepted(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(
        [
            "article-1",
            "article-1",
            "article-2",
        ]
    )

    assert state.is_published("article-1") is True
    assert state.is_published("article-2") is True


def test_empty_collection_does_not_create_state_file(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published([])

    assert state.path.exists() is False


def test_empty_collection_does_not_change_existing_state(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    before = state.path.read_text(encoding="utf-8")

    state.mark_published([])

    after = state.path.read_text(encoding="utf-8")

    assert after == before


def test_state_file_is_valid_json(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(
        [
            "article-1",
            "article-2",
        ]
    )

    data = json.loads(
        state.path.read_text(encoding="utf-8")
    )

    assert isinstance(data, dict)


def test_state_does_not_contain_unpublished_ids(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    data = json.loads(
        state.path.read_text(encoding="utf-8")
    )

    assert "article-1" in data
    assert "article-2" not in data


def test_existing_state_is_loaded(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "published.json"

    state_path.write_text(
        json.dumps(
            {
                "article-1": "2026-08-31T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    state = PublishedState(state_path)

    assert state.is_published("article-1") is True
    assert state.is_published("article-2") is False


def test_corrupt_state_file_raises_error(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "published.json"

    state_path.write_text(
        "{ invalid json",
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        PublishedState(state_path)


def test_state_file_must_contain_object(
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "published.json"

    state_path.write_text(
        json.dumps(["article-1"]),
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        PublishedState(state_path)


def test_atomic_write_does_not_leave_temp_file(
    tmp_path: Path,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(
        [
            "article-1",
            "article-2",
        ]
    )

    temporary_files = list(
        tmp_path.glob("published.json.*")
    )

    assert temporary_files == []


def test_failed_atomic_write_preserves_previous_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state(tmp_path)

    state.mark_published(["article-1"])

    original_content = state.path.read_text(
        encoding="utf-8"
    )

    def failing_replace(
        source: str | Path,
        destination: str | Path,
    ) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        Path,
        "replace",
        failing_replace,
    )

    with pytest.raises(OSError):
        state.mark_published(["article-2"])

    assert state.path.read_text(
        encoding="utf-8"
    ) == original_content

    assert state.is_published("article-1") is True
    assert state.is_published("article-2") is False


def test_failed_atomic_write_does_not_create_partial_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = make_state(tmp_path)

    def failing_replace(
        source: str | Path,
        destination: str | Path,
    ) -> None:
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        Path,
        "replace",
        failing_replace,
    )

    with pytest.raises(OSError):
        state.mark_published(
            [
                "article-1",
                "article-2",
            ]
        )

    assert state.path.exists() is False

    temporary_files = list(
        tmp_path.glob("published.json.*")
    )

    assert len(temporary_files) <= 1