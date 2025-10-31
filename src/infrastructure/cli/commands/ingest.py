import typer
import uuid
import logging
from pathlib import Path

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
from infrastructure.config.settings import Settings
from infrastructure.logging import configure_logging, set_correlation_id

app = typer.Typer(help="Ingest documents into CiteLoom")
logger = logging.getLogger(__name__)


@app.command()
def run(
    project: str = typer.Option(..., help="Project id, e.g. citeloom/clean-arch"),
    source: str = typer.Argument(..., help="Path to source document (e.g., PDF)"),
    references: str | None = typer.Option(None, help="Path to CSL-JSON references file"),
    embedding_model: str | None = typer.Option(None, help="Embedding model identifier"),
    config_path: str = typer.Option("citeloom.toml", help="Path to citeloom.toml configuration file"),
):
    """
    Ingest documents into a project-scoped collection.
    
    Converts documents, chunks them with heading awareness, enriches with citation metadata,
    generates embeddings, and stores in vector database.
    """
    # Configure logging
    configure_logging(logging.INFO)
    
    # Generate correlation ID
    correlation_id = str(uuid.uuid4())
    set_correlation_id(correlation_id)
    
    # Load settings
    try:
        settings = Settings.from_toml(config_path)
    except Exception as e:
        typer.echo(f"Error loading configuration: {e}", err=True)
        raise typer.Exit(1)
    
    # Get project settings
    try:
        project_settings = settings.get_project(project)
    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    
    # Use project settings or CLI overrides
    references_path = references or str(project_settings.references_json)
    model_id = embedding_model or project_settings.embedding_model
    
    # Get audit directory from settings
    audit_dir = Path(settings.paths.audit_dir)
    
    # Create request
    request = IngestRequest(
        project_id=project,
        source_path=source,
        references_path=references_path,
        embedding_model=model_id,
    )
    
    # Initialize adapters
    try:
        converter: TextConverterPort = DoclingConverterAdapter()
    except ImportError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    
    try:
        chunker: ChunkerPort = DoclingHybridChunkerAdapter()
    except ImportError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    
    resolver: MetadataResolverPort = ZoteroCslJsonResolver()
    embedder: EmbeddingPort = FastEmbedAdapter(default_model=model_id)
    index: VectorIndexPort = QdrantIndexAdapter(url=settings.qdrant.url)
    
    # Log start
    logger.info(
        f"Starting ingestion for project '{project}'",
        extra={"correlation_id": correlation_id, "source_path": source, "project_id": project},
    )
    
    # Run ingestion
    try:
        result = ingest_document(
            request=request,
            converter=converter,
            chunker=chunker,
            resolver=resolver,
            embedder=embedder,
            index=index,
            audit_dir=audit_dir,
            correlation_id=correlation_id,
        )
        
        # Output results
        typer.echo(f"correlation_id={correlation_id}")
        typer.echo(f"Ingested {result.chunks_written} chunks in {result.duration_seconds:.2f}s")
        
        if result.warnings:
            typer.echo("\nWarnings:")
            for warning in result.warnings:
                typer.echo(f"  - {warning}")
        
        logger.info(
            f"Ingestion complete: {result.chunks_written} chunks written",
            extra={
                "correlation_id": correlation_id,
                "chunks_written": result.chunks_written,
                "duration_seconds": result.duration_seconds,
            },
        )
        
    except Exception as e:
        logger.error(
            f"Ingestion failed: {e}",
            extra={"correlation_id": correlation_id, "project_id": project},
            exc_info=True,
        )
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
