from pydantic import BaseModel


class IngestRequest(BaseModel):
    project_id: str
    source_path: str
    references_path: str
    embedding_model: str


class IngestResult(BaseModel):
    chunks_written: int
    audit_path: str | None = None
