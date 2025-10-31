from typing import Any

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Request DTO for chunk query use case."""
    
    project_id: str
    query_text: str
    top_k: int = 6
    hybrid: bool = False
    filters: dict[str, Any] | None = None


class QueryResultItem(BaseModel):
    """Individual chunk result item."""
    
    text: str
    score: float
    citekey: str | None = None
    section: str | None = None
    page_span: tuple[int, int] | None = None
    section_path: list[str] | None = None
    doi: str | None = None
    url: str | None = None


class QueryResult(BaseModel):
    """Result DTO for chunk query use case."""
    
    items: list[QueryResultItem]
