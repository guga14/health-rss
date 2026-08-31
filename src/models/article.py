#O que é um artigo.
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256


@dataclass
class Article:
    """Normalized article representation."""

    title: str
    link: str
    source: str

    published: datetime | None = None
    description: str | None = None
    author: str | None = None
    category: list[str] = field(default_factory=list)

    id: str = field(init=False)

    def __post_init__(self) -> None:
        identity = f"{self.source}|{self.link}|{self.title}"
        self.id = sha256(
            identity.encode("utf-8")
        ).hexdigest()