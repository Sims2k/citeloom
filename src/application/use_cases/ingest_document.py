from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Mapping, Any, Sequence

from ...infrastructure.logging import get_correlation_id
from ..dto.ingest import IngestRequest, IngestResult
from ..ports.converter import TextConverterPort
from ..ports.chunker import ChunkerPort
from ..ports.metadata_resolver import MetadataResolverPort
from ..ports.embeddings import EmbeddingPort
from ..ports.vector_index import VectorIndexPort

logger = logging.getLogger(__name__)


def ingest_document(
    request: IngestRequest,
    converter: TextConverterPort,
    chunker: ChunkerPort,
    resolver: MetadataResolverPort,
    embedder: EmbeddingPort,
    index: VectorIndexPort,
    audit_dir: Path | None = None,
    correlation_id: str | None = None,
) -> IngestResult:
    """
    Orchestrate document ingestion: convert → chunk → metadata → embed → upsert → audit.
    
    Args:
        request: IngestRequest with source_path, project_id, references_path, embedding_model
        converter: TextConverterPort for document conversion
        chunker: ChunkerPort for heading-aware chunking
        resolver: MetadataResolverPort for citation metadata resolution
        embedder: EmbeddingPort for embedding generation
        index: VectorIndexPort for vector storage
        audit_dir: Optional directory for audit JSONL logs
        correlation_id: Optional correlation ID (generated if not provided)
    
    Returns:
        IngestResult with chunks_written, documents_processed, duration_seconds, embed_model, warnings
    """
    start_time = time.time()
    correlation_id = correlation_id or get_correlation_id()
    
    logger.info(
        f"Starting ingestion for project '{request.project_id}'",
        extra={"correlation_id": correlation_id, "source_path": request.source_path},
    )
    
    warnings: list[str] = []
    
    # Step 1: Convert document
    try:
        conversion: Mapping[str, Any] = converter.convert(request.source_path)
        doc_id = conversion.get("doc_id", "unknown")
        logger.info(
            f"Document converted: doc_id={doc_id}",
            extra={"correlation_id": correlation_id, "doc_id": doc_id},
        )
    except Exception as e:
        error_msg = f"Document conversion failed: {e}"
        logger.error(error_msg, extra={"correlation_id": correlation_id}, exc_info=True)
        warnings.append(error_msg)
        raise
    
    # Step 2: Chunk document
    try:
        from ...domain.policy.chunking_policy import ChunkingPolicy
        
        # TODO: Load policy from settings/config
        policy = ChunkingPolicy()
        chunks: Sequence[Any] = chunker.chunk(conversion, policy)
        
        logger.info(
            f"Document chunked: {len(chunks)} chunks created",
            extra={"correlation_id": correlation_id, "doc_id": doc_id, "chunk_count": len(chunks)},
        )
    except Exception as e:
        error_msg = f"Chunking failed: {e}"
        logger.error(error_msg, extra={"correlation_id": correlation_id, "doc_id": doc_id}, exc_info=True)
        warnings.append(error_msg)
        raise
    
    # Step 3: Resolve metadata and enrich chunks
    texts: list[str] = []
    enriched: list[dict[str, Any]] = []
    for chunk in chunks:
        # Extract text from chunk (handle both Chunk objects and dicts)
        if hasattr(chunk, "text"):
            chunk_text = chunk.text
            chunk_dict = {
                "id": chunk.id,
                "doc_id": chunk.doc_id,
                "text": chunk.text,
                "page_span": chunk.page_span,
                "section_heading": chunk.section_heading,
                "section_path": chunk.section_path,
                "chunk_idx": chunk.chunk_idx,
            }
        else:
            chunk_dict = dict(chunk)  # type: ignore[arg-type]
            chunk_text = chunk_dict.get("text", "")
        
        # Resolve citation metadata
        try:
            meta = resolver.resolve(
                citekey=None,  # TODO: Extract from chunk if available
                references_path=request.references_path,
                doc_id=doc_id,
                source_hint=None,  # TODO: Extract from conversion result if available
            )
            if meta:
                chunk_dict["citation"] = {
                    "citekey": meta.citekey,
                    "title": meta.title,
                    "authors": meta.authors,
                    "year": meta.year,
                    "doi": meta.doi,
                    "url": meta.url,
                    "tags": meta.tags,
                    "collections": meta.collections,
                }
            else:
                warnings.append(f"Metadata not resolved for doc_id={doc_id}")
                logger.warning(
                    f"Metadata not resolved for doc_id={doc_id}",
                    extra={"correlation_id": correlation_id, "doc_id": doc_id},
                )
        except Exception as e:
            warning_msg = f"Metadata resolution failed for doc_id={doc_id}: {e}"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"correlation_id": correlation_id, "doc_id": doc_id})
        
        enriched.append(chunk_dict)
        texts.append(chunk_text)
    
    # Step 4: Generate embeddings
    try:
        model_id = request.embedding_model
        vectors = embedder.embed(texts, model_id=model_id)
        
        logger.info(
            f"Embeddings generated: {len(vectors)} vectors",
            extra={
                "correlation_id": correlation_id,
                "doc_id": doc_id,
                "embed_model": model_id,
                "vector_count": len(vectors),
            },
        )
    except Exception as e:
        error_msg = f"Embedding generation failed: {e}"
        logger.error(error_msg, extra={"correlation_id": correlation_id, "doc_id": doc_id}, exc_info=True)
        warnings.append(error_msg)
        raise
    
    # Step 5: Prepare items for storage
    to_store: list[dict[str, Any]] = []
    for enriched_item, vec in zip(enriched, vectors):
        store_item = {
            **enriched_item,
            "embedding": vec,
            "embed_model": model_id,
        }
        to_store.append(store_item)
    
    # Step 6: Upsert to vector index
    try:
        index.upsert(to_store, project_id=request.project_id, model_id=model_id)
        
        logger.info(
            f"Chunks upserted: {len(to_store)} chunks",
            extra={
                "correlation_id": correlation_id,
                "doc_id": doc_id,
                "project_id": request.project_id,
                "chunks_written": len(to_store),
            },
        )
    except Exception as e:
        error_msg = f"Vector index upsert failed: {e}"
        logger.error(
            error_msg,
            extra={"correlation_id": correlation_id, "doc_id": doc_id, "project_id": request.project_id},
            exc_info=True,
        )
        warnings.append(error_msg)
        raise
    
    # Step 7: Write audit log
    duration_seconds = time.time() - start_time
    
    if audit_dir:
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{correlation_id}.jsonl"
        
        audit_entry = {
            "correlation_id": correlation_id,
            "doc_id": doc_id,
            "project_id": request.project_id,
            "source_path": request.source_path,
            "chunks_written": len(to_store),
            "documents_processed": 1,
            "duration_seconds": round(duration_seconds, 3),
            "embed_model": model_id,
            "warnings": warnings,
            "timestamp": time.time(),
        }
        
        try:
            with audit_file.open("a") as f:
                f.write(json.dumps(audit_entry) + "\n")
            
            logger.info(
                f"Audit log written: {audit_file}",
                extra={"correlation_id": correlation_id, "audit_file": str(audit_file)},
            )
        except Exception as e:
            logger.warning(
                f"Failed to write audit log: {e}",
                extra={"correlation_id": correlation_id, "audit_file": str(audit_file)},
            )
    
    return IngestResult(
        chunks_written=len(to_store),
        documents_processed=1,
        duration_seconds=duration_seconds,
        embed_model=model_id,
        warnings=warnings,
    )
