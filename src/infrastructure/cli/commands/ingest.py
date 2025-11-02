import typer
import uuid
import logging
from pathlib import Path

from src.application.dto.ingest import IngestRequest
from src.application.use_cases.ingest_document import ingest_document
from src.application.use_cases.batch_import_from_zotero import batch_import_from_zotero
from src.application.ports.converter import TextConverterPort
from src.application.ports.chunker import ChunkerPort
from src.application.ports.metadata_resolver import MetadataResolverPort
from src.application.ports.embeddings import EmbeddingPort
from src.application.ports.vector_index import VectorIndexPort
from src.infrastructure.adapters.docling_converter import DoclingConverterAdapter
from src.infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter
from src.infrastructure.adapters.zotero_metadata import ZoteroPyzoteroResolver
from src.infrastructure.adapters.zotero_importer import ZoteroImporterAdapter
from src.infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
from src.infrastructure.adapters.qdrant_index import QdrantIndexAdapter
from src.infrastructure.config.settings import Settings
from src.infrastructure.logging import configure_logging, set_correlation_id

app = typer.Typer(help="Ingest documents into CiteLoom")
logger = logging.getLogger(__name__)


@app.command()
def run(
    project: str = typer.Option(..., help="Project id, e.g. citeloom/clean-arch"),
    source: str | None = typer.Argument(None, help="Path to source document or directory (defaults to assets/raw if not specified)"),
    zotero_collection: str | None = typer.Option(None, help="Zotero collection name or key to import from (requires Zotero config)"),
    zotero_config: str | None = typer.Option(None, help="Zotero configuration (JSON string or env vars will be used)"),
    embedding_model: str | None = typer.Option(None, help="Embedding model identifier"),
    config_path: str = typer.Option("citeloom.toml", help="Path to citeloom.toml configuration file"),
):
    """
    Ingest documents into a project-scoped collection.
    
    Converts documents, chunks them with heading awareness, enriches with citation metadata,
    generates embeddings, and stores in vector database.
    
    If source is not specified, processes all documents in assets/raw directory.
    If source is a directory, processes all supported documents in that directory.
    If source is a file, processes that single file.
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
    model_id = embedding_model or project_settings.embedding_model
    
    # Zotero config: parse JSON if provided, otherwise use env vars (resolver will handle)
    zotero_config_dict = None
    if zotero_config:
        import json
        try:
            zotero_config_dict = json.loads(zotero_config)
        except json.JSONDecodeError:
            typer.echo(f"Warning: Invalid JSON for zotero_config, using environment variables instead", err=True)
    
    # Handle Zotero collection import if requested
    if zotero_collection:
        # Initialize Zotero importer
        try:
            zotero_importer = ZoteroImporterAdapter(zotero_config=zotero_config_dict)
        except Exception as e:
            typer.echo(f"Error initializing Zotero importer: {e}", err=True)
            raise typer.Exit(1)
        
        # Resolve collection key if name provided
        collection_key = None
        collection_name = None
        if len(zotero_collection) == 8 and zotero_collection.isalnum():
            # Looks like a collection key (8 alphanumeric chars)
            collection_key = zotero_collection
        else:
            # Try to find by name
            collection_info = zotero_importer.find_collection_by_name(zotero_collection)
            if collection_info:
                collection_key = collection_info.get("key")
                collection_name = collection_info.get("name", zotero_collection)
            else:
                typer.echo(f"Error: Collection '{zotero_collection}' not found", err=True)
                raise typer.Exit(1)
        
        # Get audit directory from settings
        audit_dir = Path(settings.paths.audit_dir)
        
        # Initialize adapters for batch import
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
        
        resolver: MetadataResolverPort = ZoteroPyzoteroResolver(zotero_config=zotero_config_dict)
        embedder: EmbeddingPort = FastEmbedAdapter(default_model=model_id)
        index: VectorIndexPort = QdrantIndexAdapter(url=settings.qdrant.url)
        
        # Run batch import
        typer.echo(f"Importing from Zotero collection: {collection_name or collection_key}")
        
        try:
            result = batch_import_from_zotero(
                project_id=project,
                collection_key=collection_key,
                collection_name=collection_name,
                zotero_importer=zotero_importer,
                converter=converter,
                chunker=chunker,
                resolver=resolver,
                embedder=embedder,
                index=index,
                embedding_model=model_id,
                zotero_config=zotero_config_dict,
                audit_dir=audit_dir,
            )
            
            typer.echo(f"\n{'='*60}")
            typer.echo(f"correlation_id={result['correlation_id']}")
            typer.echo(f"Collection: {result['collection_name']}")
            typer.echo(f"Imported {result['chunks_written']} chunks from {result['total_documents']} document(s)")
            typer.echo(f"Duration: {result['duration_seconds']:.2f} seconds")
            
            if result['warnings']:
                typer.echo(f"\nWarnings ({len(result['warnings'])}):")
                for warning in result['warnings']:
                    typer.echo(f"  - {warning}")
            
            if result['errors']:
                typer.echo(f"\nErrors ({len(result['errors'])}):")
                for error in result['errors']:
                    typer.echo(f"  - {error}")
            
            logger.info(
                f"Zotero batch import complete",
                extra={
                    "correlation_id": result['correlation_id'],
                    "collection_key": result['collection_key'],
                    "chunks_written": result['chunks_written'],
                    "documents_processed": result['total_documents'],
                },
            )
            
        except Exception as e:
            error_msg = f"Zotero batch import failed: {e}"
            logger.error(error_msg, extra={"correlation_id": correlation_id}, exc_info=True)
            typer.echo(f"Error: {error_msg}", err=True)
            raise typer.Exit(1)
        
        return
    
    # Get audit directory from settings
    audit_dir = Path(settings.paths.audit_dir)
    
    # Determine source path: use provided source or default to assets/raw from settings
    if source is None:
        source = settings.paths.raw_dir
        typer.echo(f"No source specified, using default directory: {source}")
    
    source_path = Path(source)
    
    # Collect documents to process
    documents_to_process: list[Path] = []
    
    if source_path.is_file():
        # Single file
        documents_to_process = [source_path]
    elif source_path.is_dir():
        # Directory: collect all supported documents
        supported_extensions = {".pdf", ".txt", ".md"}  # Add more as needed
        for ext in supported_extensions:
            documents_to_process.extend(source_path.glob(f"*{ext}"))
        
        if not documents_to_process:
            typer.echo(f"No supported documents found in {source_path}")
            typer.echo(f"Supported extensions: {', '.join(supported_extensions)}")
            raise typer.Exit(1)
        
        typer.echo(f"Found {len(documents_to_process)} document(s) to process")
    else:
        typer.echo(f"Error: Source path does not exist: {source}")
        raise typer.Exit(1)
    
    # Initialize adapters (shared across all documents)
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
    
    resolver: MetadataResolverPort = ZoteroPyzoteroResolver(zotero_config=zotero_config_dict)
    embedder: EmbeddingPort = FastEmbedAdapter(default_model=model_id)
    index: VectorIndexPort = QdrantIndexAdapter(url=settings.qdrant.url)
    
    # Process each document
    total_chunks = 0
    total_documents = 0
    all_warnings: list[str] = []
    
    logger.info(
        f"Starting ingestion for project '{project}'",
        extra={"correlation_id": correlation_id, "source_path": str(source_path), "project_id": project, "document_count": len(documents_to_process)},
    )
    
    for doc_path in documents_to_process:
        typer.echo(f"\nProcessing: {doc_path.name}")
        
        # Create request for this document
        request = IngestRequest(
            project_id=project,
            source_path=str(doc_path),
            zotero_config=zotero_config_dict,
            embedding_model=model_id,
        )
        
        # Run ingestion for this document
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
            
            total_chunks += result.chunks_written
            total_documents += result.documents_processed
            all_warnings.extend(result.warnings)
            
            typer.echo(f"  [OK] {result.chunks_written} chunks from {doc_path.name}")
            
        except Exception as e:
            error_msg = f"Failed to process {doc_path.name}: {e}"
            logger.error(
                error_msg,
                extra={"correlation_id": correlation_id, "project_id": project, "source_path": str(doc_path)},
                exc_info=True,
            )
            typer.echo(f"  [ERROR] {e}")
            all_warnings.append(error_msg)
            # Continue with next document
            continue
    
    # Output summary
    typer.echo(f"\n{'='*60}")
    typer.echo(f"correlation_id={correlation_id}")
    typer.echo(f"Ingested {total_chunks} chunks from {total_documents} document(s)")
    
    if all_warnings:
        typer.echo(f"\nWarnings ({len(all_warnings)}):")
        for warning in all_warnings:
            typer.echo(f"  - {warning}")
    
    logger.info(
        f"Ingestion complete: {total_chunks} chunks written from {total_documents} documents",
        extra={
            "correlation_id": correlation_id,
            "chunks_written": total_chunks,
            "documents_processed": total_documents,
        },
    )
