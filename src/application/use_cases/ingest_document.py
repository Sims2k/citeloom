from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Mapping, Any, Sequence

from ...infrastructure.logging import get_correlation_id
from ...domain.models.citation_meta import CitationMeta
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
    
    # Step 1: Resolve metadata early to get language for OCR (before conversion)
    # Extract source hints from source path for metadata matching
    source_path_obj = Path(request.source_path)
    title_hint = source_path_obj.stem if source_path_obj.is_file() else None
    
    resolved_meta: CitationMeta | None = None
    ocr_languages: list[str] | None = None
    
    try:
        resolved_meta = resolver.resolve(
            citekey=None,  # Citekey not available before conversion
            references_path=request.references_path,
            doc_id="",  # Doc ID not available yet, will match by title/DOI
            source_hint=title_hint,
        )
        if resolved_meta:
            logger.info(
                f"Metadata resolved early: citekey={resolved_meta.citekey}, language={resolved_meta.language}",
                extra={"correlation_id": correlation_id, "citekey": resolved_meta.citekey, "language": resolved_meta.language},
            )
            # Extract language from metadata for OCR
            if resolved_meta.language:
                # Map Zotero language code to OCR language (e.g., 'en-US' → 'en')
                lang_code = resolved_meta.language.split('-')[0].lower()
                ocr_languages = [lang_code]
    except Exception as e:
        warning_msg = f"Early metadata resolution failed: {e}"
        warnings.append(warning_msg)
        logger.warning(warning_msg, extra={"correlation_id": correlation_id})
        resolved_meta = None
    
    # Step 2: Convert document with OCR language from metadata
    try:
        conversion: Mapping[str, Any] = converter.convert(
            request.source_path,
            ocr_languages=ocr_languages,
        )
        doc_id = conversion.get("doc_id", "unknown")
        logger.info(
            f"Document converted: doc_id={doc_id}",
            extra={"correlation_id": correlation_id, "doc_id": doc_id, "ocr_languages": ocr_languages},
        )
    except Exception as e:
        error_msg = f"Document conversion failed: {e}"
        logger.error(error_msg, extra={"correlation_id": correlation_id}, exc_info=True)
        warnings.append(error_msg)
        raise
    
    # Step 3: Chunk document
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
    
    # Metadata already resolved in Step 1, but verify we still have it
    # If not resolved early, try again with doc_id now available
    if not resolved_meta:
        # Try to extract DOI from conversion result structure if available
        doi_hint: str | None = None
        structure = conversion.get("structure", {})
        if isinstance(structure, dict):
            metadata = structure.get("metadata", {})
            if isinstance(metadata, dict):
                doi_hint = metadata.get("doi") or metadata.get("DOI")
        
        # Construct source hint: prefer DOI, fallback to title
        source_hint: str | None = None
        if doi_hint:
            source_hint = f"doi:{doi_hint}"
        elif title_hint:
            source_hint = title_hint
        
        try:
            resolved_meta = resolver.resolve(
                citekey=None,  # Citekey not available from conversion result
                references_path=request.references_path,
                doc_id=doc_id,
                source_hint=source_hint,
            )
            if resolved_meta:
                logger.info(
                    f"Metadata resolved for doc_id={doc_id}: {resolved_meta.citekey}",
                    extra={"correlation_id": correlation_id, "doc_id": doc_id, "citekey": resolved_meta.citekey},
                )
        except Exception as e:
            warning_msg = f"Metadata resolution failed for doc_id={doc_id}: {e}"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"correlation_id": correlation_id, "doc_id": doc_id})
            resolved_meta = None
        
        if not resolved_meta:
            warnings.append(f"Metadata not resolved for doc_id={doc_id}")
            logger.warning(
                f"Metadata not resolved for doc_id={doc_id}",
                extra={"correlation_id": correlation_id, "doc_id": doc_id},
            )
    
    # Step 5: Enrich chunks with metadata and prepare for embedding
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
        
        # Attach citation metadata to chunk (if resolved)
        if resolved_meta:
            chunk_dict["citation"] = {
                "citekey": resolved_meta.citekey,
                "title": resolved_meta.title,
                "authors": resolved_meta.authors,
                "year": resolved_meta.year,
                "doi": resolved_meta.doi,
                "url": resolved_meta.url,
                "tags": resolved_meta.tags,
                "collections": resolved_meta.collections,
            }
        enriched.append(chunk_dict)
        texts.append(chunk_text)
    
    # Step 6: Generate embeddings
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
    
    # Step 8: Write audit log (FR-018)
    duration_seconds = time.time() - start_time
    
    if audit_dir:
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{correlation_id}.jsonl"
        
        # Note: added/updated/skipped counts are tracked at collection level
        # For now, all chunks are "added" (upsert operation handles updates)
        # In future phases, we can track explicit added/updated/skipped counts
        chunks_added = len(to_store)
        chunks_updated = 0  # TODO: Track updates vs additions in future phases
        chunks_skipped = 0  # TODO: Track skipped chunks (e.g., duplicates) in future phases
        
        # T029a: Quality filtering statistics
        # Note: Quality filtering (min 50 tokens, SNR ≥ 0.3) is applied during chunking.
        # Filtered chunks are logged by DoclingHybridChunkerAdapter during chunking.
        # The chunks_written count reflects only chunks that passed quality filtering.
        # To get exact filtered count, check chunker logs for "Quality filtering: X chunks filtered out"
        chunks_filtered = None  # Could be enhanced to extract from chunker metadata
        
        audit_entry = {
            "correlation_id": correlation_id,
            "doc_id": doc_id,
            "project_id": request.project_id,
            "source_path": request.source_path,
            "chunks_written": len(to_store),
            "chunks_added": chunks_added,
            "chunks_updated": chunks_updated,
            "chunks_skipped": chunks_skipped,
            "chunks_filtered": chunks_filtered,  # T029a: Quality filter statistics (logged by chunker)
            "documents_processed": 1,
            "duration_seconds": round(duration_seconds, 3),
            "embed_model": model_id,  # Dense embedding model
            "warnings": warnings,
            "timestamp": time.time(),
        }
        
        try:
            with audit_file.open("a") as f:
                f.write(json.dumps(audit_entry) + "\n")
            
            logger.info(
                f"Audit log written: {audit_file}",
                extra={
                    "correlation_id": correlation_id,
                    "audit_file": str(audit_file),
                    "chunks_added": chunks_added,
                    "chunks_updated": chunks_updated,
                    "chunks_skipped": chunks_skipped,
                },
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
