"""MCP tool implementations for CiteLoom."""

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
from ...infrastructure.adapters.zotero_metadata import ZoteroCslJsonResolver
from ...infrastructure.config.settings import Settings
from ...infrastructure.logging import get_correlation_id

logger = logging.getLogger(__name__)


# Error codes per MCP tool contracts
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
    Create list of MCP tools for CiteLoom.
    
    Args:
        settings: Application settings
    
    Returns:
        List of MCP Tool definitions
    """
    return [
        Tool(
            name="store_chunks",
            description="Batched upsert of chunks into a project collection. Timeout: 15s, batch size: 100-500 chunks.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier (e.g., citeloom/clean-arch)",
                    },
                    "items": {
                        "type": "array",
                        "description": "Array of chunk objects with id, text, embedding, metadata",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "text": {"type": "string"},
                                "embedding": {"type": "array", "items": {"type": "number"}},
                                "metadata": {"type": "object"},
                            },
                            "required": ["id", "text", "embedding", "metadata"],
                        },
                        "minItems": 1,
                        "maxItems": 500,
                    },
                },
                "required": ["project", "items"],
            },
        ),
        Tool(
            name="find_chunks",
            description="Vector search for chunks in a project. Timeout: 8s, always enforces project filter.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier",
                    },
                    "query": {
                        "type": "string",
                        "description": "Natural language query text",
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
                        "description": "Additional filters (e.g., {\"tags\": [\"architecture\"]})",
                    },
                },
                "required": ["project", "query"],
            },
        ),
        Tool(
            name="query_hybrid",
            description="Hybrid search (full-text + vector fusion) for chunks. Timeout: 15s, requires hybrid_enabled=True.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project": {
                        "type": "string",
                        "description": "Project identifier",
                    },
                    "query": {
                        "type": "string",
                        "description": "Query text for BM25 and vector search",
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
                        "description": "Additional filters",
                    },
                },
                "required": ["project", "query"],
            },
        ),
        Tool(
            name="inspect_collection",
            description="Inspect project collection metadata and structure. Timeout: 5s.",
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
            description="List all configured projects with basic metadata. No timeout (fast read).",
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
            message=f"Project '{project_id}' not found. Available projects: [{available}]",
            details={"project_id": project_id, "available_projects": list(settings.projects.keys())},
        )


async def _run_with_timeout(coro: Any, timeout_seconds: float, operation_name: str) -> Any:
    """
    Run coroutine with timeout.
    
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


async def handle_store_chunks(arguments: dict[str, Any], settings: Settings) -> str:
    """Handle store_chunks tool call."""
    project_id = arguments["project"]
    items = arguments["items"]
    
    # Validate batch size
    if len(items) < 100 or len(items) > 500:
        raise MCPToolError(
            code="INVALID_INPUT",
            message=f"Batch size must be 100-500 chunks, got {len(items)}",
            details={"batch_size": len(items)},
        )
    
    _validate_project(project_id, settings)
    project_settings = settings.get_project(project_id)
    
    # Initialize adapters
    index = QdrantIndexAdapter(url=settings.qdrant.url)
    
    # Convert items to upsert format
    chunks_to_upsert = []
    for item in items:
        chunk_id = item["id"]
        text = item["text"]
        embedding = item["embedding"]
        metadata = item.get("metadata", {})
        
        # Build payload structure matching Qdrant adapter expectations
        payload = {
            "project": project_id,
            "source": metadata.get("source", {}),
            "zotero": metadata.get("zotero", {}),
            "doc": metadata.get("doc", {}),
            "embed_model": project_settings.embedding_model,
            "version": "1",
            "fulltext": text,
        }
        
        chunks_to_upsert.append({
            "id": chunk_id,
            "text": text,
            "embedding": embedding,
            "metadata": payload,
        })
    
    # Upsert with timeout (15s)
    async def _upsert() -> dict[str, Any]:
        # Run sync operation in thread pool for timeout support
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: index.upsert(
                    items=chunks_to_upsert,
                    project_id=project_id,
                    model_id=project_settings.embedding_model,
                )
            )
            return {
                "chunks_written": len(chunks_to_upsert),
                "project": project_id,
                "embed_model": project_settings.embedding_model,
                "warnings": [],
            }
        except EmbeddingModelMismatch as e:
            raise MCPToolError(
                code=MCPErrorCode.EMBEDDING_MISMATCH,
                message=str(e),
                details={
                    "project_id": project_id,
                    "expected_model": e.expected_model,
                    "provided_model": e.provided_model,
                },
            ) from e
    
    result = await _run_with_timeout(_upsert(), timeout_seconds=15.0, operation_name="store_chunks")
    return json.dumps(result, indent=2)


async def handle_find_chunks(arguments: dict[str, Any], settings: Settings) -> str:
    """Handle find_chunks tool call."""
    project_id = arguments["project"]
    query_text = arguments["query"]
    top_k = arguments.get("top_k", 6)
    filters = arguments.get("filters")
    
    _validate_project(project_id, settings)
    
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
        hybrid=False,  # Vector-only search
        filters=filters,
    )
    
    # Execute query with timeout (8s)
    async def _query() -> dict[str, Any]:
        # Run sync operation in thread pool for timeout support
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: query_chunks(request, embedder, index)
            )
            
            # Format items for MCP response
            items = []
            for item in result.items:
                items.append({
                    "render_text": item.text,
                    "score": item.score,
                    "citekey": item.citekey,
                    "section": item.section,
                    "page_span": list(item.page_span) if item.page_span else None,
                    "section_path": item.section_path,
                    "doi": item.doi,
                    "full_text": None,  # Not included by default
                })
            
            return {
                "items": items,
                "count": len(items),
            }
        except ProjectNotFound as e:
            raise MCPToolError(
                code=MCPErrorCode.INVALID_PROJECT,
                message=str(e),
                details={"project_id": project_id},
            ) from e
    
    result = await _run_with_timeout(_query(), timeout_seconds=8.0, operation_name="find_chunks")
    return json.dumps(result, indent=2)


async def handle_query_hybrid(arguments: dict[str, Any], settings: Settings) -> str:
    """Handle query_hybrid tool call."""
    project_id = arguments["project"]
    query_text = arguments["query"]
    top_k = arguments.get("top_k", 6)
    filters = arguments.get("filters")
    
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
        # Run sync operation in thread pool for timeout support
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(
                None,
                lambda: query_chunks(request, embedder, index)
            )
            
            # Format items for MCP response
            items = []
            for item in result.items:
                items.append({
                    "render_text": item.text,
                    "score": item.score,
                    "citekey": item.citekey,
                    "section": item.section,
                    "page_span": list(item.page_span) if item.page_span else None,
                    "section_path": item.section_path,
                    "doi": item.doi,
                })
            
            return {
                "items": items,
                "count": len(items),
                "hybrid_enabled": True,
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
    return json.dumps(result, indent=2)


async def handle_inspect_collection(arguments: dict[str, Any], settings: Settings) -> str:
    """Handle inspect_collection tool call."""
    project_id = arguments["project"]
    sample_count = arguments.get("sample", 0)
    
    _validate_project(project_id, settings)
    project_settings = settings.get_project(project_id)
    collection_name = f"proj-{project_id.replace('/', '-')}"
    
    # Initialize Qdrant adapter
    index = QdrantIndexAdapter(url=settings.qdrant.url)
    
    # Get collection info with timeout (5s)
    async def _inspect() -> dict[str, Any]:
        # Run sync operations in thread pool for timeout support
        loop = asyncio.get_event_loop()
        try:
            # Access Qdrant client to get collection info
            if index._client is None:
                raise MCPToolError(
                    code=MCPErrorCode.INDEX_UNAVAILABLE,
                    message=f"Qdrant collection '{collection_name}' not accessible",
                    details={"collection_name": collection_name, "project_id": project_id},
                )
            
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
            
            # Get embed_model from collection metadata or project settings
            embed_model = project_settings.embedding_model
            # Try to extract from collection metadata if available
            if hasattr(collection_info, "config") and hasattr(collection_info.config, "params"):
                # embed_model is stored in project settings as fallback
                pass
            
            # Get payload schema (sample a few points)
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
                    sample_payloads.append({
                        "id": str(point.id),
                        "payload": point.payload or {},
                    })
            
            # Determine payload keys from sample
            payload_keys = set()
            indexes = {"keyword": [], "fulltext": []}
            
            if sample_payloads:
                for sample in sample_payloads:
                    payload_keys.update(sample["payload"].keys())
            
            # Common payload structure
            common_keys = ["project", "source", "zotero", "doc", "embed_model", "version", "fulltext"]
            payload_keys = common_keys if not payload_keys else payload_keys
            
            # Indexes (simplified - Qdrant doesn't expose index metadata directly)
            indexes = {
                "keyword": ["project"],
                "fulltext": ["fulltext"] if settings.qdrant.create_fulltext_index else [],
            }
            
            return {
                "project": project_id,
                "collection": collection_name,
                "size": size,
                "embed_model": embed_model,
                "payload_keys": sorted(list(payload_keys)),
                "indexes": indexes,
                "sample": sample_payloads,
            }
        except Exception as e:
            if "not found" in str(e).lower() or "does not exist" in str(e).lower():
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
    return json.dumps(result, indent=2)


async def handle_list_projects(arguments: dict[str, Any], settings: Settings) -> str:
    """Handle list_projects tool call."""
    # No timeout for fast read operation
    projects = []
    for project_id, project_settings in settings.projects.items():
        projects.append({
            "id": project_id,
            "collection": f"proj-{project_id.replace('/', '-')}",
            "embed_model": project_settings.embedding_model,
            "hybrid_enabled": project_settings.hybrid_enabled,
        })
    
    return json.dumps({"projects": projects}, indent=2)


async def handle_tool_call(name: str, arguments: dict[str, Any], settings: Settings) -> str:
    """
    Route tool call to appropriate handler.
    
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
        if name == "store_chunks":
            return await handle_store_chunks(arguments, settings)
        elif name == "find_chunks":
            return await handle_find_chunks(arguments, settings)
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
            return json.dumps(e.to_json(), indent=2)
        except Exception as e:
            logger.error(f"Unexpected error in tool '{name}': {e}", exc_info=True)
            error = MCPToolError(
                code="INTERNAL_ERROR",
                message=f"Internal error: {e}",
                details={"tool_name": name},
            )
            return json.dumps(error.to_json(), indent=2)

