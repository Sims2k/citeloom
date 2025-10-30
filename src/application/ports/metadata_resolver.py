from typing import Protocol, runtime_checkable, Mapping, Any


@runtime_checkable
class MetadataResolverPort(Protocol):
    def resolve(self, citekey: str | None, references_path: str) -> Mapping[str, Any] | None:
        """Resolve citation metadata from a CSL-JSON file."""
        ...
