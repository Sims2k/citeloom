from typing import Protocol, runtime_checkable


@runtime_checkable
class TextConverterPort(Protocol):
    def convert(self, source_path: str) -> dict:
        """Convert a document at source_path into structured text and metadata."""
        ...
