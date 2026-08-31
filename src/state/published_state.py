from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


class PublishedState:
    """Persist and query the global history of published articles."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

        # Validate an existing state file immediately.
        # A missing file is valid and represents an empty state.
        self._load()

    def is_published(self, article_id: str) -> bool:
        """Return True if an article has already been published."""
        state = self._load()

        return article_id in state

    def unpublished(self, article_ids: Iterable[str]) -> list[str]:
        """Return article IDs that have not yet been published."""
        state = self._load()

        return [
            article_id
            for article_id in article_ids
            if article_id not in state
        ]

    def mark_published(self, article_ids: Iterable[str]) -> None:
        """
        Mark multiple articles as published in a single atomic update.

        Existing article IDs are left unchanged, making this operation
        idempotent.
        """
        article_ids = list(article_ids)

        if not article_ids:
            return

        state = self._load()
        published_at = datetime.now(timezone.utc).isoformat()

        changed = False

        for article_id in article_ids:
            if article_id in state:
                continue

            state[article_id] = published_at
            changed = True

        if not changed:
            return

        self._save_atomic(state)

    def _load(self) -> dict[str, str]:
        """
        Load the published state from disk.

        A missing state file represents an empty state.

        Invalid JSON and JSON values other than an object are considered
        invalid state and raise ValueError.
        """
        if not self.path.exists():
            return {}

        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in state file: {self.path}"
            ) from exc

        if not isinstance(data, dict):
            raise ValueError(
                f"State file must contain an object: {self.path}"
            )

        return data

    def _save_atomic(
        self,
        state: dict[str, str],
    ) -> None:
        """Atomically replace the published state file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        fd, temporary_path = tempfile.mkstemp(
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
        )

        temporary_path = Path(temporary_path)

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    state,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            temporary_path.replace(self.path)

        except Exception:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass

            raise