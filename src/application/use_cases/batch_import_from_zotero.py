"""Use case for batch importing documents from Zotero collections."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from ...domain.models.download_manifest import (
    DownloadManifest,
    DownloadManifestAttachment,
    DownloadManifestItem,
)
from ..dto.ingest import IngestRequest, IngestResult
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
    zotero_config: dict[str, Any] | None = None,
    include_tags: list[str] | None = None,
    exclude_tags: list[str] | None = None,
    include_subcollections: bool = False,
    downloads_dir: Path | None = None,
    audit_dir: Path | None = None,
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
        zotero_config: Optional Zotero configuration dict
        include_tags: Optional list of tags to include (OR logic - any match selects item)
        exclude_tags: Optional list of tags to exclude (ANY-match logic - any exclude tag excludes item)
        include_subcollections: Whether to recursively include items from subcollections
        downloads_dir: Directory for downloaded attachments (default: var/zotero_downloads)
        audit_dir: Optional directory for audit JSONL logs
    
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
            - warnings: List of warnings encountered
            - errors: List of errors encountered
    
    Raises:
        ValueError: If collection_key or collection_name not provided, or if required adapters missing
    """
    start_time = datetime.now()
    
    # Generate correlation ID at start for checkpoint file naming (FR-029)
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
    
    # Phase 1: Download all attachments
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
        
        logger.info(
            f"Found {len(items_to_process)} items in collection",
            extra={"correlation_id": correlation_id, "item_count": len(items_to_process)},
        )
    except Exception as e:
        error_msg = f"Failed to fetch collection items: {e}"
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
    total_attachments = 0
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
    
    # Save download manifest
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
    
    # Process each successful download from manifest
    for item in download_manifest.get_successful_downloads():
        item_key = item.item_key
        item_metadata = item.metadata
        
        # Process all PDF attachments from this item as separate documents (FR-028)
        for attachment in item.get_pdf_attachments():
            if attachment.download_status != "success":
                continue
            
            file_path = attachment.local_path
            
            # Check if file exists
            if not file_path.exists():
                warning_msg = f"Downloaded file not found: {file_path}"
                warnings.append(warning_msg)
                logger.warning(warning_msg, extra={"correlation_id": correlation_id, "file_path": str(file_path)})
                continue
            
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
                total_documents_processed += result.documents_processed
                
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
                
            except Exception as e:
                error_msg = f"Failed to process document {file_path}: {e}"
                errors.append(error_msg)
                logger.error(error_msg, extra={"correlation_id": correlation_id, "file_path": str(file_path)}, exc_info=True)
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

