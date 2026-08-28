from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256


@dataclass
class Article:
    title: str
    link: str
    published: datetime
    source: str

    description: str | None = None
    updated: datetime | None = None
    author: str | None = None
    category: list[str] = field(default_factory=list)

    id: str = field(init=False)

    def __post_init__(self) -> None:
        identity = f"{self.source}|{self.link}|{self.title}"
        self.id = sha256(identity.encode("utf-8")).hexdigest()