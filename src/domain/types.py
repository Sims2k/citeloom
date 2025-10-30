from dataclasses import dataclass
from typing import Optional, Sequence, Tuple


@dataclass(frozen=True)
class ProjectId:
    value: str


@dataclass(frozen=True)
class CiteKey:
    value: str


@dataclass(frozen=True)
class PageSpan:
    value: Optional[Tuple[int, int]]


@dataclass(frozen=True)
class SectionPath:
    parts: Sequence[str]
