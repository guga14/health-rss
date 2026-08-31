from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable


class PublishedState:
    """Persist and query the global history of published articles."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

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

            state[article_id] = {
                "published_at": published_at,
            }
            changed = True

        if not changed:
            return

        self._save_atomic(state)

    def _load(self) -> dict[str, dict[str, str]]:
        """Load the published state from disk."""
        if not self.path.exists():
            return {}

        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            raise ValueError("Published state must be a JSON object.")

        articles = data.get("articles", {})

        if not isinstance(articles, dict):
            raise ValueError(
                "Published state 'articles' must be a JSON object."
            )

        return articles

    def _save_atomic(
        self,
        articles: dict[str, dict[str, str]],
    ) -> None:
        """Atomically replace the published state file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "articles": articles,
        }

        fd, temporary_path = NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.path.parent,
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            delete=False,
        )

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(
                    data,
                    file,
                    ensure_ascii=False,
                    indent=2,
                )
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary_path, self.path)

        except Exception:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass

            raise