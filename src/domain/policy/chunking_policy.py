from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingPolicy:
    """Policy for heading-aware chunking with tokenizer alignment."""
    
    max_tokens: int = 450
    overlap_tokens: int = 60
    heading_context: int = 2
    tokenizer_id: str | None = None
