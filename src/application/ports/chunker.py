from typing import Protocol, runtime_checkable, Sequence, Mapping, Any


@runtime_checkable
class ChunkerPort(Protocol):
    def chunk(self, conversion: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
        """Produce chunks from a conversion result."""
        ...
