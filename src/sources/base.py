from abc import ABC, abstractmethod
from typing import Any

from models.source import Source


class SourceFetcher(ABC):
    """Base class for all source fetchers."""

    def __init__(self, source: Source) -> None:
        self.source = source

    @abstractmethod
    def fetch(self) -> list[dict[str, Any]]:
        """Fetch and return extracted article data."""
        raise NotImplementedError