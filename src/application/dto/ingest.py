from typing import Any

from pydantic import BaseModel


class IngestRequest(BaseModel):
    """Request DTO for document ingestion use case."""
    
    source_path: str
    project_id: str
    zotero_config: dict[str, Any] | None = None  # Optional Zotero configuration (replaces references_path)
    embedding_model: str = "BAAI/bge-small-en-v1.5"


class IngestResult(BaseModel):
    """Result DTO for document ingestion use case."""
    
    chunks_written: int
    documents_processed: int
    duration_seconds: float
    embed_model: str
    warnings: list[str] = []
