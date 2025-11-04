# Zotero Local Database Access

This guide explains how CiteLoom accesses your Zotero library using the local SQLite database for fast, offline browsing and import operations.

## Overview

CiteLoom can access your Zotero library in two ways:
1. **Local Database** (SQLite): Fast, offline access via direct database queries
2. **Web API**: Remote access via Zotero's REST API (slower, requires internet)

Local database access provides instant browsing capabilities and eliminates API rate limits, making it ideal for large libraries and offline work.

## Platform-Specific Profile Paths

CiteLoom automatically detects your Zotero profile directory based on your operating system:

### Windows
```
%APPDATA%\Zotero\Profiles\<profile-name>\zotero\zotero.sqlite
```

Typical location:
```
C:\Users\<YourName>\AppData\Roaming\Zotero\Profiles\<profile-name>\zotero\zotero.sqlite
```

### macOS
```
~/Library/Application Support/Zotero/Profiles/<profile-name>/zotero/zotero.sqlite
```

Typical location:
```
/Users/<YourName>/Library/Application Support/Zotero/Profiles/<profile-name>/zotero/zotero.sqlite
```

### Linux
```
~/.zotero/zotero/Profiles/<profile-name>/zotero/zotero.sqlite
```

Typical location:
```
/home/<YourName>/.zotero/zotero/Profiles/<profile-name>/zotero/zotero.sqlite
```

## Profile Detection

CiteLoom automatically finds your Zotero profile by:
1. Detecting your operating system
2. Parsing `profiles.ini` in the Zotero profiles directory
3. Selecting the default profile (marked in `profiles.ini`) or the first available profile
4. Constructing the database path: `<profile-dir>/zotero/zotero.sqlite`

## Manual Override

If CiteLoom cannot auto-detect your profile, you can override the database path in `citeloom.toml`:

```toml
[zotero]
db_path = "C:/Users/YourName/AppData/Roaming/Zotero/Profiles/xxxxx.default/zotero/zotero.sqlite"
storage_dir = "C:/Users/YourName/AppData/Roaming/Zotero/Profiles/xxxxx.default/zotero/storage"
```

Or via environment variables:
```bash
export ZOTERO_DB_PATH="/path/to/zotero.sqlite"
export ZOTERO_STORAGE_DIR="/path/to/storage"
```

## Safe Database Access

CiteLoom uses **immutable read-only mode** when accessing the Zotero database:
- Creates a snapshot view of the database
- Prevents interference with Zotero desktop application
- Allows concurrent reads while Zotero is syncing
- Guarantees data consistency (SQLite isolation)

**You can safely use CiteLoom while Zotero is running** - there are no locks or conflicts.

## Storage Directory Resolution

When importing attachments, CiteLoom resolves file paths based on attachment type:

### Imported Files (`linkMode=0`)
Files stored in Zotero's storage directory:
```
{storage_dir}/storage/{itemKey}/{filename}
```

### Linked Files (`linkMode=1`)
Absolute paths stored in the database (external files).

CiteLoom handles both types and falls back to Web API download if local files are missing.

## Error Handling

If local database access fails, CiteLoom provides clear error messages:

- **Database locked**: "Zotero database is locked. Close Zotero or use Web API mode."
- **Database not found**: "Zotero database not found. Check profile path configuration."
- **Profile not found**: "Zotero profile not found. Install Zotero desktop or specify db_path."
- **Path resolution failed**: "Attachment path resolution failed. File may have been moved."

Configure fallback behavior using the `mode` setting (see Source Selection Strategies).

## Source Selection Strategies

Control how CiteLoom selects between local database and Web API:

```toml
[zotero]
mode = "local-first"  # Options: local-first, web-first, auto, local-only, web-only
```

- **`local-first`**: Try local database first, fallback to Web API per-file
- **`web-first`**: Use Web API primarily, fallback to local on rate limits
- **`auto`**: Intelligent selection based on availability and speed
- **`local-only`**: Strict local-only mode (no fallback)
- **`web-only`**: Web API only (backward compatible default)

## Offline Browsing Commands

Use local database for instant library exploration:

```bash
# List all collections with hierarchy and item counts
citeloom zotero list-collections

# Browse items in a specific collection
citeloom zotero browse-collection "Collection Name" --limit 20

# List all tags with usage counts
citeloom zotero list-tags

# View most recently added items
citeloom zotero recent-items --limit 10
```

All commands work **offline** using the local database - no internet connection required.

## Troubleshooting

### Database Access Denied
- **Check permissions**: Ensure you have read access to the Zotero profile directory
- **Check path**: Verify the database path is correct (use `db_path` override)
- **Check Zotero**: Ensure Zotero desktop is installed and profile exists

### Profile Not Found
- **Verify installation**: Check that Zotero desktop is installed
- **Check paths**: Verify platform-specific paths are correct
- **Use override**: Set `db_path` manually in `citeloom.toml`

### Files Missing Locally
- **Sync status**: Files may not be synced to local storage yet
- **Storage location**: Check `storage_dir` configuration
- **Fallback**: Use `mode=auto` or `mode=web-first` to download missing files via Web API

## Best Practices

1. **Use local-first mode** for fastest imports when most files exist locally
2. **Use auto mode** for best balance of speed and completeness
3. **Override db_path** only if auto-detection fails
4. **Keep Zotero synced** to ensure local files are available
5. **Monitor storage directory** if you use linked files (`linkMode=1`)

## See Also

- [Zotero Configuration](../docs/environment-config.md#zotero)
- [Source Selection Strategies](#source-selection-strategies)
- [Offline Browsing Commands](#offline-browsing-commands)


