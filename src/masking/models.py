from dataclasses import dataclass, field


@dataclass
class Entity:
    original: str
    label: str
    token: str
    start: int
    end: int
    source: str


@dataclass
class MaskingResult:
    masked_text: str
    mapping: dict[str, str] = field(default_factory=dict)
    entities: list[Entity] = field(default_factory=list)
