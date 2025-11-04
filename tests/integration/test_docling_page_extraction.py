"""Integration tests for Docling page map extraction (T018)."""

from __future__ import annotations

import pytest
from pathlib import Path
from typing import Any

from src.infrastructure.adapters.docling_converter import DoclingConverterAdapter


@pytest.fixture
def docling_available():
    """Skip tests if Docling is not available."""
    try:
        converter = DoclingConverterAdapter()
        return converter
    except ImportError:
        pytest.skip("Docling not available (Windows compatibility - use WSL/Docker)")


@pytest.fixture
def sample_multi_page_pdf():
    """Get path to a multi-page PDF file if available."""
    # Try common test PDF locations
    possible_paths = [
        Path("assets/raw/Sakai - 2025 - AI Agent Architecture Mapping Domain, Agent, and Orchestration to Clean Architecture.pdf"),
        Path("assets/raw/test_multi_page.pdf"),
        Path("tests/fixtures/multi_page.pdf"),
    ]
    
    for pdf_path in possible_paths:
        if pdf_path.exists():
            return str(pdf_path.absolute())
    return None


class TestDoclingPageExtraction:
    """Tests for page map extraction with multi-page documents (T018)."""
    
    def test_page_map_extraction_multi_page_document(self, docling_available, sample_multi_page_pdf):
        """
        Test that page map extraction correctly identifies multiple pages in a multi-page document.
        
        T018: Add test for page map extraction with multi-page document.
        
        Success criteria:
        - page_map contains more than 1 page
        - Each page number maps to a valid (start_offset, end_offset) tuple
        - Offsets are non-overlapping and cover the full document text
        - Page numbers are sequential (1, 2, 3, ...)
        """
        if sample_multi_page_pdf is None:
            pytest.skip("Multi-page PDF not available - requires actual PDF file with 2+ pages")
        
        converter = docling_available
        result = converter.convert(sample_multi_page_pdf)
        
        # Verify conversion result structure
        assert "structure" in result, "Conversion result should contain structure"
        structure = result.get("structure", {})
        assert "page_map" in structure, "Structure should contain page_map"
        
        page_map = structure.get("page_map", {})
        assert isinstance(page_map, dict), "page_map should be a dictionary"
        
        # T018: Verify multi-page extraction
        assert len(page_map) > 1, f"Multi-page document should have more than 1 page, got {len(page_map)} pages"
        
        # Verify page_map structure
        page_numbers = sorted(page_map.keys())
        assert len(page_numbers) > 1, "Should have multiple pages"
        assert page_numbers[0] == 1, "Page numbering should start at 1"
        
        # Verify offsets are valid
        plain_text = result.get("plain_text", "")
        if plain_text:
            for page_num in page_numbers:
                offset_tuple = page_map[page_num]
                assert isinstance(offset_tuple, tuple), f"Page {page_num} offset should be a tuple"
                assert len(offset_tuple) == 2, f"Page {page_num} offset tuple should have 2 elements (start, end)"
                
                start_offset, end_offset = offset_tuple
                assert isinstance(start_offset, int), f"Page {page_num} start offset should be int"
                assert isinstance(end_offset, int), f"Page {page_num} end offset should be int"
                assert start_offset >= 0, f"Page {page_num} start offset should be non-negative"
                assert end_offset > start_offset, f"Page {page_num} end offset should be greater than start offset"
                assert end_offset <= len(plain_text), f"Page {page_num} end offset should not exceed text length"
        
        # Verify pages are sequential
        for i in range(len(page_numbers) - 1):
            assert page_numbers[i + 1] == page_numbers[i] + 1, \
                f"Page numbers should be sequential, got gap between {page_numbers[i]} and {page_numbers[i + 1]}"
        
        # Verify offsets are non-overlapping and cover full text (approximately)
        if plain_text and len(page_map) > 1:
            sorted_pages = sorted(page_map.items())
            text_length = len(plain_text)
            
            # Check that offsets cover the text (allow some tolerance for whitespace/formatting)
            first_start = sorted_pages[0][1][0]
            last_end = sorted_pages[-1][1][1]
            
            assert first_start == 0 or abs(first_start) < 100, \
                f"First page should start near beginning, got start={first_start}"
            assert last_end >= text_length * 0.9, \
                f"Last page should end near text end, got end={last_end} vs text_length={text_length}"
            
            # Check for reasonable gaps/overlaps (pages should be mostly non-overlapping)
            for i in range(len(sorted_pages) - 1):
                current_end = sorted_pages[i][1][1]
                next_start = sorted_pages[i + 1][1][0]
                
                # Allow small overlap (up to 100 chars) or small gap (up to 200 chars)
                # This accounts for page boundaries that may not align perfectly
                gap = next_start - current_end
                assert -100 <= gap <= 200, \
                    f"Pages {sorted_pages[i][0]} and {sorted_pages[i + 1][0]} have unusual gap/overlap: {gap}"
        
        # Success: Multi-page document correctly extracted with multiple pages
        assert len(page_map) >= 2, f"Expected at least 2 pages, got {len(page_map)}"

