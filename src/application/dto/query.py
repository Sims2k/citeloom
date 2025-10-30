from pydantic import BaseModel


class QueryRequest(BaseModel):
    project_id: str
    query_text: str
    top_k: int = 6
    hybrid: bool = True


class QueryResultItem(BaseModel):
    text: str
    score: float
    citekey: str | None = None
    section: str | None = None
    page_span: tuple[int, int] | None = None


class QueryResult(BaseModel):
    items: list[QueryResultItem]
