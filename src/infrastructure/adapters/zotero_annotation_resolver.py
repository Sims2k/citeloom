"""Adapter for extracting and indexing PDF annotations from Zotero."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING

from ...application.ports.annotation_resolver import Annotation, AnnotationResolverPort
from ...application.ports.embeddings import EmbeddingPort
from ...application.ports.metadata_resolver import MetadataResolverPort
from ...application.ports.vector_index import VectorIndexPort
from ...domain.errors import ZoteroAnnotationNotFoundError, ZoteroAPIError, ZoteroRateLimitError

if TYPE_CHECKING:
    from pyzotero import zotero

logger = logging.getLogger(__name__)


class ZoteroAnnotationResolverAdapter(AnnotationResolverPort):
    """
    Adapter for extracting PDF annotations from Zotero via Web API.
    
    Fetches annotations using pyzotero children() method, normalizes them,
    and indexes as separate vector points with type:annotation tag.
    """

    def __init__(
        self,
        embedder: EmbeddingPort,
    ) -> None:
        """
        Initialize annotation resolver.
        
        Args:
            embedder: EmbeddingPort for generating annotation embeddings
        """
        self._embedder = embedder

    def _retry_with_backoff(
        self,
        func: callable,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: bool = True,
    ) -> any:
        """
        Retry function with exponential backoff and jitter.
        
        Args:
            func: Function to retry (callable)
            max_retries: Maximum number of retries (default 3)
            base_delay: Base delay in seconds (default 1.0)
            max_delay: Maximum delay in seconds (default 30.0)
            jitter: Add random jitter to prevent thundering herd (default True)
        
        Returns:
            Function result
        
        Raises:
            ZoteroAPIError: If all retries fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                last_error = e

                if attempt < max_retries - 1:
                    # Exponential backoff: base_delay * 2^attempt
                    delay = min(base_delay * (2**attempt), max_delay)

                    # Add jitter (±25%)
                    if jitter:
                        jitter_amount = delay * 0.25 * (2 * random.random() - 1)
                        delay = max(0, delay + jitter_amount)

                    logger.warning(
                        f"Annotation fetch attempt {attempt + 1}/{max_retries} failed, retrying in {delay:.2f}s: {e}",
                        extra={"attempt": attempt + 1, "max_retries": max_retries, "error": str(e)},
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        f"All {max_retries} annotation fetch attempts failed: {e}",
                        exc_info=True,
                        extra={"max_retries": max_retries},
                    )

        raise ZoteroAPIError(
            f"Annotation fetch failed after {max_retries} attempts: {last_error}",
            details={"max_retries": max_retries, "last_error": str(last_error)},
        ) from last_error

    def fetch_annotations(
        self,
        attachment_key: str,
        zotero_client: zotero.Zotero,
    ) -> list[Annotation]:
        """
        Fetch annotations for attachment via Web API.
        
        Args:
            attachment_key: Zotero attachment key
            zotero_client: PyZotero client instance (for Web API access)
        
        Returns:
            List of normalized Annotation objects
        
        Raises:
            ZoteroAPIError: If API request fails after retries
            ZoteroRateLimitError: If rate limit encountered (after retries)
        """
        def _fetch() -> list[Annotation]:
            try:
                # Fetch annotations using children() method with itemType=annotation
                annotations_data = zotero_client.children(attachment_key, itemType="annotation")
                
                if not annotations_data:
                    # No annotations found - this is not an error, just return empty list
                    return []
                
                # Normalize annotations
                normalized: list[Annotation] = []
                for ann in annotations_data:
                    data = ann.get("data", {})
                    
                    # Extract fields
                    page_index = data.get("pageIndex", 0)
                    page = page_index + 1  # Convert 0-indexed to 1-indexed
                    quote = data.get("text", "") or ""
                    comment = data.get("comment", "") or None
                    color = data.get("color", "") or None
                    
                    # Extract tags
                    tags: list[str] = []
                    tag_data = data.get("tags", [])
                    for tag_obj in tag_data:
                        tag_name = tag_obj.get("tag", "") if isinstance(tag_obj, dict) else str(tag_obj)
                        if tag_name:
                            tags.append(tag_name)
                    
                    # Create Annotation object
                    annotation = Annotation(
                        page=page,
                        quote=quote,
                        comment=comment,
                        color=color,
                        tags=tags,
                    )
                    normalized.append(annotation)
                
                return normalized
                
            except Exception as e:
                error_str = str(e).lower()
                if "rate" in error_str or "limit" in error_str or "429" in error_str:
                    raise ZoteroRateLimitError(
                        "Zotero API rate limit exceeded during annotation fetch",
                        retry_after=60,
                    ) from e
                raise ZoteroAPIError(
                    f"Failed to fetch annotations for attachment {attachment_key}: {e}",
                    details={"attachment_key": attachment_key, "error": str(e)},
                ) from e

        try:
            return self._retry_with_backoff(_fetch)
        except ZoteroAPIError:
            # Log warning and return empty list (graceful degradation)
            logger.warning(
                f"Failed to fetch annotations for attachment {attachment_key} after retries. Skipping annotations.",
                extra={"attachment_key": attachment_key},
                exc_info=True,
            )
            return []

    def index_annotations(
        self,
        annotations: list[Annotation],
        item_key: str,
        attachment_key: str,
        project_id: str,
        vector_index: VectorIndexPort,
        embedding_model: str,
        resolver: MetadataResolverPort | None = None,
    ) -> int:
        """
        Index annotations as separate vector points.
        
        Args:
            annotations: List of Annotation objects to index
            item_key: Parent Zotero item key
            attachment_key: Parent attachment key
            project_id: CiteLoom project ID
            vector_index: Vector index port for storage
            embedding_model: Embedding model identifier
            resolver: Optional metadata resolver for citation metadata
        
        Returns:
            Number of annotation points successfully indexed
        
        Raises:
            IndexError: If indexing fails
        """
        if not annotations:
            return 0
        
        try:
            # Resolve citation metadata if resolver provided
            citekey: str | None = None
            title: str | None = None
            authors: list[str] = []
            year: int | None = None
            
            if resolver:
                try:
                    # Try to resolve metadata using item_key or attachment_key
                    # Note: resolver.resolve() expects citekey, doc_id, and source_hint
                    # We'll use item_key as doc_id hint
                    metadata = resolver.resolve(
                        citekey=None,
                        doc_id=item_key,
                        source_hint=f"zotero:{item_key}",
                    )
                    if metadata:
                        citekey = metadata.citekey
                        title = metadata.title
                        authors = metadata.authors or []
                        year = metadata.year
                except Exception as e:
                    logger.debug(
                        f"Failed to resolve metadata for annotation indexing: {e}",
                        extra={"item_key": item_key, "attachment_key": attachment_key},
                    )
            
            # Prepare annotation items for indexing
            items_to_index: list[dict[str, any]] = []
            
            for annotation in annotations:
                # Create chunk text: quote + comment (if comment exists)
                chunk_text = annotation.quote
                if annotation.comment:
                    chunk_text = f"{annotation.quote}\n\n{annotation.comment}"
                
                # Generate embedding for annotation
                try:
                    # embed() takes a list and returns a list of embeddings
                    embeddings = self._embedder.embed([chunk_text], model_id=embedding_model)
                    embedding = embeddings[0] if embeddings else None
                    if not embedding:
                        logger.warning(
                            f"Failed to generate embedding for annotation (empty result)",
                            extra={"attachment_key": attachment_key, "page": annotation.page},
                        )
                        continue
                except Exception as e:
                    logger.warning(
                        f"Failed to generate embedding for annotation: {e}",
                        extra={"attachment_key": attachment_key, "page": annotation.page},
                    )
                    continue  # Skip this annotation if embedding fails
                
                # Create annotation payload
                payload: dict[str, any] = {
                    "type": "annotation",
                    "project_id": project_id,
                    "chunk_text": chunk_text,
                    
                    # Zotero traceability
                    "zotero": {
                        "item_key": item_key,
                        "attachment_key": attachment_key,
                        "annotation": {
                            "page": annotation.page,
                            "quote": annotation.quote,
                            "comment": annotation.comment,
                            "color": annotation.color,
                            "tags": annotation.tags,
                        },
                    },
                    
                    # Metadata for citation
                    "citekey": citekey,
                    "page_start": annotation.page,
                    "page_end": annotation.page,
                    "title": title,
                    "authors": authors,
                    "year": year,
                    
                    # Standard fields
                    "embed_model": embedding_model,
                    "version": "1.0",
                }
                
                # Create item dict for vector index upsert
                item = {
                    "embedding": embedding,
                    "payload": payload,
                }
                
                items_to_index.append(item)
            
            # Upsert all annotation items
            if items_to_index:
                vector_index.upsert(
                    items=items_to_index,
                    project_id=project_id,
                    model_id=embedding_model,
                )
                
                logger.info(
                    f"Indexed {len(items_to_index)} annotations for attachment {attachment_key}",
                    extra={
                        "project_id": project_id,
                        "item_key": item_key,
                        "attachment_key": attachment_key,
                        "annotation_count": len(items_to_index),
                    },
                )
                
                return len(items_to_index)
            else:
                return 0
                
        except Exception as e:
            logger.error(
                f"Failed to index annotations: {e}",
                extra={
                    "project_id": project_id,
                    "item_key": item_key,
                    "attachment_key": attachment_key,
                    "annotation_count": len(annotations),
                },
                exc_info=True,
            )
            raise IndexError(f"Annotation indexing failed: {e}") from e

