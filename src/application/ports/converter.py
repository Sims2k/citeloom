from typing import Protocol, runtime_checkable, Mapping, Any


@runtime_checkable
class TextConverterPort(Protocol):
    def convert(self, source_path: str) -> Mapping[str, Any]:
        """Convert a document at source_path into structured text and metadata."""
        ...
