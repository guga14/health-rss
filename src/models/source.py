#Representa uma origem de informação, enquanto a configuração concreta dessa origem fica em config/sources/*.yml. O Source apenas diz: "Aqui estão as instruções que o mecanismo de recolha deve utilizar."
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Source:
    name: str
    url: str
    type: str

    headers: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    parser: dict[str, Any] = field(default_factory=dict)