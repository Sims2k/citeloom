import typer

from ...application.dto.query import QueryRequest
from ...application.use_cases.query_chunks import query_chunks
from ...application.ports.embeddings import EmbeddingPort
from ...application.ports.vector_index import VectorIndexPort
from ...adapters.fastembed_embeddings import FastEmbedAdapter
from ...adapters.qdrant_index import QdrantIndexAdapter

app = typer.Typer(help="Query chunks from CiteLoom")


@app.command()
def run(
    project: str = typer.Option(..., help="Project id"),
    q: str = typer.Option(..., help="Query text"),
    k: int = typer.Option(6, help="Top-k results"),
):
    request = QueryRequest(project_id=project, query_text=q, top_k=k)
    embedder: EmbeddingPort = FastEmbedAdapter()
    index: VectorIndexPort = QdrantIndexAdapter()
    result = query_chunks(request, embedder, index)
    for item in result.items:
        typer.echo(f"{item.score:.2f} | {item.citekey or '-'} | {item.section or '-'} | {item.text[:80]}")
