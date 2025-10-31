from dataclasses import dataclass


@dataclass(frozen=True)
class ChunkingPolicy:
    """Policy for heading-aware chunking with tokenizer alignment."""
    
    max_tokens: int = 450
    overlap_tokens: int = 60
    heading_context: int = 2
    tokenizer_id: str | None = None
    min_chunk_length: int = 50
    min_signal_to_noise: float = 0.3
    
    def __post_init__(self) -> None:
        """Validate chunking policy."""
        if self.max_tokens < self.min_chunk_length:
            raise ValueError(
                f"max_tokens ({self.max_tokens}) must be >= min_chunk_length ({self.min_chunk_length})"
            )
        if self.overlap_tokens >= self.max_tokens:
            raise ValueError(
                f"overlap_tokens ({self.overlap_tokens}) must be < max_tokens ({self.max_tokens})"
            )
        if not (0.0 <= self.min_signal_to_noise <= 1.0):
            raise ValueError(
                f"min_signal_to_noise must be between 0.0 and 1.0, got {self.min_signal_to_noise}"
            )
