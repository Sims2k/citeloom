# Zotero Old Schema Fallback Implementation

**Date**: 2025-11-04  
**Reference**: [zotero-mcp implementation](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py)

## Problem

After updating Zotero to version 7.0.27, the database schema was not automatically migrated. The system only supported the new schema (Zotero 5+) which uses the `items.data` column with JSON metadata. This meant the system couldn't read items from the database until the migration completed.

## Solution

Implemented old schema fallback that automatically detects and uses the old schema (`itemData` table) when the new schema is not available. This allows the system to work with Zotero databases before migration.

## Implementation Details

### Schema Detection

The system now checks:
1. **New Schema**: `items.data` column exists (Zotero 5+)
2. **Old Schema**: `itemData` table exists (Zotero < 5.0 or pre-migration)

### Old Schema Query Pattern

The old schema uses normalized tables:
- `itemData` - Links items to field values (itemID, fieldID, valueID)
- `itemDataValues` - Stores actual field values
- `fields` - Maps field names to fieldIDs
- `itemTypes` - Maps item type IDs to names
- `itemCreators` - Links items to creators
- `creators` - Creator information (firstName, lastName)
- `itemTags` - Links items to tags
- `tags` - Tag names

### Key Methods

#### `_get_collection_items_old_schema()`

Queries items from a collection using old schema:

```sql
SELECT 
    i.itemID,
    i.key,
    i.itemTypeID,
    it.typeName as item_type,
    title_val.value as title,
    date_val.value as date,
    doi_val.value as doi
FROM items i
JOIN collectionItems ci ON i.itemID = ci.itemID
JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
-- Get title (fieldID = 1)
LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
-- Get date (fieldID = 14)
LEFT JOIN itemData date_data ON i.itemID = date_data.itemID AND date_data.fieldID = 14
LEFT JOIN itemDataValues date_val ON date_data.valueID = date_val.valueID
-- Get DOI via fields table
LEFT JOIN fields doi_f ON doi_f.fieldName = 'DOI'
LEFT JOIN itemData doi_data ON i.itemID = doi_data.itemID AND doi_data.fieldID = doi_f.fieldID
LEFT JOIN itemDataValues doi_val ON doi_data.valueID = doi_val.valueID
WHERE ci.collectionID = ?
  AND it.typeName NOT IN ('attachment', 'note', 'annotation')
```

#### `_get_item_metadata_old_schema()`

Retrieves full metadata for a single item, including:
- Title, date, DOI
- Creators (authors) with firstName/lastName
- Tags
- Year extraction from date

#### `_get_recent_items_old_schema()`

Gets recently added items sorted by `dateAdded`:

```sql
SELECT 
    i.itemID,
    i.key,
    i.itemTypeID,
    it.typeName as item_type,
    i.dateAdded,
    title_val.value as title,
    date_val.value as date
FROM items i
JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
-- Get title (fieldID = 1)
LEFT JOIN itemData title_data ON i.itemID = title_data.itemID AND title_data.fieldID = 1
LEFT JOIN itemDataValues title_val ON title_data.valueID = title_val.valueID
-- Get date (fieldID = 14)
LEFT JOIN itemData date_data ON i.itemID = date_data.itemID AND date_data.fieldID = 14
LEFT JOIN itemDataValues date_val ON date_data.valueID = date_val.valueID
WHERE it.typeName NOT IN ('attachment', 'note', 'annotation')
ORDER BY i.dateAdded DESC
LIMIT ?
```

### Field ID Reference

Common field IDs used:
- `1` - Title
- `2` - Abstract
- `14` - Date
- `16` - Extra
- `DOI` - Via `fields` table lookup

### Output Format

The old schema methods return the same format as the new schema and web API:
```python
{
    "key": "item_key",
    "data": {
        "title": "...",
        "itemType": "book",
        "date": "2025",
        "creators": [
            {"firstName": "John", "lastName": "Doe"}
        ],
        "tags": ["tag1", "tag2"],
        "DOI": "...",
    }
}
```

## Benefits

1. **Immediate Functionality**: Works with databases before migration
2. **Transparent**: Automatically falls back, no user intervention needed
3. **Consistent API**: Same output format regardless of schema version
4. **Graceful Degradation**: Still works if migration hasn't completed

## Testing

Tested with:
- ✅ Zotero 7.0.27 installed
- ✅ Database not yet migrated (old schema)
- ✅ Collection browsing works
- ✅ Recent items works
- ✅ Item metadata retrieval works
- ✅ CLI commands function correctly

## Files Modified

1. `src/infrastructure/adapters/zotero_local_db.py`
   - Added `_check_has_item_data_table()` method
   - Added `_get_collection_items_old_schema()` method
   - Added `_get_item_metadata_old_schema()` method
   - Added `_get_recent_items_old_schema()` method
   - Updated `get_collection_items()` to use old schema fallback
   - Updated `get_item_metadata()` to use old schema fallback
   - Updated `get_recent_items()` to use old schema fallback
   - Updated `get_item_attachments()` to support old schema

2. `src/infrastructure/cli/commands/ingest.py`
   - Updated collection resolution to prefer local adapter for collection lookup

## Limitations

1. **Fulltext**: Fulltext extraction still requires migrated database (needs `fulltext` table which is only available after migration)
2. **Performance**: Old schema queries are slower due to multiple JOINs
3. **Field Coverage**: Only common fields are extracted (title, date, DOI, creators, tags)

## Future Improvements

1. Add more field extractions (abstract, extra, etc.)
2. Cache field ID mappings for performance
3. Support fulltext extraction from old schema (if possible)

## References

- [zotero-mcp local_db.py](https://github.com/54yyyu/zotero-mcp/blob/main/src/zotero_mcp/local_db.py)
- [Zotero Database Schema Documentation](https://www.zotero.org/support/kb/corrupted_database)

