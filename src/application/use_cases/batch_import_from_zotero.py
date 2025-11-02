"""Use case for batch importing documents from Zotero collections."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.checkpoint import DocumentCheckpoint, IngestionCheckpoint
from ...domain.models.download_manifest import (
    DownloadManifest,
    DownloadManifestAttachment,
    DownloadManifestItem,
)
from ..dto.ingest import IngestRequest, IngestResult
from ..ports.checkpoint_manager import CheckpointManagerPort
from ..ports.converter import TextConverterPort
from ..ports.chunker import ChunkerPort
from ..ports.embeddings import EmbeddingPort
from ..ports.metadata_resolver import MetadataResolverPort
from ..ports.progress_reporter import ProgressReporterPort
from ..ports.vector_index import VectorIndexPort
from ..ports.zotero_importer import ZoteroImporterPort
from ..use_cases.ingest_document import ingest_document

logger = logging.getLogger(__name__)


def batch_import_from_zotero(
    project_id: str,
    collection_key: str | None = None,
    collection_name: str | None = None,
    zotero_importer: ZoteroImporterPort | None = None,
    converter: TextConverterPort | None = None,
    chunker: ChunkerPort | None = None,
    resolver: MetadataResolverPort | None = None,
    embedder: EmbeddingPort | None = None,
    index: VectorIndexPort | None = None,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
    progress_reporter: ProgressReporterPort | None = None,
    checkpoint_manager: CheckpointManagerPort | None = None,
    resume: bool = False,
    correlation_id: str | None = None,
    zotero_config: dict[str, Any] | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    include_subcollections: bool = False,
    downloads_dir: Path | None = None,
    audit_dir: Path | None = None,
    checkpoints_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Orchestrate batch import of documents from Zotero collection.
    
    Two-phase workflow:
    1. Download all PDF attachments to persistent storage (var/zotero_downloads/{collection_key}/)
    2. Process downloaded files through conversion/chunking/embedding/storage pipeline
    
    Args:
        project_id: CiteLoom project identifier
        collection_key: Zotero collection key (preferred over collection_name)
        collection_name: Zotero collection name (requires lookup if collection_key not provided)
        zotero_importer: ZoteroImporterPort adapter for fetching collections/items/attachments
        converter: TextConverterPort for document conversion
        chunker: ChunkerPort for document chunking
        resolver: MetadataResolverPort for citation metadata resolution (reused for metadata extraction)
        embedder: EmbeddingPort for embedding generation
        index: VectorIndexPort for vector storage
        embedding_model: Embedding model ID (default: "BAAI/bge-small-en-v1.5")
        progress_reporter: Optional progress reporter for batch-level and document-level progress
        checkpoint_manager: Optional checkpoint manager for resumable processing
        resume: Whether to resume from existing checkpoint (loads checkpoint if exists)
        correlation_id: Optional correlation ID (generated if not provided, required for resume)
        zotero_config: Optional Zotero configuration dict
        include_tags: Optional list of tags to include (OR logic - any match selects item)
        exclude_tags: Optional list of tags to exclude (ANY-match logic - any exclude tag excludes item)
        include_subcollections: Whether to recursively include items from subcollections
        downloads_dir: Directory for downloaded attachments (default: var/zotero_downloads)
        audit_dir: Optional directory for audit JSONL logs
        checkpoints_dir: Directory for checkpoint files (default: var/checkpoints)
    
    Returns:
        Dict with:
            - correlation_id: Correlation ID for this import run
            - collection_key: Zotero collection key
            - collection_name: Zotero collection name
            - total_items: Total items processed
            - total_attachments: Total PDF attachments downloaded
            - total_documents: Total documents processed (each PDF attachment is a document)
            - chunks_written: Total chunks written to vector index
            - duration_seconds: Total duration
            - manifest_path: Path to download manifest JSON file
            - checkpoint_path: Path to checkpoint file (if checkpointing enabled)
            - warnings: List of warnings encountered
            - errors: List of errors encountered
    
    Raises:
        ValueError: If collection_key or collection_name not provided, or if required adapters missing
    """
    start_time = datetime.now()
    
    # Generate correlation ID at start for checkpoint file naming (FR-029)
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    logger.info(
        f"Starting batch import from Zotero collection",
        extra={
            "correlation_id": correlation_id,
            "project_id": project_id,
            "collection_key": collection_key,
            "collection_name": collection_name,
        },
    )
    
    # Validate required adapters
    if not zotero_importer:
        raise ValueError("zotero_importer adapter required")
    if not converter:
        raise ValueError("converter adapter required")
    if not chunker:
        raise ValueError("chunker adapter required")
    if not resolver:
        raise ValueError("resolver adapter required")
    if not embedder:
        raise ValueError("embedder adapter required")
    if not index:
        raise ValueError("index adapter required")
    
    # Resolve collection key if name provided
    if collection_name and not collection_key:
        collection_info = zotero_importer.find_collection_by_name(collection_name)
        if not collection_info:
            raise ValueError(f"Collection '{collection_name}' not found")
        collection_key = collection_info.get("key")
        collection_name = collection_info.get("name", collection_name)
    
    if not collection_key:
        raise ValueError("collection_key or collection_name required")
    
    # Get collection name if not provided
    if not collection_name:
        collections = zotero_importer.list_collections()
        for coll in collections:
            if coll.get("key") == collection_key:
                collection_name = coll.get("name", f"Collection {collection_key}")
                break
        if not collection_name:
            collection_name = f"Collection {collection_key}"
    
    # Set up downloads directory
    if downloads_dir is None:
        downloads_dir = Path("var/zotero_downloads")
    
    collection_downloads_dir = downloads_dir / collection_key
    collection_downloads_dir.mkdir(parents=True, exist_ok=True)
    
    warnings: list[str] = []
    errors: list[str] = []
    
    # Check for existing download manifest (T089: detect existing downloads and skip download phase)
    manifest_path = collection_downloads_dir / "manifest.json"
    download_manifest: DownloadManifest | None = None
    skip_download_phase = False
    
    if manifest_path.exists():
        try:
            with manifest_path.open("r") as f:
                manifest_data = json.load(f)
                download_manifest = DownloadManifest.from_dict(manifest_data)
            
            # Verify all files from manifest exist
            all_files_exist = True
            missing_files: list[str] = []
            for item in download_manifest.get_successful_downloads():
                for attachment in item.get_pdf_attachments():
                    if attachment.download_status == "success":
                        file_path = attachment.local_path
                        if not file_path.exists():
                            all_files_exist = False
                            missing_files.append(str(file_path))
            
            if all_files_exist:
                skip_download_phase = True
                logger.info(
                    f"Found existing download manifest with {len(download_manifest.get_successful_downloads())} items. "
                    f"All files exist, skipping download phase.",
                    extra={"correlation_id": correlation_id, "manifest_path": str(manifest_path)},
                )
            else:
                logger.warning(
                    f"Found existing download manifest but some files are missing ({len(missing_files)} files). "
                    f"Will re-download.",
                    extra={
                        "correlation_id": correlation_id,
                        "manifest_path": str(manifest_path),
                        "missing_files_count": len(missing_files),
                    },
                )
                download_manifest = None  # Reset to force re-download
        except Exception as e:
            logger.warning(
                f"Failed to load existing manifest: {e}. Will re-download.",
                extra={"correlation_id": correlation_id, "manifest_path": str(manifest_path)},
                exc_info=True,
            )
            download_manifest = None
    
    # Initialize checkpoint manager and load checkpoint if resuming
    checkpoint: IngestionCheckpoint | None = None
    checkpoint_path: Path | None = None
    
    if checkpoint_manager:
        checkpoint_path = checkpoint_manager.get_checkpoint_path(correlation_id)
        
        if resume:
            # Try to load existing checkpoint
            try:
                checkpoint = checkpoint_manager.load_checkpoint(correlation_id=correlation_id)
                
                if checkpoint:
                    # Validate checkpoint before resuming
                    if not checkpoint_manager.validate_checkpoint(checkpoint):
                        warning_msg = "Checkpoint file is invalid or corrupted. Starting fresh import."
                        warnings.append(warning_msg)
                        logger.warning(
                            warning_msg,
                            extra={"correlation_id": correlation_id, "checkpoint_path": str(checkpoint_path)},
                        )
                        checkpoint = None
                    else:
                        # Verify checkpoint matches current import context
                        if checkpoint.project_id != project_id:
                            warning_msg = (
                                f"Checkpoint project_id mismatch: expected '{project_id}', "
                                f"got '{checkpoint.project_id}'. Starting fresh import."
                            )
                            warnings.append(warning_msg)
                            logger.warning(warning_msg, extra={"correlation_id": correlation_id})
                            checkpoint = None
                        elif checkpoint.collection_key != collection_key:
                            warning_msg = (
                                f"Checkpoint collection_key mismatch: expected '{collection_key}', "
                                f"got '{checkpoint.collection_key}'. Starting fresh import."
                            )
                            warnings.append(warning_msg)
                            logger.warning(warning_msg, extra={"correlation_id": correlation_id})
                            checkpoint = None
                        else:
                            logger.info(
                                f"Resuming from checkpoint: {len(checkpoint.get_completed_documents())} "
                                f"documents completed, {len(checkpoint.get_incomplete_documents())} remaining",
                                extra={
                                    "correlation_id": correlation_id,
                                    "completed": len(checkpoint.get_completed_documents()),
                                    "incomplete": len(checkpoint.get_incomplete_documents()),
                                },
                            )
                else:
                    logger.info(
                        "No checkpoint found for resume, starting fresh import",
                        extra={"correlation_id": correlation_id},
                    )
            except Exception as e:
                warning_msg = f"Failed to load checkpoint: {e}. Starting fresh import."
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                checkpoint = None
        
        # Create new checkpoint if not resuming or checkpoint invalid
        if checkpoint is None:
            checkpoint = IngestionCheckpoint(
                correlation_id=correlation_id,
                project_id=project_id,
                collection_key=collection_key,
                start_time=start_time,
            )
    
    # Phase 1: Download all attachments (skip if manifest exists and files are present)
    total_attachments = 0
    
    if not skip_download_phase:
        logger.info(
            f"Phase 1: Downloading attachments from collection '{collection_name}'",
            extra={"correlation_id": correlation_id, "collection_key": collection_key},
        )
        
        download_manifest = DownloadManifest(
            collection_key=collection_key,
            collection_name=collection_name,
            download_time=datetime.now(),
        )
        
        # Fetch items from collection
        items_to_process: list[dict[str, Any]] = []
        try:
            items_iterator = zotero_importer.get_collection_items(
                collection_key=collection_key,
                include_subcollections=include_subcollections,
            )
            items_to_process = list(items_iterator)
            
            # Check for empty collections
            if not items_to_process:
                error_msg = f"Collection '{collection_name}' is empty (no items found)"
                logger.warning(error_msg, extra={"correlation_id": correlation_id, "collection_key": collection_key})
                warnings.append(error_msg)
                return {
                    "correlation_id": correlation_id,
                    "collection_key": collection_key,
                    "collection_name": collection_name,
                    "total_items": 0,
                    "total_attachments": 0,
                    "total_documents": 0,
                    "chunks_written": 0,
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "manifest_path": None,
                    "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
                    "warnings": warnings,
                    "errors": errors,
                }
            
            logger.info(
                f"Found {len(items_to_process)} items in collection",
                extra={"correlation_id": correlation_id, "item_count": len(items_to_process)},
            )
        except Exception as e:
            # Enhanced error handling for network interruptions and API failures
            error_type = type(e).__name__
            error_msg_base = f"Failed to fetch collection items from '{collection_name}': {e}"
            
            # Detect network-related errors
            if "Connection" in error_type or "timeout" in str(e).lower() or "network" in str(e).lower():
                error_msg = f"{error_msg_base} (network interruption detected). Please check your internet connection and try again."
            elif "401" in str(e) or "Unauthorized" in str(e):
                error_msg = f"{error_msg_base} (authentication failed). Please verify your Zotero API key and library ID."
            elif "404" in str(e) or "Not Found" in str(e):
                error_msg = f"{error_msg_base} (collection not found). Please verify the collection name or key is correct."
            elif "429" in str(e) or "rate limit" in str(e).lower():
                error_msg = f"{error_msg_base} (rate limit exceeded). Please wait a few moments and try again."
            else:
                error_msg = error_msg_base
            
            logger.error(error_msg, extra={"correlation_id": correlation_id}, exc_info=True)
            errors.append(error_msg)
            raise
        
        # Filter items by tags if specified
        if include_tags or exclude_tags:
            filtered_items: list[dict[str, Any]] = []
            for item in items_to_process:
                item_data = item.get("data", {})
                
                # Extract tags from item
                item_tags: list[str] = []
                tag_list = item_data.get("tags", [])
                if isinstance(tag_list, list):
                    for tag_obj in tag_list:
                        if isinstance(tag_obj, dict) and "tag" in tag_obj:
                            item_tags.append(tag_obj["tag"])
                        elif isinstance(tag_obj, str):
                            item_tags.append(tag_obj)
                
                # Apply tag filtering: case-insensitive partial matching
                if _matches_tag_filter(item_tags, include_tags, exclude_tags):
                    filtered_items.append(item)
            
            logger.info(
                f"Tag filtering: {len(filtered_items)} items match criteria (from {len(items_to_process)} total)",
                extra={
                    "correlation_id": correlation_id,
                    "include_tags": include_tags,
                    "exclude_tags": exclude_tags,
                    "filtered_count": len(filtered_items),
                    "total_count": len(items_to_process),
                },
            )
            items_to_process = filtered_items
            
            if not items_to_process:
                warning_msg = "No items match tag filter criteria"
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id})
                return {
                    "correlation_id": correlation_id,
                    "collection_key": collection_key,
                    "collection_name": collection_name,
                    "total_items": 0,
                    "total_attachments": 0,
                    "total_documents": 0,
                    "chunks_written": 0,
                    "duration_seconds": (datetime.now() - start_time).total_seconds(),
                    "manifest_path": None,
                    "warnings": warnings,
                    "errors": errors,
                }
        
        # Download attachments for each item (10-20 files per batch)
        BATCH_SIZE = 15  # 10-20 files per batch
        batch_attachment_count = 0
        
        for item_idx, item in enumerate(items_to_process):
            item_key = item.get("key", "")
            item_data = item.get("data", {})
            item_title = item_data.get("title", "Untitled")
            
            if not item_key:
                warning_msg = f"Skipping item {item_idx + 1}: missing item key"
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id, "item_index": item_idx + 1})
                continue
            
            # Get metadata for this item
            try:
                item_metadata = zotero_importer.get_item_metadata(item_key)
            except Exception as e:
                warning_msg = f"Failed to get metadata for item {item_key}: {e}"
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id, "item_key": item_key})
                item_metadata = {}
            
            # Get PDF attachments for this item
            try:
                attachments = zotero_importer.get_item_attachments(item_key)
            except Exception as e:
                warning_msg = f"Failed to get attachments for item {item_key}: {e}"
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id, "item_key": item_key})
                continue
            
            # Filter PDF attachments only
            pdf_attachments = [
                att for att in attachments
                if att.get("data", {}).get("contentType") == "application/pdf"
                or att.get("data", {}).get("filename", "").endswith(".pdf")
            ]
            
            if not pdf_attachments:
                logger.debug(
                    f"Item {item_key} has no PDF attachments, skipping",
                    extra={"correlation_id": correlation_id, "item_key": item_key, "title": item_title},
                )
                continue
            
            # Create manifest item
            manifest_item = DownloadManifestItem(
                item_key=item_key,
                title=item_title,
                metadata=item_metadata,
            )
            
            # Download each PDF attachment
            for att in pdf_attachments:
                attachment_key = att.get("key", "")
                attachment_data = att.get("data", {})
                filename = attachment_data.get("filename", f"{attachment_key}.pdf")
                
                if not attachment_key:
                    continue
                
                # Generate safe filename
                safe_filename = _sanitize_filename(filename)
                if not safe_filename.endswith(".pdf"):
                    safe_filename += ".pdf"
                
                output_path = collection_downloads_dir / safe_filename
                
                # Ensure unique filename (if file exists, append counter)
                counter = 1
                original_output_path = output_path
                while output_path.exists():
                    stem = original_output_path.stem
                    output_path = collection_downloads_dir / f"{stem}_{counter}.pdf"
                    counter += 1
                
                # Download attachment
                try:
                    downloaded_path = zotero_importer.download_attachment(
                        item_key=item_key,
                        attachment_key=attachment_key,
                        output_path=output_path,
                    )
                    
                    file_size = downloaded_path.stat().st_size if downloaded_path.exists() else None
                    
                    manifest_attachment = DownloadManifestAttachment(
                        attachment_key=attachment_key,
                        filename=filename,
                        local_path=downloaded_path.resolve(),  # Ensure absolute path
                        download_status="success",
                        file_size=file_size,
                    )
                    
                    total_attachments += 1
                    batch_attachment_count += 1
                    
                    logger.debug(
                        f"Downloaded attachment: {downloaded_path}",
                        extra={
                            "correlation_id": correlation_id,
                            "item_key": item_key,
                            "attachment_key": attachment_key,
                            "output_path": str(downloaded_path),
                        },
                    )
                    
                except Exception as e:
                    error_msg = f"Failed to download attachment {attachment_key} for item {item_key}: {e}"
                    errors.append(error_msg)
                    logger.error(error_msg, extra={"correlation_id": correlation_id, "item_key": item_key}, exc_info=True)
                    
                    manifest_attachment = DownloadManifestAttachment(
                        attachment_key=attachment_key,
                        filename=filename,
                        local_path=output_path.resolve(),
                        download_status="failed",
                        error=str(e),
                    )
                
                manifest_item.add_attachment(manifest_attachment)
            
            # Add item to manifest (only if it has attachments)
            if manifest_item.attachments:
                download_manifest.add_item(manifest_item)
            
            # Batch progress logging (every 10-20 files)
            if batch_attachment_count >= BATCH_SIZE:
                logger.info(
                    f"Downloaded batch: {batch_attachment_count} attachments so far",
                    extra={"correlation_id": correlation_id, "total_attachments": total_attachments},
                )
                batch_attachment_count = 0
        
        # Save download manifest after all downloads complete
        manifest_path = collection_downloads_dir / "manifest.json"
        try:
            with manifest_path.open("w") as f:
                json.dump(download_manifest.to_dict(), f, indent=2)
            
            logger.info(
                f"Download manifest saved: {manifest_path}",
                extra={"correlation_id": correlation_id, "manifest_path": str(manifest_path)},
            )
        except Exception as e:
            error_msg = f"Failed to save download manifest: {e}"
            errors.append(error_msg)
            logger.error(error_msg, extra={"correlation_id": correlation_id}, exc_info=True)
    else:
        # Use existing manifest - count total attachments
        if download_manifest:
            for item in download_manifest.get_successful_downloads():
                total_attachments += len(item.get_pdf_attachments())
        
        logger.info(
            f"Using existing download manifest: {total_attachments} attachments ready",
            extra={"correlation_id": correlation_id, "manifest_path": str(manifest_path)},
        )
    
    # Phase 2: Process downloaded files
    logger.info(
        f"Phase 2: Processing {total_attachments} downloaded documents",
        extra={"correlation_id": correlation_id, "total_attachments": total_attachments},
    )
    
    # Initialize batch progress if reporter provided
    batch_progress = None
    if progress_reporter:
        batch_progress = progress_reporter.start_batch(
            total_documents=total_attachments,
            description=f"Processing documents from {collection_name}",
        )
    
    total_chunks = 0
    total_documents_processed = 0
    document_index = 0
    
    # Track completed document paths from checkpoint for skipping
    completed_paths: set[str] = set()
    if checkpoint:
        for doc in checkpoint.get_completed_documents():
            completed_paths.add(doc.path)
    
    # Track chunks written for batch checkpoint saving (100-500 points per batch)
    chunks_since_last_checkpoint = 0
    CHECKPOINT_BATCH_SIZE = 300  # Save checkpoint every 300 chunks (between 100-500)
    
    # Process each successful download from manifest
    for item in download_manifest.get_successful_downloads():
        item_key = item.item_key
        item_metadata = item.metadata
        
        # Process all PDF attachments from this item as separate documents (FR-028)
        for attachment in item.get_pdf_attachments():
            if attachment.download_status != "success":
                continue
            
            file_path = attachment.local_path
            file_path_str = str(file_path.resolve())  # Use absolute path for checkpoint matching
            
            # Check if file exists
            if not file_path.exists():
                warning_msg = f"Downloaded file not found: {file_path}"
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id, "file_path": str(file_path)})
                continue
            
            # Skip if already completed (resume logic)
            if file_path_str in completed_paths:
                logger.debug(
                    f"Skipping completed document: {file_path.name}",
                    extra={"correlation_id": correlation_id, "file_path": str(file_path)},
                )
                # Still count it in total_documents_processed for progress tracking
                if checkpoint:
                    # Find document checkpoint to get chunk count
                    for doc in checkpoint.documents:
                        if doc.path == file_path_str and doc.status == "completed":
                            total_chunks += doc.chunks_count
                            total_documents_processed += 1
                            if batch_progress:
                                batch_progress.update(total_documents_processed)
                            break
                document_index += 1
                continue
            
            # Create document checkpoint for tracking
            doc_checkpoint = DocumentCheckpoint(
                path=file_path_str,
                status="pending",
                zotero_item_key=item_key,
                zotero_attachment_key=attachment.attachment_key,
            )
            
            # Update checkpoint with pending document
            if checkpoint:
                checkpoint.add_document_checkpoint(doc_checkpoint)
            
            # Create ingest request
            ingest_request = IngestRequest(
                source_path=str(file_path),
                project_id=project_id,
                zotero_config=zotero_config,
                embedding_model=embedding_model,
            )
            
            # Use existing ZoteroPyzoteroResolver for metadata extraction (reuse existing resolver)
            # Note: The resolver will attempt to match by file path/title, but we can also
            # provide Zotero metadata via zotero_config or enhance the resolver to accept
            # pre-extracted metadata. For now, resolver will do its best to match.
            
            document_index += 1
            
            try:
                # Update checkpoint: marking as converting
                if checkpoint:
                    doc_checkpoint.mark_stage("converting")
                    checkpoint.add_document_checkpoint(doc_checkpoint)
                    # Save checkpoint after stage update (handles file disappearance)
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                    except Exception as e:
                        warning_msg = f"Failed to save checkpoint after stage update: {e}"
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                
                # Process document through ingest pipeline
                result: IngestResult = ingest_document(
                    request=ingest_request,
                    converter=converter,
                    chunker=chunker,
                    resolver=resolver,
                    embedder=embedder,
                    index=index,
                    audit_dir=audit_dir,
                    correlation_id=correlation_id,
                    progress_reporter=progress_reporter,
                    document_index=document_index,
                    total_documents=total_attachments,
                )
                
                total_chunks += result.chunks_written
                chunks_since_last_checkpoint += result.chunks_written
                total_documents_processed += result.documents_processed
                
                # Update checkpoint: mark as completed
                if checkpoint:
                    doc_checkpoint.mark_completed(
                        chunks_count=result.chunks_written,
                        doc_id=result.doc_id if hasattr(result, "doc_id") else f"doc_{correlation_id}_{document_index}",
                    )
                    checkpoint.add_document_checkpoint(doc_checkpoint)
                
                if batch_progress:
                    batch_progress.update(total_documents_processed)
                
                logger.info(
                    f"Processed document: {file_path.name} ({result.chunks_written} chunks)",
                    extra={
                        "correlation_id": correlation_id,
                        "file_path": str(file_path),
                        "chunks_written": result.chunks_written,
                    },
                )
                
                # Save checkpoint after each document completes (enables fine-grained resume)
                if checkpoint and checkpoint_manager:
                    try:
                        # Check for concurrent import processes (T099)
                        # If checkpoint file exists but was modified recently by another process, warn user
                        if checkpoint_path.exists():
                            import os
                            file_stat = checkpoint_path.stat()
                            # If file was modified in the last 5 seconds, might be another process
                            import time
                            time_since_mod = time.time() - file_stat.st_mtime
                            if 0 < time_since_mod < 5:
                                warning_msg = (
                                    f"Warning: Checkpoint file was recently modified. "
                                    f"Another import process may be running. "
                                    f"Concurrent imports can cause checkpoint corruption. "
                                    f"Please ensure only one import process runs at a time."
                                )
                                warnings.append(warning_msg)
                                logger.warning(
                                    warning_msg,
                                    extra={
                                        "correlation_id": correlation_id,
                                        "checkpoint_path": str(checkpoint_path),
                                        "time_since_mod": time_since_mod,
                                    },
                                )
                        
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                    except Exception as e:
                        warning_msg = f"Failed to save checkpoint after document: {e}"
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                        # Try to recreate checkpoint if file disappeared (T098)
                        try:
                            # Check if file still exists
                            if not checkpoint_path.exists():
                                logger.warning(
                                    "Checkpoint file disappeared, recreating",
                                    extra={"correlation_id": correlation_id, "checkpoint_path": str(checkpoint_path)},
                                )
                                # Ensure directory exists before recreating
                                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                                checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                        except Exception:
                            pass  # Ignore errors on recreate attempt
                
                # Save checkpoint after batch upsert (every 100-500 points)
                if checkpoint and checkpoint_manager and chunks_since_last_checkpoint >= CHECKPOINT_BATCH_SIZE:
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                        chunks_since_last_checkpoint = 0
                        logger.debug(
                            f"Checkpoint saved after batch upsert ({CHECKPOINT_BATCH_SIZE} chunks)",
                            extra={"correlation_id": correlation_id},
                        )
                    except Exception as e:
                        warning_msg = f"Failed to save checkpoint after batch upsert: {e}"
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                
            except Exception as e:
                # Enhanced error handling for corrupted PDFs and processing errors
                error_type = type(e).__name__
                error_str = str(e).lower()
                
                # Detect corrupted PDF errors
                if "corrupt" in error_str or "invalid" in error_str or "cannot read" in error_str or "pdf" in error_type.lower():
                    error_msg = f"Failed to process document {file_path.name}: Corrupted or invalid PDF file ({e})"
                elif "timeout" in error_str:
                    error_msg = f"Failed to process document {file_path.name}: Processing timeout ({e})"
                elif "memory" in error_str or "MemoryError" in error_type:
                    error_msg = f"Failed to process document {file_path.name}: Insufficient memory ({e})"
                else:
                    error_msg = f"Failed to process document {file_path.name}: {e}"
                
                errors.append(error_msg)
                logger.error(error_msg, extra={"correlation_id": correlation_id, "file_path": str(file_path)}, exc_info=True)
                
                # Update checkpoint: mark as failed
                if checkpoint:
                    doc_checkpoint.mark_failed(error=error_msg)
                    checkpoint.add_document_checkpoint(doc_checkpoint)
                    # Save checkpoint even on failure (with enhanced error handling)
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                    except Exception as checkpoint_err:
                        # Handle checkpoint file deletion/movement during processing (T098)
                        checkpoint_err_str = str(checkpoint_err).lower()
                        if "no such file" in checkpoint_err_str or "not found" in checkpoint_err_str or "permission" in checkpoint_err_str:
                            # Checkpoint file may have been deleted or moved
                            logger.warning(
                                f"Checkpoint file may have been deleted or moved during processing. Attempting to recreate.",
                                extra={
                                    "correlation_id": correlation_id,
                                    "checkpoint_path": str(checkpoint_path),
                                    "error": str(checkpoint_err),
                                },
                            )
                            # Try to recreate checkpoint directory and file
                            try:
                                checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
                                checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                            except Exception as recreate_err:
                                logger.error(
                                    f"Failed to recreate checkpoint after file deletion/movement: {recreate_err}",
                                    extra={"correlation_id": correlation_id},
                                    exc_info=True,
                                )
                        else:
                            logger.warning(
                                f"Failed to save checkpoint after document failure: {checkpoint_err}",
                                extra={"correlation_id": correlation_id},
                                exc_info=True,
                            )
                continue
    
    # Finish batch progress
    if batch_progress:
        batch_progress.finish()
    
    duration_seconds = (datetime.now() - start_time).total_seconds()
    
    # Display final summary using progress reporter if available
    if progress_reporter and hasattr(progress_reporter, "display_summary"):
        progress_reporter.display_summary(
            total_documents=total_documents_processed,
            chunks_created=total_chunks,
            duration_seconds=duration_seconds,
            warnings=warnings,
            errors=errors,
        )
    
    # Clean up progress reporter if it has cleanup method
    if progress_reporter and hasattr(progress_reporter, "cleanup"):
        progress_reporter.cleanup()
    
    logger.info(
        f"Batch import completed: {total_documents_processed} documents, {total_chunks} chunks",
        extra={
            "correlation_id": correlation_id,
            "total_documents": total_documents_processed,
            "chunks_written": total_chunks,
            "duration_seconds": duration_seconds,
        },
    )
    
    return {
        "correlation_id": correlation_id,
        "collection_key": collection_key,
        "collection_name": collection_name,
        "total_items": len(items_to_process),
        "total_attachments": total_attachments,
        "total_documents": total_documents_processed,
        "chunks_written": total_chunks,
        "duration_seconds": duration_seconds,
        "manifest_path": str(manifest_path),
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        "warnings": warnings,
        "errors": errors,
    }


def _matches_tag_filter(
    item_tags: list[str],
    include_tags: list[str] | None,
    exclude_tags: list[str] | None,
) -> bool:
    """
    Check if item matches tag filter criteria.
    
    Args:
        item_tags: List of tags on the item
        include_tags: List of tags to include (OR logic - any match selects item)
        exclude_tags: List of tags to exclude (ANY-match logic - any exclude tag excludes item)
    
    Returns:
        True if item matches filter criteria, False otherwise
    """
    # Case-insensitive partial matching
    item_tags_lower = [tag.lower() for tag in item_tags]
    
    # Include tags: OR logic (any match selects item)
    if include_tags:
        include_match = False
        for include_tag in include_tags:
            include_tag_lower = include_tag.lower()
            if any(include_tag_lower in item_tag for item_tag in item_tags_lower):
                include_match = True
                break
        if not include_match:
            return False
    
    # Exclude tags: ANY-match logic (any exclude tag excludes item)
    if exclude_tags:
        for exclude_tag in exclude_tags:
            exclude_tag_lower = exclude_tag.lower()
            if any(exclude_tag_lower in item_tag for item_tag in item_tags_lower):
                return False
    
    return True


def download_zotero_collection(
    collection_key: str | None = None,
    collection_name: str | None = None,
    zotero_importer: ZoteroImporterPort | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    include_subcollections: bool = False,
    downloads_dir: Path | None = None,
    zotero_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Download all PDF attachments from a Zotero collection without processing them.
    
    Creates a download manifest for later processing via process_downloaded_files.
    
    Args:
        collection_key: Zotero collection key (preferred over collection_name)
        collection_name: Zotero collection name (requires lookup if collection_key not provided)
        zotero_importer: ZoteroImporterPort adapter for fetching collections/items/attachments
        include_tags: Optional list of tags to include (OR logic - any match selects item)
        exclude_tags: Optional list of tags to exclude (ANY-match logic - any exclude tag excludes item)
        include_subcollections: Whether to recursively include items from subcollections
        downloads_dir: Directory for downloaded attachments (default: var/zotero_downloads)
        zotero_config: Optional Zotero configuration dict
    
    Returns:
        Dict with:
            - collection_key: Zotero collection key
            - collection_name: Zotero collection name
            - total_items: Total items processed
            - total_attachments: Total PDF attachments downloaded
            - manifest_path: Path to download manifest JSON file
            - warnings: List of warnings encountered
            - errors: List of errors encountered
    
    Raises:
        ValueError: If collection_key or collection_name not provided, or if zotero_importer missing
    """
    from datetime import datetime
    
    start_time = datetime.now()
    
    if not zotero_importer:
        raise ValueError("zotero_importer adapter required")
    
    # Resolve collection key if name provided
    if collection_name and not collection_key:
        collection_info = zotero_importer.find_collection_by_name(collection_name)
        if not collection_info:
            raise ValueError(f"Collection '{collection_name}' not found")
        collection_key = collection_info.get("key")
        collection_name = collection_info.get("name", collection_name)
    
    if not collection_key:
        raise ValueError("collection_key or collection_name required")
    
    # Get collection name if not provided
    if not collection_name:
        collections = zotero_importer.list_collections()
        for coll in collections:
            if coll.get("key") == collection_key:
                collection_name = coll.get("name", f"Collection {collection_key}")
                break
        if not collection_name:
            collection_name = f"Collection {collection_key}"
    
    # Set up downloads directory
    if downloads_dir is None:
        downloads_dir = Path("var/zotero_downloads")
    
    collection_downloads_dir = downloads_dir / collection_key
    collection_downloads_dir.mkdir(parents=True, exist_ok=True)
    
    warnings: list[str] = []
    errors: list[str] = []
    
    # Check for existing manifest and skip if all files exist
    manifest_path = collection_downloads_dir / "manifest.json"
    download_manifest: DownloadManifest | None = None
    
    if manifest_path.exists():
        try:
            with manifest_path.open("r") as f:
                manifest_data = json.load(f)
                download_manifest = DownloadManifest.from_dict(manifest_data)
            
            # Verify all files from manifest exist
            all_files_exist = True
            for item in download_manifest.get_successful_downloads():
                for attachment in item.get_pdf_attachments():
                    if attachment.download_status == "success":
                        if not attachment.local_path.exists():
                            all_files_exist = False
                            break
                if not all_files_exist:
                    break
            
            if all_files_exist:
                # Count attachments
                total_attachments = sum(
                    len(item.get_pdf_attachments())
                    for item in download_manifest.get_successful_downloads()
                )
                logger.info(
                    f"Found existing download manifest with {len(download_manifest.get_successful_downloads())} items. "
                    f"All {total_attachments} files exist, skipping download.",
                    extra={"collection_key": collection_key, "manifest_path": str(manifest_path)},
                )
                return {
                    "collection_key": collection_key,
                    "collection_name": collection_name,
                    "total_items": len(download_manifest.items),
                    "total_attachments": total_attachments,
                    "manifest_path": str(manifest_path),
                    "warnings": warnings,
                    "errors": errors,
                }
        except Exception as e:
            logger.warning(
                f"Failed to load existing manifest: {e}. Will re-download.",
                extra={"collection_key": collection_key, "manifest_path": str(manifest_path)},
                exc_info=True,
            )
            download_manifest = None
    
    # Create new manifest
    download_manifest = DownloadManifest(
        collection_key=collection_key,
        collection_name=collection_name,
        download_time=datetime.now(),
    )
    
    # Fetch items from collection
    items_to_process: list[dict[str, Any]] = []
    try:
        items_iterator = zotero_importer.get_collection_items(
            collection_key=collection_key,
            include_subcollections=include_subcollections,
        )
        items_to_process = list(items_iterator)
        
        logger.info(
            f"Found {len(items_to_process)} items in collection",
            extra={"collection_key": collection_key, "item_count": len(items_to_process)},
        )
    except Exception as e:
        error_msg = f"Failed to fetch collection items: {e}"
        logger.error(error_msg, extra={"collection_key": collection_key}, exc_info=True)
        errors.append(error_msg)
        raise
    
    # Filter items by tags if specified
    if include_tags or exclude_tags:
        filtered_items: list[dict[str, Any]] = []
        for item in items_to_process:
            item_data = item.get("data", {})
            
            # Extract tags from item
            item_tags: list[str] = []
            tag_list = item_data.get("tags", [])
            if isinstance(tag_list, list):
                for tag_obj in tag_list:
                    if isinstance(tag_obj, dict) and "tag" in tag_obj:
                        item_tags.append(tag_obj["tag"])
                    elif isinstance(tag_obj, str):
                        item_tags.append(tag_obj)
            
            # Apply tag filtering
            if _matches_tag_filter(item_tags, include_tags, exclude_tags):
                filtered_items.append(item)
        
        logger.info(
            f"Tag filtering: {len(filtered_items)} items match criteria (from {len(items_to_process)} total)",
            extra={
                "collection_key": collection_key,
                "include_tags": include_tags,
                "exclude_tags": exclude_tags,
                "filtered_count": len(filtered_items),
                "total_count": len(items_to_process),
            },
        )
        items_to_process = filtered_items
        
        if not items_to_process:
            warning_msg = "No items match tag filter criteria"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"collection_key": collection_key})
            return {
                "collection_key": collection_key,
                "collection_name": collection_name,
                "total_items": 0,
                "total_attachments": 0,
                "manifest_path": None,
                "warnings": warnings,
                "errors": errors,
            }
    
    # Download attachments for each item
    BATCH_SIZE = 15
    total_attachments = 0
    batch_attachment_count = 0
    
    for item_idx, item in enumerate(items_to_process):
        item_key = item.get("key", "")
        item_data = item.get("data", {})
        item_title = item_data.get("title", "Untitled")
        
        if not item_key:
            warning_msg = f"Skipping item {item_idx + 1}: missing item key"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"collection_key": collection_key, "item_index": item_idx + 1})
            continue
        
        # Get metadata for this item
        try:
            item_metadata = zotero_importer.get_item_metadata(item_key)
        except Exception as e:
            warning_msg = f"Failed to get metadata for item {item_key}: {e}"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"collection_key": collection_key, "item_key": item_key})
            item_metadata = {}
        
        # Get PDF attachments for this item
        try:
            attachments = zotero_importer.get_item_attachments(item_key)
        except Exception as e:
            warning_msg = f"Failed to get attachments for item {item_key}: {e}"
            warnings.append(warning_msg)
            logger.warning(warning_msg, extra={"collection_key": collection_key, "item_key": item_key})
            continue
        
        # Filter PDF attachments only
        pdf_attachments = [
            att for att in attachments
            if att.get("data", {}).get("contentType") == "application/pdf"
            or att.get("data", {}).get("filename", "").endswith(".pdf")
        ]
        
        if not pdf_attachments:
            logger.debug(
                f"Item {item_key} has no PDF attachments, skipping",
                extra={"collection_key": collection_key, "item_key": item_key, "title": item_title},
            )
            continue
        
        # Create manifest item
        manifest_item = DownloadManifestItem(
            item_key=item_key,
            title=item_title,
            metadata=item_metadata,
        )
        
        # Download each PDF attachment
        for att in pdf_attachments:
            attachment_key = att.get("key", "")
            attachment_data = att.get("data", {})
            filename = attachment_data.get("filename", f"{attachment_key}.pdf")
            
            if not attachment_key:
                continue
            
            # Generate safe filename
            safe_filename = _sanitize_filename(filename)
            if not safe_filename.endswith(".pdf"):
                safe_filename += ".pdf"
            
            output_path = collection_downloads_dir / safe_filename
            
            # Ensure unique filename
            counter = 1
            original_output_path = output_path
            while output_path.exists():
                stem = original_output_path.stem
                output_path = collection_downloads_dir / f"{stem}_{counter}.pdf"
                counter += 1
            
            # Download attachment
            try:
                downloaded_path = zotero_importer.download_attachment(
                    item_key=item_key,
                    attachment_key=attachment_key,
                    output_path=output_path,
                )
                
                file_size = downloaded_path.stat().st_size if downloaded_path.exists() else None
                
                manifest_attachment = DownloadManifestAttachment(
                    attachment_key=attachment_key,
                    filename=filename,
                    local_path=downloaded_path.resolve(),
                    download_status="success",
                    file_size=file_size,
                )
                
                total_attachments += 1
                batch_attachment_count += 1
                
                logger.debug(
                    f"Downloaded attachment: {downloaded_path}",
                    extra={
                        "collection_key": collection_key,
                        "item_key": item_key,
                        "attachment_key": attachment_key,
                        "output_path": str(downloaded_path),
                    },
                )
                
            except Exception as e:
                error_msg = f"Failed to download attachment {attachment_key} for item {item_key}: {e}"
                errors.append(error_msg)
                logger.error(error_msg, extra={"collection_key": collection_key, "item_key": item_key}, exc_info=True)
                
                manifest_attachment = DownloadManifestAttachment(
                    attachment_key=attachment_key,
                    filename=filename,
                    local_path=output_path.resolve(),
                    download_status="failed",
                    error=str(e),
                )
            
            manifest_item.add_attachment(manifest_attachment)
        
        # Add item to manifest (only if it has attachments)
        if manifest_item.attachments:
            download_manifest.add_item(manifest_item)
        
        # Batch progress logging
        if batch_attachment_count >= BATCH_SIZE:
            logger.info(
                f"Downloaded batch: {batch_attachment_count} attachments so far",
                extra={"collection_key": collection_key, "total_attachments": total_attachments},
            )
            batch_attachment_count = 0
    
    # Save download manifest
    try:
        with manifest_path.open("w") as f:
            json.dump(download_manifest.to_dict(), f, indent=2)
        
        logger.info(
            f"Download manifest saved: {manifest_path}",
            extra={"collection_key": collection_key, "manifest_path": str(manifest_path)},
        )
    except Exception as e:
        error_msg = f"Failed to save download manifest: {e}"
        errors.append(error_msg)
        logger.error(error_msg, extra={"collection_key": collection_key}, exc_info=True)
    
    duration_seconds = (datetime.now() - start_time).total_seconds()
    
    return {
        "collection_key": collection_key,
        "collection_name": collection_name,
        "total_items": len(items_to_process),
        "total_attachments": total_attachments,
        "manifest_path": str(manifest_path),
        "duration_seconds": duration_seconds,
        "warnings": warnings,
        "errors": errors,
    }


def process_downloaded_files(
    project_id: str,
    collection_key: str,
    manifest_path: Path,
    converter: TextConverterPort | None = None,
    chunker: ChunkerPort | None = None,
    resolver: MetadataResolverPort | None = None,
    embedder: EmbeddingPort | None = None,
    index: VectorIndexPort | None = None,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
    progress_reporter: ProgressReporterPort | None = None,
    checkpoint_manager: CheckpointManagerPort | None = None,
    resume: bool = False,
    correlation_id: str | None = None,
    zotero_config: dict[str, Any] | None = None,
    audit_dir: Path | None = None,
    checkpoints_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Process already-downloaded files from a download manifest.
    
    Loads manifest, verifies files exist, and processes them through the ingest pipeline.
    Supports checkpointing for resumability.
    
    Args:
        project_id: CiteLoom project identifier
        collection_key: Zotero collection key
        manifest_path: Path to download manifest JSON file
        converter: TextConverterPort for document conversion
        chunker: ChunkerPort for document chunking
        resolver: MetadataResolverPort for citation metadata resolution
        embedder: EmbeddingPort for embedding generation
        index: VectorIndexPort for vector storage
        embedding_model: Embedding model ID (default: "BAAI/bge-small-en-v1.5")
        progress_reporter: Optional progress reporter for batch-level and document-level progress
        checkpoint_manager: Optional checkpoint manager for resumable processing
        resume: Whether to resume from existing checkpoint
        correlation_id: Optional correlation ID (generated if not provided)
        zotero_config: Optional Zotero configuration dict
        audit_dir: Optional directory for audit JSONL logs
        checkpoints_dir: Directory for checkpoint files (default: var/checkpoints)
    
    Returns:
        Dict with same structure as batch_import_from_zotero return value
    
    Raises:
        ValueError: If required adapters missing or manifest invalid
        FileNotFoundError: If manifest file not found
    """
    from datetime import datetime
    
    start_time = datetime.now()
    
    # Validate required adapters
    if not converter:
        raise ValueError("converter adapter required")
    if not chunker:
        raise ValueError("chunker adapter required")
    if not resolver:
        raise ValueError("resolver adapter required")
    if not embedder:
        raise ValueError("embedder adapter required")
    if not index:
        raise ValueError("index adapter required")
    
    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    logger.info(
        f"Processing downloaded files from manifest: {manifest_path}",
        extra={
            "correlation_id": correlation_id,
            "project_id": project_id,
            "collection_key": collection_key,
            "manifest_path": str(manifest_path),
        },
    )
    
    # Load download manifest (T092: load manifest and verify files exist)
    if not manifest_path.exists():
        raise FileNotFoundError(f"Download manifest not found: {manifest_path}")
    
    try:
        with manifest_path.open("r") as f:
            manifest_data = json.load(f)
        download_manifest = DownloadManifest.from_dict(manifest_data)
    except Exception as e:
        raise ValueError(f"Failed to load download manifest: {e}") from e
    
    # Verify manifest matches collection
    if download_manifest.collection_key != collection_key:
        raise ValueError(
            f"Manifest collection_key mismatch: expected '{collection_key}', "
            f"got '{download_manifest.collection_key}'"
        )
    
    # Verify files exist before processing (T092)
    missing_files: list[str] = []
    for item in download_manifest.get_successful_downloads():
        for attachment in item.get_pdf_attachments():
            if attachment.download_status == "success":
                if not attachment.local_path.exists():
                    missing_files.append(str(attachment.local_path))
    
    if missing_files:
        raise FileNotFoundError(
            f"Missing {len(missing_files)} files from manifest. "
            f"First missing file: {missing_files[0]}"
        )
    
    # Get collection name from manifest
    collection_name = download_manifest.collection_name
    
    warnings: list[str] = []
    errors: list[str] = []
    
    # Initialize checkpoint manager and load checkpoint if resuming (T093: use checkpointing)
    checkpoint: IngestionCheckpoint | None = None
    checkpoint_path: Path | None = None
    
    if checkpoint_manager:
        checkpoint_path = checkpoint_manager.get_checkpoint_path(correlation_id)
        
        if resume:
            try:
                checkpoint = checkpoint_manager.load_checkpoint(correlation_id=correlation_id)
                
                if checkpoint:
                    if not checkpoint_manager.validate_checkpoint(checkpoint):
                        warning_msg = "Checkpoint file is invalid or corrupted. Starting fresh processing."
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id})
                        checkpoint = None
                    else:
                        if checkpoint.project_id != project_id or checkpoint.collection_key != collection_key:
                            warning_msg = "Checkpoint project/collection mismatch. Starting fresh processing."
                            warnings.append(warning_msg)
                            logger.warning(warning_msg, extra={"correlation_id": correlation_id})
                            checkpoint = None
                        else:
                            logger.info(
                                f"Resuming from checkpoint: {len(checkpoint.get_completed_documents())} "
                                f"documents completed, {len(checkpoint.get_incomplete_documents())} remaining",
                                extra={"correlation_id": correlation_id},
                            )
            except Exception as e:
                warning_msg = f"Failed to load checkpoint: {e}. Starting fresh processing."
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                checkpoint = None
        
        if checkpoint is None:
            checkpoint = IngestionCheckpoint(
                correlation_id=correlation_id,
                project_id=project_id,
                collection_key=collection_key,
                start_time=start_time,
            )
    
    # Count total attachments
    total_attachments = sum(
        len(item.get_pdf_attachments())
        for item in download_manifest.get_successful_downloads()
    )
    
    logger.info(
        f"Processing {total_attachments} downloaded documents",
        extra={"correlation_id": correlation_id, "total_attachments": total_attachments},
    )
    
    # Initialize batch progress if reporter provided
    batch_progress = None
    if progress_reporter:
        batch_progress = progress_reporter.start_batch(
            total_documents=total_attachments,
            description=f"Processing documents from {collection_name}",
        )
    
    total_chunks = 0
    total_documents_processed = 0
    document_index = 0
    
    # Track completed document paths from checkpoint for skipping
    completed_paths: set[str] = set()
    if checkpoint:
        for doc in checkpoint.get_completed_documents():
            completed_paths.add(doc.path)
    
    # Track chunks written for batch checkpoint saving
    chunks_since_last_checkpoint = 0
    CHECKPOINT_BATCH_SIZE = 300
    
    # Process each successful download from manifest
    for item in download_manifest.get_successful_downloads():
        item_key = item.item_key
        item_metadata = item.metadata
        
        # Process all PDF attachments from this item as separate documents
        for attachment in item.get_pdf_attachments():
            if attachment.download_status != "success":
                continue
            
            file_path = attachment.local_path
            file_path_str = str(file_path.resolve())
            
            # Skip if already completed (resume logic)
            if file_path_str in completed_paths:
                logger.debug(
                    f"Skipping completed document: {file_path.name}",
                    extra={"correlation_id": correlation_id, "file_path": str(file_path)},
                )
                if checkpoint:
                    for doc in checkpoint.documents:
                        if doc.path == file_path_str and doc.status == "completed":
                            total_chunks += doc.chunks_count
                            total_documents_processed += 1
                            if batch_progress:
                                batch_progress.update(total_documents_processed)
                            break
                document_index += 1
                continue
            
            # Create document checkpoint for tracking
            doc_checkpoint = DocumentCheckpoint(
                path=file_path_str,
                status="pending",
                zotero_item_key=item_key,
                zotero_attachment_key=attachment.attachment_key,
            )
            
            # Update checkpoint with pending document
            if checkpoint:
                checkpoint.add_document_checkpoint(doc_checkpoint)
            
            # Create ingest request
            ingest_request = IngestRequest(
                source_path=str(file_path),
                project_id=project_id,
                zotero_config=zotero_config,
                embedding_model=embedding_model,
            )
            
            document_index += 1
            
            try:
                # Update checkpoint: marking as converting
                if checkpoint:
                    doc_checkpoint.mark_stage("converting")
                    checkpoint.add_document_checkpoint(doc_checkpoint)
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                    except Exception as e:
                        warning_msg = f"Failed to save checkpoint after stage update: {e}"
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                
                # Process document through ingest pipeline
                result: IngestResult = ingest_document(
                    request=ingest_request,
                    converter=converter,
                    chunker=chunker,
                    resolver=resolver,
                    embedder=embedder,
                    index=index,
                    audit_dir=audit_dir,
                    correlation_id=correlation_id,
                    progress_reporter=progress_reporter,
                    document_index=document_index,
                    total_documents=total_attachments,
                )
                
                total_chunks += result.chunks_written
                chunks_since_last_checkpoint += result.chunks_written
                total_documents_processed += result.documents_processed
                
                # Update checkpoint: mark as completed
                if checkpoint:
                    doc_checkpoint.mark_completed(
                        chunks_count=result.chunks_written,
                        doc_id=result.doc_id if hasattr(result, "doc_id") else f"doc_{correlation_id}_{document_index}",
                    )
                    checkpoint.add_document_checkpoint(doc_checkpoint)
                
                if batch_progress:
                    batch_progress.update(total_documents_processed)
                
                logger.info(
                    f"Processed document: {file_path.name} ({result.chunks_written} chunks)",
                    extra={
                        "correlation_id": correlation_id,
                        "file_path": str(file_path),
                        "chunks_written": result.chunks_written,
                    },
                )
                
                # Save checkpoint after each document completes
                if checkpoint and checkpoint_manager:
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                    except Exception as e:
                        warning_msg = f"Failed to save checkpoint after document: {e}"
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                
                # Save checkpoint after batch upsert
                if checkpoint and checkpoint_manager and chunks_since_last_checkpoint >= CHECKPOINT_BATCH_SIZE:
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                        chunks_since_last_checkpoint = 0
                    except Exception as e:
                        warning_msg = f"Failed to save checkpoint after batch upsert: {e}"
                        warnings.append(warning_msg)
                        logger.warning(warning_msg, extra={"correlation_id": correlation_id}, exc_info=True)
                
            except Exception as e:
                error_msg = f"Failed to process document {file_path}: {e}"
                errors.append(error_msg)
                logger.error(error_msg, extra={"correlation_id": correlation_id, "file_path": str(file_path)}, exc_info=True)
                
                # Update checkpoint: mark as failed
                if checkpoint:
                    doc_checkpoint.mark_failed(error=str(e))
                    checkpoint.add_document_checkpoint(doc_checkpoint)
                    try:
                        checkpoint_manager.save_checkpoint(checkpoint, checkpoint_path)
                    except Exception as checkpoint_err:
                        logger.warning(
                            f"Failed to save checkpoint after document failure: {checkpoint_err}",
                            extra={"correlation_id": correlation_id},
                            exc_info=True,
                        )
                continue
    
    # Finish batch progress
    if batch_progress:
        batch_progress.finish()
    
    duration_seconds = (datetime.now() - start_time).total_seconds()
    
    # Display final summary
    if progress_reporter and hasattr(progress_reporter, "display_summary"):
        progress_reporter.display_summary(
            total_documents=total_documents_processed,
            chunks_created=total_chunks,
            duration_seconds=duration_seconds,
            warnings=warnings,
            errors=errors,
        )
    
    if progress_reporter and hasattr(progress_reporter, "cleanup"):
        progress_reporter.cleanup()
    
    logger.info(
        f"Processing completed: {total_documents_processed} documents, {total_chunks} chunks",
        extra={
            "correlation_id": correlation_id,
            "total_documents": total_documents_processed,
            "chunks_written": total_chunks,
            "duration_seconds": duration_seconds,
        },
    )
    
    return {
        "correlation_id": correlation_id,
        "collection_key": collection_key,
        "collection_name": collection_name,
        "total_items": len(download_manifest.items),
        "total_attachments": total_attachments,
        "total_documents": total_documents_processed,
        "chunks_written": total_chunks,
        "duration_seconds": duration_seconds,
        "manifest_path": str(manifest_path),
        "checkpoint_path": str(checkpoint_path) if checkpoint_path else None,
        "warnings": warnings,
        "errors": errors,
    }


def _sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe filesystem storage.
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename safe for filesystem
    """
    import re
    
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    
    # Remove leading/trailing dots and spaces (Windows doesn't allow these)
    sanitized = sanitized.strip(" .")
    
    # Limit length (Windows has 255 char limit for filenames)
    if len(sanitized) > 200:
        stem, ext = sanitized.rsplit(".", 1) if "." in sanitized else (sanitized, "")
        sanitized = stem[:200 - len(ext) - 1] + "." + ext if ext else stem[:200]
    
    return sanitized

