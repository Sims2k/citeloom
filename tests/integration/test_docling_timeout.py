"""Integration tests for Docling converter timeout enforcement (T061)."""

import pytest
import sys
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.infrastructure.adapters.docling_converter import (
    DoclingConverterAdapter,
    TimeoutError,
    DOCLING_AVAILABLE,
)


@pytest.mark.skipif(not DOCLING_AVAILABLE, reason="Docling not available")
class TestDoclingTimeout:
    """Test timeout enforcement for document conversion (T061)."""
    
    def test_timeout_enforcement_windows_and_unix(self):
        """
        Verify timeout enforcement works on all platforms (Windows, Linux, macOS).
        
        This test verifies that ThreadPoolExecutor-based timeout works consistently
        across platforms, unlike the previous signal.SIGALRM approach which only
        worked on Unix systems.
        """
        # Create converter instance
        converter = DoclingConverterAdapter()
        
        # Create a mock converter that will hang indefinitely
        # This simulates a document that takes too long to convert
        original_convert = converter.converter.convert
        
        def slow_convert(path: str):
            """Simulate a conversion that takes longer than timeout."""
            time.sleep(converter.DOCUMENT_TIMEOUT_SECONDS + 5)  # Exceed timeout
            return original_convert(path)
        
        # Patch the converter to simulate slow conversion
        converter.converter.convert = Mock(side_effect=slow_convert)
        
        # Create a dummy file path for testing
        test_file = Path(__file__).parent / "test_data" / "sample.pdf"
        
        # If test file doesn't exist, create a dummy path
        if not test_file.exists():
            test_file = Path("/tmp/test.pdf") if sys.platform != "win32" else Path("C:\\temp\\test.pdf")
        
        # Verify that timeout is raised
        with pytest.raises(TimeoutError) as exc_info:
            start_time = time.time()
            converter._convert_with_timeout(str(test_file))
            elapsed = time.time() - start_time
            
            # Verify timeout occurred within reasonable time (not waiting full timeout + 5s)
            # Should timeout after approximately DOCUMENT_TIMEOUT_SECONDS
            assert elapsed < converter.DOCUMENT_TIMEOUT_SECONDS + 10, \
                f"Timeout should occur within {converter.DOCUMENT_TIMEOUT_SECONDS + 10}s, but took {elapsed}s"
        
        # Verify error message contains timeout information
        error_msg = str(exc_info.value)
        assert "timeout" in error_msg.lower() or "exceeded" in error_msg.lower()
        assert str(converter.DOCUMENT_TIMEOUT_SECONDS) in error_msg
    
    def test_timeout_works_on_windows(self):
        """
        Specifically verify timeout works on Windows platform (T061).
        
        This test ensures Windows users have timeout protection, which was
        previously missing with signal.SIGALRM approach.
        """
        if sys.platform != "win32":
            pytest.skip("This test is specifically for Windows platform")
        
        converter = DoclingConverterAdapter()
        
        # Mock converter to hang
        def hanging_convert(path: str):
            """Simulate hanging conversion."""
            while True:
                time.sleep(1)
        
        converter.converter.convert = Mock(side_effect=hanging_convert)
        
        test_file = Path("C:\\temp\\test.pdf")
        
        # Verify timeout is raised on Windows
        with pytest.raises(TimeoutError):
            start_time = time.time()
            converter._convert_with_timeout(str(test_file))
            elapsed = time.time() - start_time
            
            # Should timeout, not hang indefinitely
            assert elapsed < converter.DOCUMENT_TIMEOUT_SECONDS + 5, \
                f"Timeout should occur on Windows, but operation took {elapsed}s"
    
    def test_successful_conversion_within_timeout(self):
        """Verify that successful conversions complete without timeout."""
        converter = DoclingConverterAdapter()
        
        # Create a mock converter that completes quickly
        def fast_convert(path: str):
            """Simulate fast conversion."""
            # Return a minimal document structure
            mock_doc = Mock()
            mock_doc.export_to_markdown = Mock(return_value="Test content")
            mock_result = Mock()
            mock_result.document = mock_doc
            return mock_result
        
        converter.converter.convert = Mock(side_effect=fast_convert)
        
        test_file = Path(__file__).parent / "test_data" / "sample.pdf"
        if not test_file.exists():
            test_file = Path("/tmp/test.pdf") if sys.platform != "win32" else Path("C:\\temp\\test.pdf")
        
        # Should complete without timeout
        start_time = time.time()
        result = converter._convert_with_timeout(str(test_file))
        elapsed = time.time() - start_time
        
        # Should complete quickly
        assert elapsed < 1.0, f"Fast conversion should complete in <1s, took {elapsed}s"
        assert result is not None


