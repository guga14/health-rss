#O que é uma fonte. Representa uma origem de informação, enquanto a configuração concreta dessa origem fica em config/sources/*.yml. O Source apenas diz: "Aqui estão as instruções que o mecanismo de recolha deve utilizar."
from dataclasses import dataclass
from typing import Any, ClassVar, Literal


SourceType = Literal["api", "html"]


@dataclass
class Source:
    """Configuration describing an external article source."""

    id: str
    name: str
    url: str
    type: SourceType
    parser: dict[str, Any]

    ALLOWED_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "title",
            "link",
            "description",
            "published",
            "author",
            "category",
        }
    )

    def __post_init__(self) -> None:
        self._validate_parser()

    def _validate_parser(self) -> None:
        """Validate the parser configuration shared by all source types."""
        fields = self.parser.get("fields")

        if not isinstance(fields, dict) or not fields:
            raise ValueError(
                f"Source '{self.name}' must define "
                "'parser.fields' as a non-empty mapping."
            )

        unsupported_fields = set(fields) - self.ALLOWED_FIELDS

        if unsupported_fields:
            names = ", ".join(sorted(unsupported_fields))
            raise ValueError(
                f"Source '{self.name}' contains unsupported fields: "
                f"{names}."
            )

        for field_name, field_config in fields.items():
            if not isinstance(field_config, dict):
                raise ValueError(
                    f"Source '{self.name}' field '{field_name}' "
                    "must be a mapping."
                )