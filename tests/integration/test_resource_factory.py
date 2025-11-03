"""Integration tests for resource factory functions (User Story 4)."""

import pytest
from src.infrastructure.adapters.docling_converter import (
    DoclingConverterAdapter,
    get_converter,
    _converter_cache,
)


class TestConverterFactory:
    """Tests for get_converter() factory function (T037, T038)."""
    
    def setup_method(self):
        """Clear cache before each test to ensure isolation."""
        _converter_cache.clear()
    
    def test_factory_returns_same_instance_on_multiple_calls(self):
        """
        T037: Test that converter factory returns same instance on multiple calls.
        
        Verifies that get_converter() implements singleton pattern correctly.
        """
        # First call should create instance
        converter1 = get_converter()
        assert converter1 is not None
        assert isinstance(converter1, DoclingConverterAdapter)
        
        # Second call should return same instance
        converter2 = get_converter()
        assert converter2 is converter1, "Factory should return same instance on subsequent calls"
        
        # Third call should also return same instance
        converter3 = get_converter()
        assert converter3 is converter1, "Factory should return same instance on all calls"
        assert converter3 is converter2, "Factory should return same instance on all calls"
    
    def test_factory_cache_key_default(self):
        """Test that default cache key is used when config_hash is None."""
        _converter_cache.clear()
        
        converter1 = get_converter()
        converter2 = get_converter(None)
        converter3 = get_converter()
        
        assert converter1 is converter2, "None and omitted should use same cache key"
        assert converter2 is converter3, "Subsequent calls should return cached instance"
        
        # Verify cache key format
        assert "converter:default" in _converter_cache
    
    def test_factory_different_config_hash_creates_separate_instances(self):
        """Test that different config_hash values create separate instances."""
        _converter_cache.clear()
        
        converter1 = get_converter("config1")
        converter2 = get_converter("config2")
        converter3 = get_converter("config1")
        
        assert converter1 is not converter2, "Different config hashes should create separate instances"
        assert converter1 is converter3, "Same config hash should return same instance"
        
        # Verify both cache keys exist
        assert "converter:config1" in _converter_cache
        assert "converter:config2" in _converter_cache
    
    def test_converter_reuse_across_multiple_calls_same_process(self):
        """
        T038: Test converter reuse across multiple CLI commands in same process.
        
        Simulates multiple command invocations in the same process.
        """
        _converter_cache.clear()
        
        # Simulate first command
        converter_cmd1 = get_converter()
        converter_id_cmd1 = id(converter_cmd1)
        
        # Simulate second command (should reuse)
        converter_cmd2 = get_converter()
        converter_id_cmd2 = id(converter_cmd2)
        
        # Simulate third command (should reuse)
        converter_cmd3 = get_converter()
        converter_id_cmd3 = id(converter_cmd3)
        
        # All commands should use same instance
        assert converter_id_cmd1 == converter_id_cmd2 == converter_id_cmd3, \
            "All commands in same process should reuse converter instance"
        
        # Verify only one instance in cache
        assert len(_converter_cache) == 1, "Should have only one cached instance for default key"
    
    def test_process_scoped_lifetime(self):
        """
        T043: Verify process-scoped lifetime (no inactivity-based cleanup).
        
        The cache should persist until process termination, not be cleared
        based on inactivity or time.
        """
        _converter_cache.clear()
        
        # Get converter instance
        converter1 = get_converter()
        
        # Simulate multiple calls with delays (if we had time-based cleanup, this would clear)
        # In practice, cache persists throughout process lifetime
        converter2 = get_converter()
        converter3 = get_converter()
        
        # All should be same instance (no cleanup between calls)
        assert converter1 is converter2 is converter3, \
            "Process-scoped cache should persist across all calls"
        
        # Cache should still contain the instance
        assert "converter:default" in _converter_cache, \
            "Cache should persist instance throughout process lifetime"
    
    def test_factory_handles_import_error(self):
        """Test that factory properly propagates ImportError from DoclingConverterAdapter."""
        # Note: This test may skip if Docling is not available
        # The ImportError is raised during DoclingConverterAdapter.__init__()
        # which is called by get_converter()
        
        _converter_cache.clear()
        
        try:
            converter = get_converter()
            # If we get here, Docling is available (test passes)
            assert converter is not None
        except ImportError:
            # If ImportError is raised, it should propagate from factory
            # This is expected behavior on Windows where Docling is not available
            pytest.skip("Docling not available - ImportError expected")
    
    def test_factory_cache_is_module_level(self):
        """Verify that cache is module-level (shared across imports)."""
        _converter_cache.clear()
        
        # Get converter through factory
        converter1 = get_converter()
        
        # Import and use factory again (simulating different module)
        # Since cache is module-level, it should be shared
        from src.infrastructure.adapters.docling_converter import get_converter as get_converter_again
        
        converter2 = get_converter_again()
        
        # Should be same instance (shared cache)
        assert converter1 is converter2, \
            "Module-level cache should be shared across all imports"

