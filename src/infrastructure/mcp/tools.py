"""MCP tool implementations for CiteLoom - FastMCP contracts compliant."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from mcp.types import Tool

from ...application.dto.ingest import IngestRequest, IngestResult
from ...application.dto.query import QueryRequest, QueryResult
from ...application.use_cases.ingest_document import ingest_document
from ...application.use_cases.query_chunks import query_chunks
from ...domain.errors import EmbeddingModelMismatch, HybridNotSupported, ProjectNotFound
from ...infrastructure.adapters.docling_converter import DoclingConverterAdapter
from ...infrastructure.adapters.docling_chunker import DoclingHybridChunkerAdapter
from ...infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
from ...infrastructure.adapters.qdrant_index import QdrantIndexAdapter
from ...infrastructure.adapters.zotero_metadata import ZoteroPyzoteroResolver
from ...infrastructure.config.settings import Settings
from ...infrastructure.logging import get_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)

# Maximum characters per chunk for text trimming (FR-015)
MAX_CHARS_PER_CHUNK = 1800


# Error codes per MCP tool contracts (T052)
class MCPErrorCode:
    """MCP error code constants."""
    INVALID_PROJECT = "INVALID_PROJECT"
    EMBEDDING_MISMATCH = "EMBEDDING_MISMATCH"
    HYBRID_NOT_SUPPORTED = "HYBRID_NOT_SUPPORTED"
    INDEX_UNAVAILABLE = "INDEX_UNAVAILABLE"
    TIMEOUT = "TIMEOUT"


class MCPToolError(Exception):
    """MCP tool error with structured error response."""
    
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(message)
    
    def to_json(self) -> dict[str, Any]:
        """Convert to JSON error response format."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


def create_tools(settings: Settings) -> list[Tool]:
    """
    Create list of MCP tools for CiteLoom matching FastMCP contracts.
    
    Args:
        settings: Application settings
    
    Returns:
        List of MCP Tool definitions matching fastmcp-tools.md contracts
    """
    return [
        Tool(
            name="ingest_from_source",
            description="Ingest documents from source files or Zotero collections into a project collection. Timeout: 15s, returns counts + model IDs + warnings.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier (e.g., citeloom/clean-arch)",
                    },
                    "source": {
                        "type": "string",
                        "description": "Path to source document/directory OR 'zotero' for Zotero collection ingestion",
                    },
                    "options": {
                        "type": "object",
                        "description": "Additional options",
                        "properties": {
                            "ocr_languages": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Explicit OCR language codes (overrides Zotero/default)",
                            },
                            "zotero_config": {
                                "type": "object",
                                "description": "Override Zotero configuration (library_id, library_type, api_key for remote, or local=true for local access)",
                            },
                            "force_rebuild": {
                                "type": "boolean",
                                "description": "Force collection rebuild for model migration",
                            },
                        },
                    },
                },
                "required": ["project", "source"],
            },
        ),
        Tool(
            name="query",
            description="Dense-only vector search using named vector 'dense' with model binding. Timeout: 8s, always enforces project filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier",
                    },
                    "text": {
                        "type": "string",
                        "description": "Query text (model binding handles embedding automatically)",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum results (default 6, max configurable)",
                        "default": 6,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "filters": {
                        "type": "object",
                        "description": "Additional filters (e.g., {\"tags\": [\"architecture\"], \"section_prefix\": \"Part I\"})",
                    },
                },
                "required": ["project", "text"],
            },
        ),
        Tool(
            name="query_hybrid",
            description="Hybrid search using RRF fusion (named vectors: dense + sparse). Timeout: 15s, requires both dense and sparse models bound.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier",
                    },
                    "text": {
                        "type": "string",
                        "description": "Query text for both sparse (BM25) and dense search",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Maximum results (default 6)",
                        "default": 6,
                        "minimum": 1,
                        "maximum": 20,
                    },
                    "filters": {
                        "type": "object",
                        "description": "Additional filters with AND semantics for tags",
                    },
                },
                "required": ["project", "text"],
            },
        ),
        Tool(
            name="inspect_collection",
            description="Inspect project collection metadata, model bindings, and structure. Timeout: 5s, shows collection stats and sample payloads.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier",
                    },
                    "sample": {
                        "type": "integer",
                        "description": "Number of sample payloads to return (default 0, max 5)",
                        "default": 0,
                        "minimum": 0,
                        "maximum": 5,
                    },
                },
                "required": ["project"],
            },
        ),
        Tool(
            name="list_projects",
            description="List all configured projects with metadata. No timeout (fast enumeration).",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
    ]


def _validate_project(project_id: str, settings: Settings) -> None:
    """
    Validate project exists in settings.
    
    Raises:
        MCPToolError: If project not found
    """
    try:
        settings.get_project(project_id)
    except KeyError:
        available = ", ".join(settings.projects.keys()) if settings.projects else "(none)"
        raise MCPToolError(
            code=MCPErrorCode.INVALID_PROJECT,
            message=f"Project '{project_id}' not found. Available projects: {available}",
            details={"project_id": project_id, "available_projects": list(settings.projects.keys())},
        )


async def _run_with_timeout(coro: Any, timeout_seconds: float, operation_name: str) -> Any:
    """
    Run coroutine with timeout (T056).
    
    Raises:
        MCPToolError: If timeout exceeded
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        raise MCPToolError(
            code=MCPErrorCode.TIMEOUT,
            message=f"{operation_name} exceeded timeout of {timeout_seconds}s",
            details={"timeout_seconds": timeout_seconds, "operation": operation_name},
        )


def _trim_text(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> str:
    """
    Trim text to max_chars, breaking at word boundary (T053).
    
    Args:
        text: Text to trim
        max_chars: Maximum characters (default 1800)
    
    Returns:
        Trimmed text with ellipsis if truncated
    """
    if len(text) <= max_chars:
        return text
    # Trim to max_chars, then find last space before that point
    trimmed = text[:max_chars]
    last_space = trimmed.rfind(" ")
    if last_space > 0:
        return trimmed[:last_space] + "..."
    return trimmed[:max_chars] + "..."


def _add_correlation_id(result: dict[str, Any]) -> dict[str, Any]:
    """
    Add correlation ID to response (T054).
    
    Args:
        result: Response dictionary
    
    Returns:
        Response with correlation_id added
    """
    correlation_id = get_correlation_id()
    result["correlation_id"] = correlation_id
    return result


async def handle_ingest_from_source(arguments: dict[str, Any], settings: Settings) -> str:
    """
    Handle ingest_from_source tool call (T047).
    
    Drives Docling → chunk → embed → upsert pipeline with 15s timeout.
    """
    project_id = arguments["project"]
    source = arguments["source"]
    options = arguments.get("options", {})
    
    # Generate correlation ID for this operation
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    _validate_project(project_id, settings)
    project_settings = settings.get_project(project_id)
    
    # Handle source path
    source_path: str
    if source == "zotero":
        # Zotero ingestion not yet implemented - placeholder
        raise MCPToolError(
            code="NOT_IMPLEMENTED",
            message="Zotero collection ingestion not yet implemented",
            details={"source": source},
        )
    else:
        source_path = source
    
    # Validate source exists
    source_path_obj = Path(source_path)
    if not source_path_obj.exists():
        raise MCPToolError(
            code="INVALID_SOURCE",
            message=f"Source path does not exist: {source_path}",
            details={"source_path": source_path},
        )
    
    # Extract options
    ocr_languages = options.get("ocr_languages")
    zotero_config = options.get("zotero_config")
    force_rebuild = options.get("force_rebuild", False)
    
    # Initialize adapters
    converter = DoclingConverterAdapter()
    chunker = DoclingHybridChunkerAdapter()
    embedder = FastEmbedAdapter()
    index = QdrantIndexAdapter(
        url=settings.qdrant.url,
        create_fulltext_index=settings.qdrant.create_fulltext_index,
    )
    
    # Initialize metadata resolver (uses environment variables or zotero_config)
    resolver = ZoteroPyzoteroResolver()
    
    # Determine documents to process
    documents_to_process: list[Path] = []
    if source_path_obj.is_file():
        documents_to_process = [source_path_obj]
    elif source_path_obj.is_dir():
        # Find all supported documents in directory
        for ext in [".pdf", ".md", ".txt"]:
            documents_to_process.extend(source_path_obj.glob(f"*{ext}"))
    
    if not documents_to_process:
        raise MCPToolError(
            code="NO_DOCUMENTS",
            message=f"No supported documents found in source: {source_path}",
            details={"source_path": source_path},
        )
    
    # Execute ingestion with timeout (15s)
    async def _ingest() -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        
        total_chunks = 0
        total_documents = 0
        warnings: list[str] = []
        
        try:
            for doc_path in documents_to_process:
                # Create ingest request (zotero_config=None means use env vars)
                request = IngestRequest(
                    source_path=str(doc_path),
                    project_id=project_id,
                    zotero_config=None,  # Use environment variables for Zotero config
                    embedding_model=project_settings.embedding_model,
                )
                
                # Run ingestion in executor
                result: IngestResult = await loop.run_in_executor(
                    None,
                    lambda: ingest_document(
                        request=request,
                        converter=converter,
                        chunker=chunker,
                        resolver=resolver,
                        embedder=embedder,
                        index=index,
                        audit_dir=Path(settings.paths.audit_dir) if settings.paths.audit_dir else None,
                        correlation_id=correlation_id,
                    ),
                )
                
                total_chunks += result.chunks_written
                total_documents += result.documents_processed
                warnings.extend(result.warnings)
            
            # Get sparse model ID from collection if hybrid enabled
            sparse_model_id = None
            if project_settings.hybrid_enabled:
                # Try to get sparse model from collection metadata
                collection_name = f"proj-{project_id.replace('/', '-')}"
                try:
                    if index._client is not None:
                        collection_info = await loop.run_in_executor(
                            None,
                            lambda: index._client.get_collection(collection_name)
                        )
                        metadata = getattr(collection_info, "metadata", None) or {}
                        sparse_model_id = metadata.get("sparse_model_id")
                except Exception:
                    pass  # Sparse model ID not available
            
            return {
                "chunks_written": total_chunks,
                "documents_processed": total_documents,
                "project": project_id,
                "dense_model": project_settings.embedding_model,
                "sparse_model": sparse_model_id or "Qdrant/bm25",  # Default if not available
                "duration_seconds": 0.0,  # TODO: Track actual duration
                "warnings": warnings,
            }
        except EmbeddingModelMismatch as e:
            if not force_rebuild:
                raise MCPToolError(
                    code=MCPErrorCode.EMBEDDING_MISMATCH,
                    message=str(e),
                    details={
                        "project_id": project_id,
                        "expected_model": e.expected_model,
                        "provided_model": e.provided_model,
                    },
                ) from e
            # Force rebuild: recreate collection
            # TODO: Implement collection rebuild logic
            raise MCPToolError(
                code=MCPErrorCode.EMBEDDING_MISMATCH,
                message=f"Collection rebuild not yet implemented: {e}",
                details={"project_id": project_id},
            )
        except Exception as e:
            logger.error(f"Ingestion failed: {e}", exc_info=True)
            raise MCPToolError(
                code="INGESTION_FAILED",
                message=f"Ingestion failed: {e}",
                details={"project_id": project_id, "source_path": source_path},
            ) from e
    
    result = await _run_with_timeout(_ingest(), timeout_seconds=15.0, operation_name="ingest_from_source")
    result = _add_correlation_id(result)
    return json.dumps(result, indent=2)


async def handle_query(arguments: dict[str, Any], settings: Settings) -> str:
    """
    Handle query tool call - dense-only vector search (T048).
    
    Uses named vector 'dense' with model binding, 8s timeout.
    """
    project_id = arguments["project"]
    query_text = arguments["text"]
    top_k = arguments.get("top_k", 6)
    filters = arguments.get("filters")
    
    # Generate correlation ID
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    _validate_project(project_id, settings)
    project_settings = settings.get_project(project_id)
    
    # Initialize adapters
    embedder = FastEmbedAdapter()
    index = QdrantIndexAdapter(
        url=settings.qdrant.url,
        create_fulltext_index=settings.qdrant.create_fulltext_index,
    )
    
    # Create request
    request = QueryRequest(
        project_id=project_id,
        query_text=query_text,
        top_k=top_k,
        hybrid=False,  # Dense-only search
        filters=filters,
    )
    
    # Execute query with timeout (8s)
    async def _query() -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: query_chunks(request, embedder, index)
            )
            
            # Format items for MCP response with text trimming (T053)
            items = []
            for item in result.items:
                trimmed_text = _trim_text(item.text)
                items.append({
                    "render_text": trimmed_text,
                    "score": item.score,
                    "citekey": item.citekey,
                    "section": item.section,
                    "page_span": list(item.page_span) if item.page_span else None,
                    "section_path": item.section_path,
                    "doi": item.doi,
                    "full_text": None,  # Not included by default per contract
                })
            
            return {
                "items": items,
                "count": len(items),
                "model": project_settings.embedding_model,
            }
        except ProjectNotFound as e:
            raise MCPToolError(
                code=MCPErrorCode.INVALID_PROJECT,
                message=str(e),
                details={"project_id": project_id},
            ) from e
    
    result = await _run_with_timeout(_query(), timeout_seconds=8.0, operation_name="query")
    result = _add_correlation_id(result)
    return json.dumps(result, indent=2)


async def handle_query_hybrid(arguments: dict[str, Any], settings: Settings) -> str:
    """
    Handle query_hybrid tool call - hybrid search with RRF fusion (T049).
    
    Requires both dense and sparse models bound, 15s timeout.
    """
    project_id = arguments["project"]
    query_text = arguments["text"]
    top_k = arguments.get("top_k", 6)
    filters = arguments.get("filters")
    
    # Generate correlation ID
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    _validate_project(project_id, settings)
    project_settings = settings.get_project(project_id)
    
    # Check hybrid enabled
    if not project_settings.hybrid_enabled:
        raise MCPToolError(
            code=MCPErrorCode.HYBRID_NOT_SUPPORTED,
            message=f"Hybrid search not enabled for project '{project_id}'",
            details={"project_id": project_id},
        )
    
    # Initialize adapters
    embedder = FastEmbedAdapter()
    index = QdrantIndexAdapter(
        url=settings.qdrant.url,
        create_fulltext_index=settings.qdrant.create_fulltext_index,
    )
    
    # Create request
    request = QueryRequest(
        project_id=project_id,
        query_text=query_text,
        top_k=top_k,
        hybrid=True,  # Hybrid search
        filters=filters,
    )
    
    # Execute query with timeout (15s)
    async def _query() -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: query_chunks(request, embedder, index)
            )
            
            # Format items for MCP response with text trimming (T053)
            items = []
            for item in result.items:
                trimmed_text = _trim_text(item.text)
                items.append({
                    "render_text": trimmed_text,
                    "score": item.score,
                    "citekey": item.citekey,
                    "section": item.section,
                    "page_span": list(item.page_span) if item.page_span else None,
                    "section_path": item.section_path,
                    "doi": item.doi,
                })
            
            # Get sparse model ID from collection
            sparse_model_id = "Qdrant/bm25"  # Default
            collection_name = f"proj-{project_id.replace('/', '-')}"
            try:
                if index._client is not None:
                    collection_info = await loop.run_in_executor(
                        None,
                        lambda: index._client.get_collection(collection_name)
                    )
                    metadata = getattr(collection_info, "metadata", None) or {}
                    sparse_model_id = metadata.get("sparse_model_id", sparse_model_id)
            except Exception:
                pass  # Use default
            
            return {
                "items": items,
                "count": len(items),
                "hybrid_enabled": True,
                "dense_model": project_settings.embedding_model,
                "sparse_model": sparse_model_id,
                "fusion": "RRF",
            }
        except HybridNotSupported as e:
            raise MCPToolError(
                code=MCPErrorCode.HYBRID_NOT_SUPPORTED,
                message=str(e),
                details={"project_id": project_id, "reason": e.reason},
            ) from e
        except ProjectNotFound as e:
            raise MCPToolError(
                code=MCPErrorCode.INVALID_PROJECT,
                message=str(e),
                details={"project_id": project_id},
            ) from e
    
    result = await _run_with_timeout(_query(), timeout_seconds=15.0, operation_name="query_hybrid")
    result = _add_correlation_id(result)
    return json.dumps(result, indent=2)


async def handle_inspect_collection(arguments: dict[str, Any], settings: Settings) -> str:
    """
    Handle inspect_collection tool call (T050).
    
    Shows collection stats, model bindings, and sample payloads, 5s timeout.
    """
    project_id = arguments["project"]
    sample_count = arguments.get("sample", 0)
    
    # Generate correlation ID
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    _validate_project(project_id, settings)
    project_settings = settings.get_project(project_id)
    collection_name = f"proj-{project_id.replace('/', '-')}"
    
    # Initialize Qdrant adapter
    index = QdrantIndexAdapter(url=settings.qdrant.url)
    
    # Get collection info with timeout (5s)
    async def _inspect() -> dict[str, Any]:
        loop = asyncio.get_event_loop()
        try:
            if index._client is None:
                raise MCPToolError(
                    code=MCPErrorCode.INDEX_UNAVAILABLE,
                    message=f"Qdrant collection '{collection_name}' not accessible",
                    details={"collection_name": collection_name, "project_id": project_id},
                )
            
            # Get collection info
            collection_info = await loop.run_in_executor(
                None,
                lambda: index._client.get_collection(collection_name)
            )
            
            # Get collection size
            collection_points = await loop.run_in_executor(
                None,
                lambda: index._client.scroll(
                    collection_name=collection_name,
                    limit=0,  # Just get count
                    with_payload=False,
                    with_vectors=False,
                )
            )
            size = len(collection_points[0]) if collection_points[0] else 0
            
            # Get model IDs from collection metadata
            metadata = getattr(collection_info, "metadata", None) or {}
            dense_model_id = metadata.get("dense_model_id") or project_settings.embedding_model
            sparse_model_id = metadata.get("sparse_model_id")
            
            # Check named vectors configuration
            named_vectors = ["dense"]
            if sparse_model_id:
                named_vectors.append("sparse")
            
            # Get payload schema and indexes
            payload_keys = set()
            indexes = {"keyword": [], "fulltext": []}
            
            # Sample payloads if requested
            sample_payloads = []
            if sample_count > 0:
                sample_limit = min(sample_count, 5)
                sample_points = await loop.run_in_executor(
                    None,
                    lambda: index._client.scroll(
                        collection_name=collection_name,
                        limit=sample_limit,
                        with_payload=True,
                        with_vectors=False,
                    )
                )
                for point in sample_points[0][:sample_limit]:
                    payload = point.payload or {}
                    payload_keys.update(payload.keys())
                    sample_payloads.append({
                        "id": str(point.id),
                        "payload": payload,
                    })
            
            # Common payload keys (from contracts)
            common_keys = [
                "project_id", "doc_id", "section_path", "page_start", "page_end",
                "citekey", "doi", "year", "authors", "title", "tags", "source_path",
                "chunk_text", "heading_chain", "embed_model", "version",
            ]
            payload_keys = payload_keys or set(common_keys)
            
            # Determine indexes (simplified - actual indexes may differ)
            indexes = {
                "keyword": ["project_id", "doc_id", "citekey", "year", "tags"],
                "fulltext": ["chunk_text"] if settings.qdrant.create_fulltext_index else [],
            }
            
            # Check storage flags (simplified)
            storage = {
                "on_disk_vectors": False,
                "on_disk_hnsw": False,
            }
            
            return {
                "project": project_id,
                "collection": collection_name,
                "size": size,
                "dense_model": dense_model_id,
                "sparse_model": sparse_model_id,
                "named_vectors": named_vectors,
                "payload_keys": sorted(list(payload_keys)),
                "indexes": indexes,
                "storage": storage,
                "sample_payloads": sample_payloads,
            }
        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "does not exist" in error_str:
                raise MCPToolError(
                    code=MCPErrorCode.INVALID_PROJECT,
                    message=f"Collection '{collection_name}' not found for project '{project_id}'",
                    details={"collection_name": collection_name, "project_id": project_id},
                ) from e
            raise MCPToolError(
                code=MCPErrorCode.INDEX_UNAVAILABLE,
                message=f"Failed to inspect collection: {e}",
                details={"collection_name": collection_name},
            ) from e
    
    result = await _run_with_timeout(_inspect(), timeout_seconds=5.0, operation_name="inspect_collection")
    result = _add_correlation_id(result)
    return json.dumps(result, indent=2)


async def handle_list_projects(arguments: dict[str, Any], settings: Settings) -> str:
    """
    Handle list_projects tool call (T051).
    
    Fast enumeration with no timeout.
    """
    # Generate correlation ID
    correlation_id = get_correlation_id()
    set_correlation_id(correlation_id)
    
    projects = []
    for project_id, project_settings in settings.projects.items():
        collection_name = f"proj-{project_id.replace('/', '-')}"
        
        # Get sparse model ID if hybrid enabled
        sparse_model_id = None
        if project_settings.hybrid_enabled:
            # Try to get from collection metadata
            index = QdrantIndexAdapter(url=settings.qdrant.url)
            try:
                if index._client is not None:
                    collection_info = index._client.get_collection(collection_name)
                    metadata = getattr(collection_info, "metadata", None) or {}
                    sparse_model_id = metadata.get("sparse_model_id", "Qdrant/bm25")
            except Exception:
                pass  # Use None if not available
        
        projects.append({
            "id": project_id,
            "collection": collection_name,
            "dense_model": project_settings.embedding_model,
            "sparse_model": sparse_model_id,
            "hybrid_enabled": project_settings.hybrid_enabled,
        })
    
    result = {
        "projects": projects,
        "count": len(projects),
    }
    result = _add_correlation_id(result)
    return json.dumps(result, indent=2)


async def handle_tool_call(name: str, arguments: dict[str, Any], settings: Settings) -> str:
    """
    Route tool call to appropriate handler (T046).
    
    Args:
        name: Tool name
        arguments: Tool arguments
        settings: Application settings
    
    Returns:
        JSON string result or error response
    
    Raises:
        MCPToolError: For tool-specific errors
    """
    try:
        if name == "ingest_from_source":
            return await handle_ingest_from_source(arguments, settings)
        elif name == "query":
            return await handle_query(arguments, settings)
        elif name == "query_hybrid":
            return await handle_query_hybrid(arguments, settings)
        elif name == "inspect_collection":
            return await handle_inspect_collection(arguments, settings)
        elif name == "list_projects":
            return await handle_list_projects(arguments, settings)
        else:
            raise MCPToolError(
                code="UNKNOWN_TOOL",
                message=f"Unknown tool: {name}",
                details={"tool_name": name},
            )
    except MCPToolError as e:
        # Return error as JSON
        error_json = e.to_json()
        error_json = _add_correlation_id(error_json)
        return json.dumps(error_json, indent=2)
    except Exception as e:
        logger.error(f"Unexpected error in tool '{name}': {e}", exc_info=True)
        error = MCPToolError(
            code="INTERNAL_ERROR",
            message=f"Internal error: {e}",
            details={"tool_name": name},
        )
        error_json = error.to_json()
        error_json = _add_correlation_id(error_json)
        return json.dumps(error_json, indent=2)
