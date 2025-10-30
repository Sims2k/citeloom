from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingPolicy:
    max_tokens: int = 450
    overlap: int = 60
    heading_context: int = 2
    tokenizer: str | None = None
