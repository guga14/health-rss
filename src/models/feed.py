#O que é um feed (a definição de um feed que o repositório pretende disponibilizar)
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Feed:
    """Definition of an RSS feed."""

    id: str
    title: str
    description: str
    link: str
    sources: list[str] = field(default_factory=list)
    max_items: int = 50