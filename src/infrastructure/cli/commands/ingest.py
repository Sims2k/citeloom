import typer
import uuid
import logging

from application.dto.ingest import IngestRequest
from application.use_cases.ingest_document import ingest_document
from application.ports.converter import TextConverterPort
from application.ports.chunker import ChunkerPort
from application.ports.metadata_resolver import MetadataResolverPort
from application.ports.embeddings import EmbeddingPort
from application.ports.vector_index import VectorIndexPort
from infrastructure.adapters.docling_converter import DoclingConverterAdapter
from infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter
from infrastructure.adapters.zotero_metadata import ZoteroCslJsonResolver
from infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
from infrastructure.adapters.qdrant_index import QdrantIndexAdapter

app = typer.Typer(help="Ingest documents into CiteLoom")


@app.command()
def run(
    project: str = typer.Option(..., help="Project id, e.g. citeloom/clean-arch"),
    source: str = typer.Argument(..., help="Path to source document (e.g., PDF)"),
    references: str = typer.Option("references/clean-arch.json", help="Path to CSL-JSON"),
    model: str = typer.Option("sentence-transformers/all-MiniLM-L6-v2", help="Embedding model"),
):
    request = IngestRequest(
        project_id=project,
        source_path=source,
        references_path=references,
        embedding_model=model,
    )
    converter: TextConverterPort = DoclingConverterAdapter()
    chunker: ChunkerPort = DoclingHybridChunkerAdapter()
    resolver: MetadataResolverPort = ZoteroCslJsonResolver()
    embedder: EmbeddingPort = FastEmbedAdapter(default_model=model)
    index: VectorIndexPort = QdrantIndexAdapter()
    correlation_id = str(uuid.uuid4())
    logging.getLogger(__name__).info("ingest_start", extra={"correlation_id": correlation_id})
    result = ingest_document(request, converter, chunker, resolver, embedder, index)
    logging.getLogger(__name__).info("ingest_done", extra={"correlation_id": correlation_id, "chunks": result.chunks_written})
    typer.echo(f"correlation_id={correlation_id}")
    typer.echo(f"Ingested {result.chunks_written} chunks")
