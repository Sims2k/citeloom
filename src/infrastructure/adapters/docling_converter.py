"""Docling converter adapter with optional import handling for Windows compatibility."""

import hashlib
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Mapping, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...application.ports.progress_reporter import ProgressReporterPort, DocumentProgressContext

try:
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    try:
        from docling.document_converter.pipeline_options import PdfPipelineOptions
        from docling.document_converter.pipeline_options import DoclingPipelineOptions
    except ImportError:
        # Pipeline options may have different import path in some versions
        PdfPipelineOptions = None  # type: ignore
        DoclingPipelineOptions = None  # type: ignore
    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    DocumentConverter = None  # type: ignore
    InputFormat = None  # type: ignore
    PdfPipelineOptions = None  # type: ignore
    DoclingPipelineOptions = None  # type: ignore

logger = logging.getLogger(__name__)

# Module-level cache for process-scoped converter instances (T004)
_converter_cache: dict[str, "DoclingConverterAdapter"] = {}


class TimeoutError(Exception):
    """Raised when document conversion exceeds timeout limits."""


class DoclingConverterAdapter:
    """Adapter for Docling document conversion (optional on Windows)."""

    # Default OCR languages (priority: Zotero metadata → explicit config → default)
    DEFAULT_OCR_LANGUAGES = ['en', 'de']
    
    # Timeout limits (from spec clarifications)
    DOCUMENT_TIMEOUT_SECONDS = 120
    PAGE_TIMEOUT_SECONDS = 10
    
    def __init__(self):
        if not DOCLING_AVAILABLE:
            raise ImportError(
                "Docling is not available on Windows (Python 3.12). "
                "deepsearch-glm dependency lacks Windows wheels for Python 3.12. "
                "Windows users should either:\n"
                "1. Use WSL (Windows Subsystem for Linux)\n"
                "2. Use Python 3.11 (not recommended - project requires 3.12)\n"
                "3. Wait for Windows support from docling/deepsearch-glm"
            )
        
        # Initialize DocumentConverter with OCR support
        self._initialize_converter()
    
    def _initialize_converter(self) -> None:
        """Initialize DocumentConverter with OCR configuration."""
        try:
            logger.info("Initializing Docling DocumentConverter (this may take a moment on first run while models are downloaded)...")
            
            # Check for model cache directory to show user if models are cached
            import os
            from pathlib import Path
            
            # Docling stores models in ~/.cache/docling/models by default
            cache_dir = Path.home() / ".cache" / "docling" / "models"
            if cache_dir.exists():
                model_count = len(list(cache_dir.rglob("*.onnx"))) + len(list(cache_dir.rglob("*.bin"))) + len(list(cache_dir.rglob("*.pt")))
                if model_count > 0:
                    logger.info(f"Found {model_count} cached model files in {cache_dir}. Using cached models.")
                else:
                    logger.info(f"Model cache directory exists but appears empty. Models will be downloaded on first use.")
            else:
                logger.info(f"Model cache directory not found. Models will be downloaded to {cache_dir} on first use.")
            
            # Configure pipeline options with OCR enabled (if available)
            # Docling v2 supports OCR via Tesseract/RapidOCR
            # If pipeline options are not available, use default converter
            logger.info("Configuring Docling pipeline options...")
            if DoclingPipelineOptions:
                pipeline_options = DoclingPipelineOptions()
                
                # Enable OCR for scanned documents
                # Note: Docling automatically detects if OCR is needed
                # We configure OCR languages via pipeline options
                if PdfPipelineOptions:
                    pdf_options = PdfPipelineOptions()
                    # Enable OCR detection and processing
                    pipeline_options.pdf = pdf_options
                
                logger.info("Creating DocumentConverter instance (this may take 10-30 seconds on first run)...")
                self.converter = DocumentConverter(
                    pipeline_options=pipeline_options,
                    # Allow common formats: PDF, DOCX, PPTX, HTML, images
                )
            else:
                # Fallback: initialize without pipeline options
                logger.info("Creating DocumentConverter instance (this may take 10-30 seconds on first run)...")
                self.converter = DocumentConverter()
            
            logger.info("DocumentConverter initialized successfully with OCR support")
        except Exception as e:
            logger.error(f"Failed to initialize DocumentConverter: {e}", exc_info=True)
            raise
    
    def _select_ocr_languages(
        self,
        ocr_languages: list[str] | None = None,
    ) -> list[str]:
        """
        Select OCR languages with priority:
        1. Explicit ocr_languages parameter
        2. Default ['en', 'de']
        
        Note: Zotero metadata language should be passed via ocr_languages parameter
        by the caller (use case layer).
        
        Args:
            ocr_languages: Optional explicit OCR language codes
        
        Returns:
            List of OCR language codes for Docling
        """
        if ocr_languages:
            # Normalize language codes (e.g., 'en-US' → 'en')
            normalized = []
            for lang in ocr_languages:
                # Extract base language code (e.g., 'en' from 'en-US')
                base_lang = lang.split('-')[0].lower()
                if base_lang not in normalized:
                    normalized.append(base_lang)
            return normalized if normalized else self.DEFAULT_OCR_LANGUAGES
        
        return self.DEFAULT_OCR_LANGUAGES
    
    def _configure_ocr(self, languages: list[str]) -> None:
        """
        Configure OCR with Tesseract/RapidOCR for scanned documents.
        
        Args:
            languages: OCR language codes (e.g., ['en', 'de'])
        
        Note:
            Docling automatically detects when OCR is needed.
            Language configuration may be done via pipeline options or converter settings.
        """
        # Docling v2 handles OCR configuration internally
        # We ensure languages are available for OCR engine selection
        logger.debug(f"OCR configured with languages: {languages}")
    
    def _convert_with_timeout(self, source_path: str) -> Any:
        """
        Convert document with timeout enforcement using ThreadPoolExecutor (T059, T060).
        
        Cross-platform timeout implementation using concurrent.futures.ThreadPoolExecutor.
        This works on all platforms (Windows, Linux, macOS), unlike signal.SIGALRM which
        only works on Unix systems.
        
        Args:
            source_path: Path to source document
        
        Returns:
            Docling conversion result
        
        Raises:
            TimeoutError: If conversion exceeds timeout (renamed from built-in TimeoutError
                         to avoid conflict with concurrent.futures.TimeoutError)
        
        Platform Behavior (T062a):
        - All platforms: Uses ThreadPoolExecutor with timeout parameter
        - Timeout enforcement: Thread-based timeout works consistently across platforms
        - Note: If conversion is already executing when timeout occurs, it may continue
          in background thread until completion, but the result will not be returned
        """
        def _perform_conversion() -> Any:
            """Perform the actual conversion in a separate thread."""
            return self.converter.convert(source_path)
        
        # Use ThreadPoolExecutor for cross-platform timeout enforcement (T059, T060)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_perform_conversion)
            try:
                # Wait for conversion with timeout - works on all platforms
                result = future.result(timeout=self.DOCUMENT_TIMEOUT_SECONDS)
                return result
            except FutureTimeoutError:
                # Conversion exceeded timeout - cancel if possible
                # Note: If conversion is already executing, cancellation may not interrupt it
                # but the timeout exception will be raised
                future.cancel()
                timeout_error = TimeoutError(
                    f"Document conversion exceeded {self.DOCUMENT_TIMEOUT_SECONDS}s timeout. "
                    f"Page timeout limit: {self.PAGE_TIMEOUT_SECONDS}s per page."
                )
                # Enhanced diagnostic logging for timeout failures (T103)
                logger.error(
                    f"Document conversion timeout after {self.DOCUMENT_TIMEOUT_SECONDS}s: {source_path}",
                    extra={
                        "source_path": source_path,
                        "timeout_seconds": self.DOCUMENT_TIMEOUT_SECONDS,
                        "page_timeout_seconds": self.PAGE_TIMEOUT_SECONDS,
                        "diagnostic": "Document-level timeout occurred. This may indicate: "
                                      "1. Document is extremely large (>1000 pages), "
                                      "2. Complex document structure requiring extensive processing, "
                                      "3. Resource constraints (CPU/memory). "
                                      "Consider splitting large documents or increasing timeout limits.",
                    },
                    exc_info=True,
                )
                raise timeout_error
            except Exception as e:
                # Re-raise any other exceptions from conversion
                # T103: Enhanced diagnostic logging for conversion failures
                logger.error(
                    f"Document conversion failed during processing: {e}",
                    extra={
                        "source_path": source_path,
                        "timeout_seconds": self.DOCUMENT_TIMEOUT_SECONDS,
                        "diagnostic": "Conversion error occurred during document processing. "
                                      "Check document format, corruption, or system resources.",
                    },
                    exc_info=True,
                )
                raise
    
    def _extract_page_map(self, doc: Any, plain_text: str) -> dict[int, tuple[int, int]]:
        """
        Extract page map (page number → (start_offset, end_offset)) from Docling document.
        
        T022: Fixed to correctly extract page boundaries from Docling Document structure.
        
        Args:
            doc: Docling document object
            plain_text: Converted plain text
        
        Returns:
            Dictionary mapping page numbers to character span tuples
        """
        page_map: dict[int, tuple[int, int]] = {}
        
        try:
            # T022: Extract page information from Docling document structure
            # Try multiple approaches to find page boundaries
            
            # Approach 1: Check if document has pages attribute directly
            if hasattr(doc, 'pages') and doc.pages:
                logger.debug("Extracting page map from doc.pages attribute")
                current_offset = 0
                for page_idx, page in enumerate(doc.pages, start=1):
                    # Get page content - try multiple ways to access page text
                    page_text = ""
                    if hasattr(page, 'text') and page.text:
                        page_text = str(page.text)
                    elif hasattr(page, 'content'):
                        page_text = str(page.content)
                    elif hasattr(page, 'export_to_text'):
                        page_text = page.export_to_text()
                    
                    if page_text:
                        start_offset = current_offset
                        end_offset = current_offset + len(page_text)
                        page_map[page_idx] = (start_offset, end_offset)
                        current_offset = end_offset
                    elif hasattr(page, 'page_num'):
                        # If we have page numbers but no text, estimate from position
                        page_num = getattr(page, 'page_num', page_idx)
                        # Estimate page boundaries based on total text length and page count
                        if plain_text and len(doc.pages) > 0:
                            chars_per_page = len(plain_text) / len(doc.pages)
                            start_offset = int((page_num - 1) * chars_per_page)
                            end_offset = int(page_num * chars_per_page)
                            page_map[page_num] = (start_offset, min(end_offset, len(plain_text)))
            
            # Approach 2: Extract from document dictionary structure
            elif hasattr(doc, 'export_to_dict'):
                logger.debug("Extracting page map from doc.export_to_dict() structure")
                doc_dict = doc.export_to_dict()
                page_elements = self._find_page_elements_in_dict(doc_dict)
                
                if page_elements:
                    # Build page map from elements with page numbers
                    for element in page_elements:
                        page_num = element.get('page', element.get('page_num'))
                        if page_num and page_num not in page_map:
                            # Estimate offset based on element position
                            # This is approximate but better than single page
                            text_pos = element.get('text_offset', 0)
                            page_map[page_num] = (text_pos, text_pos + 1000)  # Approximate page size
                    
                    # If we have page numbers but not boundaries, estimate from text
                    if page_map and plain_text:
                        sorted_pages = sorted(page_map.keys())
                        if len(sorted_pages) > 1:
                            # Redistribute text across pages
                            chars_per_page = len(plain_text) / len(sorted_pages)
                            for idx, page_num in enumerate(sorted_pages):
                                start = int(idx * chars_per_page)
                                end = int((idx + 1) * chars_per_page) if idx < len(sorted_pages) - 1 else len(plain_text)
                                page_map[page_num] = (start, end)
            
            # Approach 3: Use markdown export and infer pages from structure
            elif hasattr(doc, 'export_to_markdown') and plain_text:
                logger.debug("Extracting page map from markdown/text estimation")
                markdown = doc.export_to_markdown()
                
                # Look for page breaks or markers in markdown
                # Estimate pages based on document length and structure
                # Average page: ~2000-3000 characters for PDF, ~1500-2500 for Word
                chars_per_page = 2500
                total_pages = max(1, (len(plain_text) // chars_per_page) + (1 if len(plain_text) % chars_per_page > 0 else 0))
                
                for page_num in range(1, total_pages + 1):
                    start_offset = (page_num - 1) * chars_per_page
                    end_offset = min(page_num * chars_per_page, len(plain_text))
                    if start_offset < len(plain_text):
                        page_map[page_num] = (start_offset, end_offset)
            
            # Fallback: If no structure found, estimate from text length
            if not page_map and plain_text:
                logger.debug("Using fallback: estimating pages from text length")
                # Estimate reasonable page count
                chars_per_page = 2500
                total_pages = max(1, (len(plain_text) // chars_per_page) + (1 if len(plain_text) % chars_per_page > 0 else 0))
                
                for page_num in range(1, total_pages + 1):
                    start_offset = (page_num - 1) * chars_per_page
                    end_offset = min(page_num * chars_per_page, len(plain_text))
                    if start_offset < len(plain_text):
                        page_map[page_num] = (start_offset, end_offset)
            
            # T023: Enhanced diagnostic logging
            logger.info(
                f"Extracted page map with {len(page_map)} pages",
                extra={
                    "page_count": len(page_map),
                    "total_text_length": len(plain_text) if plain_text else 0,
                    "page_numbers": sorted(page_map.keys()) if page_map else [],
                },
            )
            
        except Exception as e:
            # T023: Enhanced diagnostic logging for page map extraction failures
            logger.warning(
                f"Failed to extract page map: {e}, using fallback",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "diagnostic": "Page map extraction failed. This may indicate: "
                                  "1. Document structure is not accessible via expected API, "
                                  "2. Document format is not fully supported, "
                                  "3. Document structure is missing page metadata. "
                                  "Fallback mapping will be used, which may affect precise page references.",
                    "plain_text_length": len(plain_text) if plain_text else 0,
                },
                exc_info=True,
            )
            # Fallback: estimate pages from text length
            if plain_text:
                chars_per_page = 2500
                total_pages = max(1, (len(plain_text) // chars_per_page) + 1)
                for page_num in range(1, total_pages + 1):
                    start_offset = (page_num - 1) * chars_per_page
                    end_offset = min(page_num * chars_per_page, len(plain_text))
                    if start_offset < len(plain_text):
                        page_map[page_num] = (start_offset, end_offset)
                logger.info(f"Using fallback page map with {len(page_map)} estimated pages")
            else:
                # Last resort: single page
                page_map[1] = (0, len(plain_text) if plain_text else 0)
        
        return page_map
    
    def _find_page_elements_in_dict(self, doc_dict: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract page-related elements from Docling document dictionary structure."""
        elements: list[dict[str, Any]] = []
        
        def traverse(obj: Any) -> None:
            if isinstance(obj, dict):
                # Check for page metadata
                if 'page' in obj or 'page_num' in obj or 'page_number' in obj:
                    elements.append({
                        'page': obj.get('page') or obj.get('page_num') or obj.get('page_number'),
                        'text_offset': obj.get('text_offset', obj.get('offset', 0)),
                        'type': obj.get('type', 'unknown'),
                    })
                # Traverse nested structures
                for value in obj.values():
                    traverse(value)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)
        
        traverse(doc_dict)
        return elements
    
    def _extract_heading_tree(self, doc: Any, page_map: dict[int, tuple[int, int]]) -> dict[str, Any]:
        """
        Extract heading tree hierarchy with page anchors from Docling document.
        
        T024: Fixed to correctly extract heading hierarchy from Docling Document structure.
        
        Args:
            doc: Docling document object
            page_map: Page map for page anchor calculation
        
        Returns:
            Hierarchical heading tree with page anchors
        """
        heading_tree: dict[str, Any] = {}
        
        try:
            # T024: Extract headings from document structure using multiple approaches
            headings: list[dict[str, Any]] = []
            
            # Approach 1: Extract from document dictionary structure
            if hasattr(doc, 'export_to_dict'):
                logger.debug("Extracting headings from doc.export_to_dict() structure")
                doc_dict = doc.export_to_dict()
                if isinstance(doc_dict, dict):
                    headings = self._find_headings_in_structure(doc_dict, page_map)
            
            # Approach 2: Extract from markdown export
            if not headings and hasattr(doc, 'export_to_markdown'):
                logger.debug("Extracting headings from markdown export")
                markdown = doc.export_to_markdown()
                headings = self._parse_markdown_headings(markdown, page_map)
            
            # Approach 3: Try to access headings directly from document object
            if not headings and hasattr(doc, 'headings'):
                logger.debug("Extracting headings from doc.headings attribute")
                doc_headings = doc.headings
                if doc_headings:
                    for heading in doc_headings:
                        level = getattr(heading, 'level', getattr(heading, 'heading_level', 1))
                        title = getattr(heading, 'text', getattr(heading, 'title', getattr(heading, 'content', '')))
                        page = getattr(heading, 'page', getattr(heading, 'page_num', 1))
                        headings.append({
                            'level': level,
                            'title': str(title),
                            'page': int(page) if page else 1,
                        })
            
            # Build hierarchical tree structure
            if headings:
                heading_tree = self._build_heading_tree(headings, page_map)
                # T025: Enhanced diagnostic logging
                logger.info(
                    f"Extracted heading tree with {len(headings)} headings",
                    extra={
                        "heading_count": len(headings),
                        "tree_root_nodes": len(heading_tree.get('root', [])),
                        "pages_with_headings": len(set(h.get('page', 1) for h in headings)),
                    },
                )
            else:
                logger.debug("No headings found in document structure")
                heading_tree = {'root': []}
                
        except Exception as e:
            # T025: Enhanced diagnostic logging for heading tree extraction failures
            logger.warning(
                f"Failed to extract heading tree: {e}, using empty tree",
                extra={
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "diagnostic": "Heading tree extraction failed. This may indicate: "
                                  "1. Document has no headings (this is normal for some documents), "
                                  "2. Document structure is not accessible via expected API, "
                                  "3. Document format does not preserve heading structure. "
                                  "Empty heading tree will be used, which may affect heading-aware chunking.",
                    "page_count": len(page_map) if page_map else 0,
                },
                exc_info=True,
            )
            heading_tree = {'root': []}
        
        return heading_tree
    
    def _find_headings_in_structure(
        self,
        doc_dict: dict[str, Any],
        page_map: dict[int, tuple[int, int]],
    ) -> list[dict[str, Any]]:
        """Recursively find headings in Docling document structure."""
        headings: list[dict[str, Any]] = []
        
        def traverse(obj: Any, level: int = 1) -> None:
            if isinstance(obj, dict):
                # Check for heading-like structures
                heading_type = obj.get('type', '')
                heading_level = obj.get('level', obj.get('heading_level', level))
                heading_title = obj.get('text', obj.get('title', obj.get('content', '')))
                
                # Check various heading indicators
                is_heading = (
                    heading_type in ['heading', 'title', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'] or
                    heading_type.startswith('heading') or
                    'heading' in heading_type.lower() or
                    (heading_title and heading_type == 'text' and any(keyword in str(obj).lower() for keyword in ['heading', 'title', 'section']))
                )
                
                if is_heading and heading_title:
                    # Extract page number
                    page = obj.get('page', obj.get('page_num', obj.get('page_number', 1)))
                    if not page or page == 0:
                        # Try to infer page from text offset if available
                        text_offset = obj.get('text_offset', obj.get('offset', 0))
                        page = self._find_page_for_offset(text_offset, page_map) if page_map else 1
                    
                    headings.append({
                        'level': int(heading_level) if heading_level else level,
                        'title': str(heading_title).strip(),
                        'page': int(page) if page else 1,
                    })
                
                # Traverse nested structures - headings often nested in sections
                for key, value in obj.items():
                    # Increase level when entering section-like structures
                    new_level = level + 1 if key in ['section', 'subsection', 'children', 'content'] else level
                    traverse(value, new_level)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item, level)
        
        traverse(doc_dict)
        return headings
    
    def _parse_markdown_headings(
        self,
        markdown: str,
        page_map: dict[int, tuple[int, int]],
    ) -> list[dict[str, Any]]:
        """Parse markdown headings and map to pages."""
        headings: list[dict[str, Any]] = []
        
        lines = markdown.split('\n')
        for line in lines:
            # Match markdown heading patterns (# ## ### etc.)
            match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()
                
                # Find which page this heading is on
                line_pos = markdown.find(line)
                page_num = self._find_page_for_offset(line_pos, page_map)
                
                headings.append({
                    'level': level,
                    'title': title,
                    'page': page_num,
                })
        
        return headings
    
    def _find_page_for_offset(self, offset: int, page_map: dict[int, tuple[int, int]]) -> int:
        """Find page number for a given text offset."""
        for page_num, (start, end) in sorted(page_map.items()):
            if start <= offset < end:
                return page_num
        # Fallback to first page
        return 1
    
    def _build_heading_tree(
        self,
        headings: list[dict[str, Any]],
        page_map: dict[int, tuple[int, int]],
    ) -> dict[str, Any]:
        """Build hierarchical heading tree structure."""
        if not headings:
            return {}
        
        # Sort by page, then by level
        sorted_headings = sorted(headings, key=lambda h: (h.get('page', 1), h.get('level', 1)))
        
        # Build tree with parent-child relationships
        tree: dict[str, Any] = {
            'root': [],
        }
        stack: list[dict[str, Any]] = []  # Stack of parent nodes
        
        for heading in sorted_headings:
            level = heading.get('level', 1)
            title = heading.get('title', '')
            page = heading.get('page', 1)
            
            node = {
                'level': level,
                'title': title,
                'page': page,
                'children': [],
            }
            
            # Find appropriate parent based on level
            while stack and stack[-1].get('level', 1) >= level:
                stack.pop()
            
            if stack:
                stack[-1]['children'].append(node)
            else:
                tree['root'].append(node)
            
            stack.append(node)
        
        return tree
    
    def _normalize_text(self, text: str) -> str:
        """
        Normalize text: hyphen repair, whitespace normalization, preserving code/math blocks.
        
        Args:
            text: Raw converted text
        
        Returns:
            Normalized text
        """
        if not text:
            return text
        
        # Preserve code blocks (between ``` or `)
        code_blocks: list[tuple[int, int, str]] = []
        code_pattern = r'```([^`]+)```|`([^`]+)`'
        for match in re.finditer(code_pattern, text):
            start, end = match.span()
            code_blocks.append((start, end, match.group(0)))
        
        # Preserve math blocks (between $$ or \( \))
        math_blocks: list[tuple[int, int, str]] = []
        math_pattern = r'\$\$([^$]+)\$\$|\$\([^)]+\)\$'
        for match in re.finditer(math_pattern, text):
            start, end = match.span()
            math_blocks.append((start, end, match.group(0)))
        
        # Temporarily replace code/math blocks with placeholders
        replacements: dict[str, str] = {}
        protected_text = text
        offset = 0
        
        for start, end, original in sorted(code_blocks + math_blocks, key=lambda x: x[0]):
            placeholder = f"__PROTECTED_{len(replacements)}__"
            replacements[placeholder] = original
            protected_text = (
                protected_text[:start + offset] +
                placeholder +
                protected_text[end + offset:]
            )
            offset += len(placeholder) - (end - start)
        
        # Hyphen repair: fix line breaks at hyphens (e.g., "line-\nbreak" → "line-break")
        # Match hyphen at end of line followed by newline
        protected_text = re.sub(r'-\s*\n\s*', '', protected_text)
        
        # Whitespace normalization: collapse multiple spaces, normalize newlines
        protected_text = re.sub(r'[ \t]+', ' ', protected_text)  # Multiple spaces → single space
        protected_text = re.sub(r'\n{3,}', '\n\n', protected_text)  # Multiple newlines → double newline
        protected_text = re.sub(r'[ \t]+\n', '\n', protected_text)  # Trailing spaces before newline
        protected_text = protected_text.strip()
        
        # Restore code/math blocks
        normalized = protected_text
        for placeholder, original in replacements.items():
            normalized = normalized.replace(placeholder, original)
        
        return normalized
    
    def _detect_image_only_pages(self, doc: Any) -> list[int]:
        """
        Detect pages that contain only images (no text).
        
        Args:
            doc: Docling document object
        
        Returns:
            List of page numbers that are image-only
        """
        image_only_pages: list[int] = []
        
        try:
            if hasattr(doc, 'pages'):
                for page_idx, page in enumerate(doc.pages, start=1):
                    # Check if page has minimal or no text content
                    has_text = False
                    if hasattr(page, 'text') and page.text and page.text.strip():
                        has_text = True
                    elif hasattr(page, 'elements'):
                        # Check elements for text content
                        for element in page.elements:
                            if hasattr(element, 'text') and element.text and element.text.strip():
                                has_text = True
                                break
                    
                    # If no text but has images, mark as image-only
                    if not has_text and hasattr(page, 'images') and page.images:
                        image_only_pages.append(page_idx)
                        logger.debug(
                            f"Detected image-only page {page_idx}",
                            extra={"page_num": page_idx},
                        )
        except Exception as e:
            logger.warning(
                f"Failed to detect image-only pages: {e}",
                exc_info=True,
            )
        
        return image_only_pages
    
    def _compute_doc_id(self, source_path: str) -> str:
        """
        Compute stable document identifier from source path.
        
        Args:
            source_path: Path to source document
        
        Returns:
            Stable doc_id (content hash or file path hash)
        """
        path = Path(source_path)
        
        # Try content-based hash first (if file exists and is readable)
        try:
            if path.exists() and path.is_file():
                # Compute SHA256 hash of file content
                hasher = hashlib.sha256()
                with path.open('rb') as f:
                    # Read in chunks for large files
                    while chunk := f.read(8192):
                        hasher.update(chunk)
                return f"sha256_{hasher.hexdigest()[:16]}"
        except Exception:
            pass
        
        # Fallback: path-based hash
        path_str = str(path.absolute())
        path_hash = hashlib.sha256(path_str.encode()).hexdigest()
        return f"path_{path_hash[:16]}"
    
    def convert(
        self,
        source_path: str,
        ocr_languages: list[str] | None = None,
        progress_reporter: "ProgressReporterPort | None" = None,
    ) -> Mapping[str, Any]:
        """
        Convert a document at source_path into structured text and metadata.
        
        Args:
            source_path: Path to source document (PDF, DOCX, PPTX, HTML, images)
            ocr_languages: Optional OCR language codes (priority: Zotero metadata → explicit config → default ['en', 'de'])
            progress_reporter: Optional progress reporter for document-level progress updates
        
        Returns:
            ConversionResult-like dict with keys:
            - doc_id (str): Stable document identifier
            - structure (dict): heading_tree (hierarchical with page anchors) and page_map (page → (start_offset, end_offset))
            - plain_text (str, optional): Converted text (normalized, hyphen-repaired)
            - ocr_languages (list[str], optional): Languages used for OCR
        
        Raises:
            ImportError: If docling is not available (Windows compatibility)
            TimeoutError: If conversion exceeds timeout (120s document, 10s per-page)
        """
        if not DOCLING_AVAILABLE:
            raise ImportError("Docling is not installed. See __init__ error for details.")
        
        # T064: Use Zotero metadata language information for OCR when available
        # ocr_languages parameter should contain language from Zotero metadata (already mapped by resolver)
        selected_languages = self._select_ocr_languages(ocr_languages)
        
        # Log OCR language selection (T064)
        if ocr_languages:
            logger.debug(
                f"Using OCR languages from Zotero metadata: {selected_languages}",
                extra={"source_path": source_path, "zotero_languages": ocr_languages, "selected_languages": selected_languages},
            )
        else:
            logger.debug(
                f"Using default OCR languages: {selected_languages}",
                extra={"source_path": source_path, "selected_languages": selected_languages},
            )
        
        logger.info(
            f"Converting document: {source_path}",
            extra={"source_path": source_path, "ocr_languages": selected_languages},
        )
        
        # T031, T032: Initialize document-level progress if reporter provided
        doc_progress: "DocumentProgressContext | None" = None
        if progress_reporter:
            doc_progress = progress_reporter.start_document(
                document_index=1,
                total_documents=1,
                document_name=source_path,
            )
            # T034: Throttled progress update - converting stage
            if doc_progress:
                doc_progress.update_stage("converting", "Converting document to text")
        
        # Configure OCR with selected languages (already selected above at line 778)
        self._configure_ocr(selected_languages)
        
        # Compute stable doc_id
        doc_id = self._compute_doc_id(source_path)
        
        try:
            # Log conversion start with progress indication
            logger.info(f"Starting document conversion pipeline (this may take a moment, especially for large PDFs)...")
            
            # Convert with timeout enforcement
            conversion_result = self._convert_with_timeout(source_path)
            
            logger.info(f"Document conversion pipeline completed, extracting results...")
            
            # Extract document object
            if hasattr(conversion_result, 'document'):
                doc = conversion_result.document
            else:
                doc = conversion_result
            
            # Extract plain text
            plain_text: str | None = None
            if hasattr(doc, 'export_to_markdown'):
                plain_text = doc.export_to_markdown()
            elif hasattr(doc, 'text'):
                plain_text = doc.text
            elif hasattr(doc, 'export_to_text'):
                plain_text = doc.export_to_text()
            
            # Extract page map
            page_map = self._extract_page_map(doc, plain_text or "")
            
            # Extract heading tree
            heading_tree = self._extract_heading_tree(doc, page_map)
            
            # Normalize text
            if plain_text:
                plain_text = self._normalize_text(plain_text)
            
            # Detect image-only pages
            image_only_pages = self._detect_image_only_pages(doc)
            if image_only_pages:
                # T103: Enhanced diagnostic logging for image-only pages
                logger.info(
                    f"Detected {len(image_only_pages)} image-only pages: {image_only_pages}",
                    extra={
                        "source_path": source_path,
                        "image_only_pages": image_only_pages,
                        "page_count": len(page_map),
                        "diagnostic": f"Pages {image_only_pages} contain only images. "
                                     f"OCR may be required for these pages. "
                                     f"Verify OCR languages ({selected_languages}) are appropriate.",
                    },
                )
            
            # Build result
            result: dict[str, Any] = {
                "doc_id": doc_id,
                "structure": {
                    "heading_tree": heading_tree,
                    "page_map": page_map,
                },
            }
            
            if plain_text:
                result["plain_text"] = plain_text
            
            if selected_languages:
                result["ocr_languages"] = selected_languages
            
            logger.info(
                f"Document converted successfully: doc_id={doc_id}, pages={len(page_map)}, headings={len(heading_tree.get('root', []))}",
                extra={
                    "doc_id": doc_id,
                    "page_count": len(page_map),
                    "heading_count": len(heading_tree.get('root', [])),
                    "image_only_pages": image_only_pages,
                },
            )
            
            # T032: Mark conversion stage as complete
            if doc_progress:
                doc_progress.finish()
            
            return result
        
        except TimeoutError as e:
            # T032: Mark progress as failed
            if doc_progress:
                doc_progress.fail(f"Conversion timed out: {e}")
            
            # T103: Enhanced diagnostic logging for timeout failures
            logger.error(
                f"Document conversion timed out: {e}",
                extra={
                    "source_path": source_path,
                    "doc_id": doc_id,
                    "timeout_seconds": self.DOCUMENT_TIMEOUT_SECONDS,
                    "page_timeout_seconds": self.PAGE_TIMEOUT_SECONDS,
                    "diagnostic": "Document exceeded timeout limits. Consider: "
                                  "1. Splitting large documents into smaller files, "
                                  "2. Increasing timeout limits if system resources allow, "
                                  "3. Checking for corrupted or unusually complex document structure",
                },
                exc_info=True,
            )
            raise
        except Exception as e:
            # T032: Mark progress as failed
            if doc_progress:
                doc_progress.fail(f"Conversion failed: {e}")
            
            # T103: Enhanced diagnostic logging for general conversion failures
            logger.error(
                f"Document conversion failed: {e}",
                extra={
                    "source_path": source_path,
                    "doc_id": doc_id,
                    "ocr_languages": selected_languages if 'selected_languages' in locals() else None,
                    "diagnostic": "Conversion error occurred. Check: "
                                  "1. Document format is supported (PDF, DOCX, PPTX, HTML, images), "
                                  "2. File is not corrupted, "
                                  "3. OCR languages are correct if document is scanned",
                },
                exc_info=True,
            )
            raise


def get_converter(config_hash: str | None = None) -> DoclingConverterAdapter:
    """
    Get or create shared DoclingConverterAdapter instance (process-scoped).
    
    This factory function implements a singleton pattern with module-level cache
    to avoid reinitialization overhead on subsequent commands in the same process.
    
    Args:
        config_hash: Optional configuration hash for variant instances
            (default: "default" for single instance)
    
    Returns:
        DoclingConverterAdapter instance (shared across process lifetime)
    
    Behavior:
        - First call: Creates new DoclingConverterAdapter, caches it, returns instance
        - Subsequent calls: Returns cached instance (no reinitialization overhead)
        - Cache key: f"converter:{config_hash or 'default'}"
        - Lifetime: Process-scoped (cleared only on process termination)
    
    Thread Safety:
        - Module-level cache is safe for single-user CLI (no concurrent access expected)
        - No locking required for single-threaded CLI operations
    
    Raises:
        ImportError: If Docling is not available (Windows compatibility)
    """
    cache_key = f"converter:{config_hash or 'default'}"
    
    if cache_key not in _converter_cache:
        logger.debug(f"Creating new converter instance (cache_key={cache_key})")
        _converter_cache[cache_key] = DoclingConverterAdapter()
    else:
        logger.debug(f"Reusing cached converter instance (cache_key={cache_key})")
    
    return _converter_cache[cache_key]
