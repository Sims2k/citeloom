# Zotero Integration - Additional Test Cases & Edge Cases

## Testing Plan: Local SQLite vs Web API Comparison

This document outlines additional use cases and edge cases to comprehensively test Zotero integration, comparing local SQLite database access with Web API access.

---

## Performance Comparison Tests

### Test Case 1: List Collections Performance
**Objective**: Compare execution time and API calls between local SQLite and Web API

**Local SQLite Test**:
```bash
# Configure local database
# In citeloom.toml:
[zotero]
db_path = "C:/Users/YourName/AppData/Roaming/Zotero/Profiles/xxxxx/zotero/zotero.sqlite"
storage_dir = "C:/Users/YourName/AppData/Roaming/Zotero/Profiles/xxxxx/zotero/storage"

# Test command
time uv run citeloom zotero list-collections
```

**Web API Test**:
```bash
# Ensure ZOTERO_LOCAL=false or not set
# Test command
time uv run citeloom zotero list-collections
```

**Metrics to Compare**:
- Total execution time
- Number of database queries / API calls
- Memory usage
- CPU usage

**Expected Results**:
- Local SQLite: < 1 second (single query)
- Web API: 15-20 seconds (multiple API calls)
- Local SQLite should be 10-20x faster

---

### Test Case 2: Browse Collection Performance (Small Collection)
**Objective**: Compare performance for small collections (5-10 items)

**Test Setup**:
- Collection with 5-10 items
- Some items with attachments, some without
- Mix of item types (journal articles, books, web pages)

**Commands**:
```bash
# Local SQLite
uv run citeloom zotero browse-collection --collection "Test Collection" --limit 10

# Web API
uv run citeloom zotero browse-collection --collection "Test Collection" --limit 10
```

**Metrics**:
- Time to first item displayed
- Total execution time
- Number of queries/calls
- Accuracy of metadata displayed

**Edge Cases to Test**:
- Items with no attachments
- Items with multiple attachments
- Items with missing metadata fields
- Items with special characters in titles/authors

---

### Test Case 3: Browse Collection Performance (Large Collection)
**Objective**: Compare performance for large collections (100+ items)

**Test Setup**:
- Collection with 100+ items
- Various item types
- Mixed attachment status

**Commands**:
```bash
# Test with different limits
uv run citeloom zotero browse-collection --collection "Large Collection" --limit 20
uv run citeloom zotero browse-collection --collection "Large Collection" --limit 50
uv run citeloom zotero browse-collection --collection "Large Collection" --limit 100
```

**Metrics**:
- Time per item displayed
- Memory usage with large result sets
- Query performance degradation

**Expected**:
- Local SQLite: Linear scaling, fast queries
- Web API: Significant slowdown with pagination

---

## Edge Cases: Collection Resolution

### Test Case 4: Collection Name Ambiguity
**Objective**: Test behavior when multiple collections have similar names

**Test Setup**:
- Create collections: "Clean Code", "Clean Code - Practice", "Clean Code Architecture"
- Create subcollection: "AI Engineering > Architecture > Clean Code"

**Test Scenarios**:

**4a. Exact Match Priority**:
```bash
uv run citeloom zotero browse-collection --collection "Clean Code"
```
- Should prioritize exact match over partial match
- Should handle subcollections correctly

**4b. Partial Match**:
```bash
uv run citeloom zotero browse-collection --collection "Clean"
```
- Should return multiple matches or most specific match
- Should show hierarchy context

**4c. Case Sensitivity**:
```bash
uv run citeloom zotero browse-collection --collection "clean code"
uv run citeloom zotero browse-collection --collection "CLEAN CODE"
```
- Both should work (case-insensitive matching)

**4d. Collection Key vs Name**:
```bash
# By key (direct lookup)
uv run citeloom zotero browse-collection --collection "6EAXG8AV"

# By name (requires search)
uv run citeloom zotero browse-collection --collection "Clean Code"
```
- Key lookup should be faster (no search needed)
- Name lookup should find correct collection

**Compare Results**:
- Local SQLite: Uses SQL LIKE queries
- Web API: Fetches all collections, searches in memory
- Verify both return same results

---

### Test Case 5: Subcollection Resolution
**Objective**: Test subcollection name resolution and hierarchy

**Test Setup**:
- Parent: "AI Engineering" (key: HIVKTPGI)
- Sub: "Architecture" (key: 8C7HRXTA, parent: HIVKTPGI)
- Sub-sub: "Clean Code" (key: 6EAXG8AV, parent: 8C7HRXTA)

**Test Scenarios**:

**5a. Browse Parent with Subcollections**:
```bash
uv run citeloom zotero browse-collection --collection "AI Engineering" --subcollections
```
- Should include items from all subcollections
- Should show correct item counts

**5b. Browse Subcollection Directly**:
```bash
uv run citeloom zotero browse-collection --collection "Clean Code"
```
- Should find subcollection even though it's nested
- Should handle parent context

**5c. Ambiguous Subcollection Names**:
```bash
# If "Clean Code" exists as both top-level and subcollection
uv run citeloom zotero browse-collection --collection "Clean Code"
```
- Should return the correct one (or show disambiguation)

**5d. Deep Nesting (3+ levels)**:
```bash
# Test with deeply nested subcollections
uv run citeloom zotero browse-collection --collection "Deep Collection" --subcollections
```
- Should handle recursion correctly
- Should not cause stack overflow or infinite loops

---

## Edge Cases: Metadata Handling

### Test Case 6: Creator Format Variations
**Objective**: Test handling of different creator name formats

**Test Items**:
1. Creator with `firstName` and `lastName`:
   ```json
   {"firstName": "John", "lastName": "Doe", "creatorType": "author"}
   ```

2. Creator with single `name` field:
   ```json
   {"name": "John Doe", "creatorType": "author"}
   ```

3. Creator with empty fields:
   ```json
   {"firstName": "", "lastName": "", "name": "", "creatorType": "author"}
   ```

4. Multiple creators (some with firstName/lastName, some with name):
   ```json
   [
     {"firstName": "John", "lastName": "Doe"},
     {"name": "Jane Smith"},
     {"firstName": "", "lastName": "Unknown"}
   ]
   ```

**Test Commands**:
```bash
uv run citeloom zotero browse-collection --collection "Metadata Test" --limit 20
```

**Verify**:
- All creator formats display correctly
- No missing authors
- Proper formatting (commas, "et al." for many authors)
- Local SQLite and Web API show same results

---

### Test Case 7: Missing or Incomplete Metadata
**Objective**: Test graceful handling of missing metadata fields

**Test Items**:
- Item with no title
- Item with no authors
- Item with no date/year
- Item with no DOI
- Item with empty tags list
- Item with no collections

**Test Commands**:
```bash
uv run citeloom zotero browse-collection --collection "Metadata Edge Cases"
uv run citeloom zotero recent-items --limit 20
```

**Verify**:
- Displays "-" or placeholder text for missing fields
- Doesn't crash on null/missing values
- Handles gracefully in both adapters

---

### Test Case 8: Special Characters in Metadata
**Objective**: Test handling of special characters, unicode, and encoding

**Test Items**:
- Title with unicode: "Über die Bedeutung"
- Author with accents: "José García"
- Title with special chars: "C++ Best Practices"
- Title with emoji: "📚 Research Methods"
- Title with quotes: "The "Clean" Code"
- Title with HTML entities: "&lt;script&gt;"

**Test Commands**:
```bash
uv run citeloom zotero browse-collection --collection "Special Chars"
uv run citeloom zotero list-collections  # Check collection names too
```

**Verify**:
- Proper encoding/decoding
- Display correctly in terminal
- No encoding errors
- SQLite handles UTF-8 correctly

---

## Edge Cases: Attachments

### Test Case 9: Attachment Resolution
**Objective**: Test attachment path resolution for both imported and linked files

**Test Items**:
- Item with imported PDF (linkMode=0)
- Item with linked PDF (linkMode=1)
- Item with multiple attachments
- Item with no attachments
- Item with non-PDF attachments (should be filtered)

**Local SQLite Test**:
```bash
# Test attachment resolution
uv run citeloom zotero browse-collection --collection "Attachment Test"
```

**Verify**:
- Correctly identifies imported vs linked files
- Resolves paths correctly
- Handles missing files gracefully
- Shows correct attachment counts

**Web API Comparison**:
- Should return same attachment metadata
- Should handle download paths correctly

---

### Test Case 10: Missing Attachment Files
**Objective**: Test handling when attachment files are missing

**Test Setup**:
- Item with attachment in database but file missing from storage
- Item with linked file path that no longer exists

**Test Commands**:
```bash
uv run citeloom zotero browse-collection --collection "Missing Attachments"
```

**Verify**:
- Doesn't crash on missing files
- Shows appropriate warnings/errors
- Continues processing other items
- Web API fallback works correctly

---

## Edge Cases: Tags

### Test Case 11: Tag Usage Counts
**Objective**: Compare tag usage counts between adapters

**Test Commands**:
```bash
# Local SQLite
uv run citeloom zotero list-tags

# Web API
uv run citeloom zotero list-tags
```

**Verify**:
- Local SQLite: Counts from SQL query (accurate)
- Web API: Counts from API response (may differ)
- Tags sorted correctly
- Tag names match exactly

**Edge Cases**:
- Tags with no items (count = 0)
- Tags with special characters
- Tags with spaces
- Hierarchical tags (colons: "Computers / Languages / Python")

---

### Test Case 12: Tag Filtering in Browse
**Objective**: Test tag-based filtering (if implemented in browse)

**Test Items**:
- Items with multiple tags
- Items with no tags
- Items with hierarchical tags

**Future Enhancement Test**:
```bash
# If tag filtering is added to browse-collection
uv run citeloom zotero browse-collection --collection "Test" --tags "Python,AI"
```

---

## Edge Cases: Recent Items

### Test Case 13: Recent Items Consistency
**Objective**: Verify recent items match between adapters

**Test Commands**:
```bash
# Test with different limits
uv run citeloom zotero recent-items --limit 5
uv run citeloom zotero recent-items --limit 10
uv run citeloom zotero recent-items --limit 50
```

**Verify**:
- Same items returned in same order
- Date sorting matches
- Collection names displayed correctly
- Performance comparison (local should be faster)

**Edge Cases**:
- Very recent items (just added)
- Items with same dateAdded timestamp
- Items with invalid dates

---

## Edge Cases: Empty Collections

### Test Case 14: Empty Collection Handling
**Objective**: Test behavior with empty collections

**Test Setup**:
- Collection with 0 items
- Collection with only attachments (no top-level items)
- Collection that was recently cleared

**Test Commands**:
```bash
uv run citeloom zotero browse-collection --collection "Empty Collection"
uv run citeloom zotero list-collections  # Check item count = 0
```

**Verify**:
- Shows "No items found" message
- Doesn't crash
- Item count shows 0
- Handles gracefully

---

## Edge Cases: Large Datasets

### Test Case 15: Large Library Performance
**Objective**: Test performance with very large libraries

**Test Setup**:
- Library with 1000+ items
- Library with 100+ collections
- Library with deeply nested subcollections

**Test Commands**:
```bash
# Test different operations
uv run citeloom zotero list-collections
uv run citeloom zotero list-tags
uv run citeloom zotero recent-items --limit 100
```

**Verify**:
- Performance doesn't degrade significantly
- Memory usage stays reasonable
- Query time stays acceptable
- Compare local vs web performance

---

## Edge Cases: Data Consistency

### Test Case 16: Concurrent Access
**Objective**: Test accessing database while Zotero is running/syncing

**Test Scenarios**:

**16a. Read While Syncing**:
- Start Zotero sync
- Run CiteLoom commands simultaneously
- Verify no locks or conflicts

**16b. Read While Zotero Running**:
- Keep Zotero desktop open
- Run CiteLoom commands
- Verify immutable read-only mode works

**16c. Database Changes**:
- Add item in Zotero
- Immediately query with CiteLoom
- Verify consistency (may see old data due to snapshot)

**Commands**:
```bash
# Run while Zotero is syncing
uv run citeloom zotero list-collections
uv run citeloom zotero browse-collection --collection "Test"
```

**Verify**:
- No database locks
- No errors
- Safe concurrent access
- Immutable snapshot works correctly

---

### Test Case 17: Database Schema Variations
**Objective**: Test with different Zotero database versions

**Test Scenarios**:
- Old Zotero database (older schema)
- New Zotero database (latest schema)
- Database with custom fields
- Database with Better BibTeX data

**Verify**:
- SQL queries work across versions
- Handles missing columns gracefully
- JSON extraction works correctly

---

## Edge Cases: Error Handling

### Test Case 18: Database Not Found
**Objective**: Test error handling when database doesn't exist

**Test Setup**:
- Configure invalid db_path
- Configure non-existent path
- Configure path to non-database file

**Commands**:
```bash
# With invalid db_path in citeloom.toml
uv run citeloom zotero list-collections
```

**Verify**:
- Clear error message
- Graceful fallback to Web API
- Helpful hints for user

---

### Test Case 19: Database Locked
**Objective**: Test handling when database is locked (shouldn't happen with immutable mode, but test edge case)

**Test Scenarios**:
- Database file permissions issue
- Database file corruption
- Database in use by another process (legacy mode)

**Verify**:
- Appropriate error message
- Fallback behavior
- No data corruption

---

### Test Case 20: Web API Failures
**Objective**: Test fallback behavior when Web API fails

**Test Scenarios**:
- Network timeout
- Rate limiting (429 errors)
- API key invalid
- Zotero server down

**Verify**:
- Appropriate error messages
- Retry logic works
- Fallback to local SQLite if available
- Graceful degradation

---

## Comparison Test Matrix

### Test Case 21: Comprehensive Comparison
**Objective**: Run identical commands with both adapters and compare results

**Test Matrix**:

| Operation | Local SQLite | Web API | Expected Match |
|-----------|-------------|---------|----------------|
| `list-collections` | Result set | Result set | ✅ Exact match |
| `browse-collection` | Items, metadata | Items, metadata | ✅ Exact match |
| `recent-items` | Items, order | Items, order | ✅ Exact match |
| `list-tags` | Tags, counts | Tags, counts | ⚠️ Counts may differ |
| Item counts | Count from SQL | Count from API | ✅ Should match |
| Collection hierarchy | Structure | Structure | ✅ Exact match |
| Metadata fields | All fields | All fields | ✅ Exact match |
| Attachment counts | Count from SQL | Count from API | ✅ Should match |

**Automated Test Script**:
```bash
#!/bin/bash
# Compare results between adapters

echo "Testing Local SQLite..."
uv run citeloom zotero list-collections > local_list_collections.txt

echo "Testing Web API..."
# Temporarily disable local adapter
ZOTERO_LOCAL=false uv run citeloom zotero list-collections > web_list_collections.txt

echo "Comparing results..."
diff local_list_collections.txt web_list_collections.txt
```

---

## Performance Benchmark Suite

### Test Case 22: Automated Benchmarking
**Objective**: Create automated performance tests

**Metrics to Measure**:
- Execution time
- Number of queries/calls
- Memory usage
- CPU usage
- Network traffic (for Web API)

**Benchmark Commands**:
```bash
# Create benchmark script
time uv run citeloom zotero list-collections
time uv run citeloom zotero browse-collection --collection "Test" --limit 20
time uv run citeloom zotero recent-items --limit 50
time uv run citeloom zotero list-tags
```

**Compare Results**:
- Generate report comparing local vs web
- Document performance differences
- Identify optimization opportunities

---

## Edge Cases: Collection Filtering

### Test Case 23: Collection Filtering in Batch Import
**Objective**: Test collection filtering logic for batch imports

**Test Scenarios**:
- Import from parent collection only
- Import from parent + subcollections
- Filter by tags
- Exclude specific tags
- Multiple collections

**Commands**:
```bash
# Test filtering logic
uv run citeloom ingest run --project test --zotero-collection "Parent" --include-subcollections
uv run citeloom ingest run --project test --zotero-collection "Parent" --zotero-tags "Python"
```

**Verify**:
- Correct items included
- Subcollection items included when flag set
- Tag filtering works correctly
- Both adapters return same items

---

## Edge Cases: Unicode and Encoding

### Test Case 24: Unicode Handling
**Objective**: Test comprehensive Unicode support

**Test Items**:
- Chinese characters: "中文标题"
- Japanese characters: "日本語のタイトル"
- Arabic: "عنوان بالعربية"
- Cyrillic: "Заголовок на русском"
- Mathematical symbols: "α, β, γ"
- Special punctuation: "¿Qué es esto?"

**Test Commands**:
```bash
uv run citeloom zotero browse-collection --collection "Unicode Test"
uv run citeloom zotero list-collections  # Check collection names too
```

**Verify**:
- Proper encoding in SQLite (UTF-8)
- Proper encoding in Web API responses
- Display correctly in terminal
- No encoding errors in logs

---

## Summary of Test Categories

1. **Performance Comparison** (Tests 1-3)
   - Execution time comparison
   - API call reduction
   - Scalability testing

2. **Collection Resolution** (Tests 4-5)
   - Name ambiguity
   - Subcollection handling
   - Hierarchy traversal

3. **Metadata Handling** (Tests 6-8)
   - Creator formats
   - Missing fields
   - Special characters

4. **Attachments** (Tests 9-10)
   - Path resolution
   - Missing files

5. **Tags** (Tests 11-12)
   - Usage counts
   - Filtering

6. **Recent Items** (Test 13)
   - Consistency
   - Sorting

7. **Empty Collections** (Test 14)
   - Edge case handling

8. **Large Datasets** (Test 15)
   - Performance at scale

9. **Data Consistency** (Tests 16-17)
   - Concurrent access
   - Schema variations

10. **Error Handling** (Tests 18-20)
    - Database errors
    - API failures

11. **Comprehensive Comparison** (Tests 21-22)
    - Result matching
    - Benchmarking

12. **Advanced Features** (Tests 23-24)
    - Filtering
    - Unicode support

---

## Test Execution Priority

### High Priority (Must Test)
- Test Case 1: List Collections Performance
- Test Case 2: Browse Collection Performance (Small)
- Test Case 4: Collection Name Ambiguity
- Test Case 6: Creator Format Variations
- Test Case 21: Comprehensive Comparison

### Medium Priority (Should Test)
- Test Case 3: Large Collection Performance
- Test Case 5: Subcollection Resolution
- Test Case 9: Attachment Resolution
- Test Case 11: Tag Usage Counts
- Test Case 16: Concurrent Access

### Low Priority (Nice to Have)
- Test Case 7-8: Missing/Special Metadata
- Test Case 12-15: Additional Edge Cases
- Test Case 17-20: Error Scenarios
- Test Case 22-24: Advanced Features

---

## Automated Test Script Template

```python
"""Automated test script for comparing Local SQLite vs Web API adapters."""

import subprocess
import time
import json
from pathlib import Path

def run_command(cmd: list[str], env: dict | None = None) -> tuple[str, float]:
    """Run command and return output with timing."""
    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env
    )
    elapsed = time.time() - start
    return result.stdout, elapsed

def test_list_collections():
    """Test list-collections performance."""
    print("Testing list-collections...")
    
    # Local SQLite
    local_out, local_time = run_command([
        "uv", "run", "citeloom", "zotero", "list-collections"
    ])
    
    # Web API
    web_env = {"ZOTERO_LOCAL": "false"}
    web_out, web_time = run_command([
        "uv", "run", "citeloom", "zotero", "list-collections"
    ], env=web_env)
    
    print(f"Local SQLite: {local_time:.2f}s")
    print(f"Web API: {web_time:.2f}s")
    print(f"Speedup: {web_time/local_time:.2f}x")
    
    return {
        "local_time": local_time,
        "web_time": web_time,
        "local_output": local_out,
        "web_output": web_out
    }

# Add more test functions...
```

---

## Expected Outcomes

### Performance Improvements
- Local SQLite should be **10-20x faster** for most operations
- Local SQLite should make **fewer queries** (direct SQL vs multiple API calls)
- Local SQLite should work **offline** (no network required)

### Consistency Requirements
- Both adapters should return **identical results** for same queries
- Metadata should match exactly
- Collection structures should match
- Item counts should match (except for edge cases)

### Issues to Document
- Any differences in results between adapters
- Performance bottlenecks in either adapter
- Missing features in local SQLite adapter
- Edge cases where one adapter fails and other succeeds

