from pydantic import BaseModel


class IngestRequest(BaseModel):
    """Request DTO for document ingestion use case."""
    
    source_path: str
    project_id: str
    references_path: str
    embedding_model: str


class IngestResult(BaseModel):
    """Result DTO for document ingestion use case."""
    
    chunks_written: int
    documents_processed: int
    duration_seconds: float
    embed_model: str
    warnings: list[str] = []
