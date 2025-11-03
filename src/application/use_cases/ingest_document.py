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
from ..ports.progress_reporter import DocumentProgressContext, ProgressReporterPort
from ..ports.fulltext_resolver import FulltextResolverPort, FulltextResult

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
    progress_reporter: ProgressReporterPort | None = None,
    document_index: int | None = None,
    total_documents: int | None = None,
    fulltext_resolver: FulltextResolverPort | None = None,
    attachment_key: str | None = None,
    prefer_zotero_fulltext: bool = True,
    item_key: str | None = None,
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
        progress_reporter: Optional progress reporter for stage-level progress updates
        document_index: Optional document index for progress display (1-based)
        total_documents: Optional total documents count for progress display
        fulltext_resolver: Optional FulltextResolverPort for Zotero fulltext reuse
        attachment_key: Optional Zotero attachment key for fulltext lookup
        prefer_zotero_fulltext: If True, prefer Zotero fulltext when available (default: True)
        item_key: Optional Zotero item key for traceability (T094)
    
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
    doc_progress: DocumentProgressContext | None = None
    
    # Initialize document-level progress if reporter provided
    source_path_obj = Path(request.source_path)
    if progress_reporter:
        document_name = source_path_obj.name if source_path_obj.is_file() else request.source_path
        doc_progress = progress_reporter.start_document(
            document_index=document_index or 1,
            total_documents=total_documents or 1,
            document_name=document_name,
        )
    
    # Step 1: Resolve metadata early to get language for OCR (before conversion)
    # Extract source hints from source path for metadata matching
    title_hint = source_path_obj.stem if source_path_obj.is_file() else None
    
    resolved_meta: CitationMeta | None = None
    ocr_languages: list[str] | None = None
    
    try:
        resolved_meta = resolver.resolve(
            citekey=None,  # Citekey not available before conversion
            doc_id="",  # Doc ID not available yet, will match by title/DOI
            source_hint=title_hint,
            zotero_config=request.zotero_config,
        )
        if resolved_meta:
            logger.info(
                f"Metadata resolved early: citekey={resolved_meta.citekey}, language={resolved_meta.language}",
                extra={"correlation_id": correlation_id, "citekey": resolved_meta.citekey, "language": resolved_meta.language},
            )
            # Extract language from metadata for OCR (already mapped by resolver)
            if resolved_meta.language:
                # Language is already mapped to OCR code (e.g., 'en', 'de') by resolver
                ocr_languages = [resolved_meta.language]
    except Exception as e:
        warning_msg = f"Early metadata resolution failed: {e}"
        warnings.append(warning_msg)
        logger.warning(warning_msg, extra={"correlation_id": correlation_id})
        resolved_meta = None
    
    # Step 2: Resolve fulltext or convert document
    source_path_obj = Path(request.source_path)
    fulltext_result: FulltextResult | None = None
    conversion: Mapping[str, Any] | None = None
    
    # Try fulltext resolver first if available and attachment_key provided
    if fulltext_resolver is not None and attachment_key is not None:
        if doc_progress:
            doc_progress.update_stage("resolving", "Resolving fulltext from Zotero")
        try:
            fulltext_result = fulltext_resolver.resolve_fulltext(
                attachment_key=attachment_key,
                file_path=source_path_obj,
                prefer_zotero=prefer_zotero_fulltext,
                min_length=100,
            )
            
            if fulltext_result.source in ("zotero", "mixed"):
                # Use fulltext - construct conversion_result-like structure
                # Compute doc_id similar to DoclingConverterAdapter
                import hashlib
                path_str = str(source_path_obj.resolve())
                path_hash = hashlib.sha256(path_str.encode("utf-8")).hexdigest()
                doc_id = f"path_{path_hash[:16]}"
                
                # Build minimal structure: empty heading_tree, simple page_map
                # The chunker can work with minimal structure
                page_map: dict[int, tuple[int, int]] = {}
                if fulltext_result.pages_from_zotero:
                    # Create page_map entries for Zotero pages
                    text = fulltext_result.text
                    # Estimate page boundaries (approximate, since Zotero doesn't provide offsets)
                    chars_per_page = len(text) // max(1, len(fulltext_result.pages_from_zotero))
                    current_offset = 0
                    for page_num in fulltext_result.pages_from_zotero:
                        start_offset = current_offset
                        end_offset = min(current_offset + chars_per_page, len(text))
                        page_map[page_num] = (start_offset, end_offset)
                        current_offset = end_offset
                elif fulltext_result.pages_from_docling:
                    # Similar estimation for Docling pages
                    text = fulltext_result.text
                    chars_per_page = len(text) // max(1, len(fulltext_result.pages_from_docling))
                    current_offset = 0
                    for page_num in fulltext_result.pages_from_docling:
                        start_offset = current_offset
                        end_offset = min(current_offset + chars_per_page, len(text))
                        page_map[page_num] = (start_offset, end_offset)
                        current_offset = end_offset
                else:
                    # No page information, treat as single page
                    page_map[1] = (0, len(fulltext_result.text))
                
                conversion = {
                    "doc_id": doc_id,
                    "structure": {
                        "heading_tree": {},  # Empty - chunker will work without headings
                        "page_map": page_map,
                    },
                    "plain_text": fulltext_result.text,
                    "fulltext_source": fulltext_result.source,
                    "fulltext_provenance": {
                        "pages_from_zotero": fulltext_result.pages_from_zotero,
                        "pages_from_docling": fulltext_result.pages_from_docling,
                        "zotero_quality_score": fulltext_result.zotero_quality_score,
                    },
                }
                
                logger.info(
                    f"Using fulltext from {fulltext_result.source} for {attachment_key}: doc_id={doc_id}",
                    extra={
                        "correlation_id": correlation_id,
                        "doc_id": doc_id,
                        "attachment_key": attachment_key,
                        "source": fulltext_result.source,
                        "zotero_pages": len(fulltext_result.pages_from_zotero),
                        "docling_pages": len(fulltext_result.pages_from_docling),
                    },
                )
        except Exception as e:
            warning_msg = f"Fulltext resolution failed: {e}, falling back to Docling conversion"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
            # Fall through to Docling conversion
    
    # If fulltext not used, convert via Docling
    if conversion is None:
        if doc_progress:
            doc_progress.update_stage("converting", "Converting document to text")
        try:
            conversion = converter.convert(
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
            if doc_progress:
                doc_progress.fail(error_msg)
            raise
    
    doc_id = conversion.get("doc_id", "unknown")
    
    # Step 3: Chunk document
    if doc_progress:
        doc_progress.update_stage("chunking", "Chunking document into segments")
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
        if doc_progress:
            doc_progress.fail(error_msg)
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
                doc_id=doc_id,
                source_hint=source_hint,
                zotero_config=request.zotero_config,
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
    if doc_progress:
        doc_progress.update_stage("embedding", f"Generating embeddings using {request.embedding_model}")
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
        if doc_progress:
            doc_progress.fail(error_msg)
        raise
    
    # Step 5: Prepare items for storage
    to_store: list[dict[str, Any]] = []
    for enriched_item, vec in zip(enriched, vectors):
        store_item = {
            **enriched_item,
            "embedding": vec,
            "embed_model": model_id,
        }
        # T094: Add zotero.item_key and zotero.attachment_key fields for traceability
        if item_key or attachment_key:
            store_item["zotero_item_key"] = item_key
            store_item["zotero_attachment_key"] = attachment_key
        to_store.append(store_item)
    
    # Step 6: Upsert to vector index
    if doc_progress:
        doc_progress.update_stage("storing", f"Storing {len(to_store)} chunks in vector index")
    upsert_errors: list[str] = []  # T039a: Capture errors during upsert
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
        upsert_errors.append(error_msg)  # T039a: Capture error for audit log
        logger.error(
            error_msg,
            extra={"correlation_id": correlation_id, "doc_id": doc_id, "project_id": request.project_id},
            exc_info=True,
        )
        warnings.append(error_msg)
        if doc_progress:
            doc_progress.fail(error_msg)
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
        
        # T102: Enhance audit logging to include dense_model and sparse_model IDs
        # T039a: Capture model IDs (dense and sparse) in audit log
        # Get sparse_model_id from collection metadata if available
        sparse_model_id = None
        try:
            # Try to get sparse_model_id from collection metadata
            # This is stored when collection is created with hybrid search enabled
            if hasattr(index, '_client') and index._client is not None:
                collection_name = f"proj-{request.project_id.replace('/', '-')}"
                try:
                    collection_info = index._client.get_collection(collection_name)
                    # Access metadata - structure varies by Qdrant version
                    metadata = {}
                    if hasattr(collection_info, 'config'):
                        if hasattr(collection_info.config, 'params'):
                            if hasattr(collection_info.config.params, 'metadata'):
                                metadata = collection_info.config.params.metadata or {}
                    elif hasattr(collection_info, 'metadata'):
                        metadata = collection_info.metadata or {}
                    
                    sparse_model_id = metadata.get("sparse_model_id")
                except Exception as e:
                    logger.debug(
                        f"Could not retrieve sparse_model_id from collection metadata: {e}",
                        extra={"collection_name": collection_name},
                    )
        except Exception as e:
            logger.debug(f"Error accessing collection metadata for sparse_model_id: {e}")
        
        # T102: dense_model is already captured as model_id, ensure it's included in audit log
        
        audit_entry = {
            "correlation_id": correlation_id,
            "doc_id": doc_id,
            "project_id": request.project_id,
            "source_path": request.source_path,
            "chunks_written": len(to_store),  # T039a: Collection write count
            "chunks_added": chunks_added,
            "chunks_updated": chunks_updated,
            "chunks_skipped": chunks_skipped,
            "chunks_filtered": chunks_filtered,  # T029a: Quality filter statistics (logged by chunker)
            "documents_processed": 1,
            "duration_seconds": round(duration_seconds, 3),
            "dense_model": model_id,  # T039a, T102: Dense embedding model ID
            "sparse_model": sparse_model_id,  # T039a, T102: Sparse model ID (optional, for hybrid search)
            "warnings": warnings,
            "errors": upsert_errors,  # T039a: Errors encountered during upsert operations
            "timestamp": time.time(),
        }
        
        # T053: Add fulltext provenance metadata to audit log
        if conversion is not None and "fulltext_provenance" in conversion:
            provenance = conversion["fulltext_provenance"]
            audit_entry["fulltext_source"] = conversion.get("fulltext_source", "docling")
            audit_entry["fulltext_provenance"] = {
                "pages_from_zotero": provenance.get("pages_from_zotero", []),
                "pages_from_docling": provenance.get("pages_from_docling", []),
                "zotero_quality_score": provenance.get("zotero_quality_score"),
                "total_pages_zotero": len(provenance.get("pages_from_zotero", [])),
                "total_pages_docling": len(provenance.get("pages_from_docling", [])),
            }
            if audit_entry["fulltext_provenance"]["total_pages_zotero"] > 0 or audit_entry["fulltext_provenance"]["total_pages_docling"] > 0:
                total_pages = audit_entry["fulltext_provenance"]["total_pages_zotero"] + audit_entry["fulltext_provenance"]["total_pages_docling"]
                if total_pages > 0:
                    audit_entry["fulltext_provenance"]["zotero_coverage"] = (
                        audit_entry["fulltext_provenance"]["total_pages_zotero"] / total_pages
                    )
        
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
    
    # Mark document processing as complete
    if doc_progress:
        doc_progress.finish()
    
    return IngestResult(
        chunks_written=len(to_store),
        documents_processed=1,
        duration_seconds=duration_seconds,
        embed_model=model_id,
        warnings=warnings,
    )
