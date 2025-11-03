"""Performance tests for collection browsing operations (T128)."""

from __future__ import annotations

import pytest

# Performance test: Collection browsing should be < 2 seconds (SC-001)
# This test may be skipped if Zotero database is not available


@pytest.mark.skip(reason="Requires Zotero database accessible")
def test_collection_listing_performance():
    """
    Performance test for collection listing operations.

    SC-001: Collection browsing: < 2 seconds using local DB.

    This test requires:
    - Local Zotero database accessible
    - LocalZoteroDbAdapter configured
    """
    import time

    # TODO: Create adapter with real database
    # adapter = LocalZoteroDbAdapter()

    start_time = time.time()
    # collections = adapter.list_collections()
    elapsed = time.time() - start_time

    # Assert performance target
    assert elapsed < 2.0, f"Collection listing took {elapsed:.3f}s, expected < 2.0s"

    pytest.skip("Test infrastructure not yet implemented")


@pytest.mark.skip(reason="Requires Zotero database accessible")
def test_collection_items_browsing_performance():
    """
    Performance test for browsing collection items.

    Similar to test_collection_listing_performance but tests get_collection_items().
    """
    pytest.skip("Test infrastructure not yet implemented")


@pytest.mark.skip(reason="Requires Zotero database accessible")
def test_tags_listing_performance():
    """
    Performance test for listing tags with usage counts.

    Tests list_tags() performance.
    """
    pytest.skip("Test infrastructure not yet implemented")
