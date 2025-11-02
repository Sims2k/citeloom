# Quickstart: Zotero Collection Import with Batch Processing

**Feature**: 004-zotero-batch-import  
**Date**: 2025-01-27

This guide provides step-by-step instructions for implementing Zotero collection import with batch processing, progress indication, and checkpointing.

## Implementation Checklist

### Phase 1: Domain Models

- [ ] Create `src/domain/models/checkpoint.py` with:
  - `IngestionCheckpoint` entity
  - `DocumentCheckpoint` entity
  - `CheckpointStatistics` value object
- [ ] Create `src/domain/models/download_manifest.py` with:
  - `DownloadManifest` entity
  - `DownloadManifestItem` entity
  - `DownloadManifestAttachment` entity
- [ ] Add validation rules and state transition logic
- [ ] Write unit tests for domain models (`tests/unit/test_checkpoint_models.py`)

### Phase 2: Port Interfaces

- [ ] Create `src/application/ports/zotero_importer.py` with `ZoteroImporterPort`
- [ ] Create `src/application/ports/checkpoint_manager.py` with `CheckpointManagerPort`
- [ ] Create `src/application/ports/progress_reporter.py` with `ProgressReporterPort`
- [ ] Enhance `IngestDocument` use case signature to accept optional `ProgressReporterPort`

### Phase 3: Infrastructure Adapters

- [ ] Create `src/infrastructure/adapters/zotero_importer.py`:
  - Implement `ZoteroImporterPort`
  - Use pyzotero with rate limiting wrapper (0.5s interval for web API)
  - Support local and remote API modes
  - Implement retry logic with exponential backoff
- [ ] Create `src/infrastructure/adapters/checkpoint_manager.py`:
  - Implement `CheckpointManagerPort`
  - Atomic writes (temp file + rename)
  - JSON serialization/deserialization
  - Checkpoint validation
- [ ] Create `src/infrastructure/adapters/rich_progress_reporter.py`:
  - Implement `ProgressReporterPort`
  - Use Rich library for visual progress bars
  - Detect non-interactive mode and fallback to logging
- [ ] Write integration tests for adapters

### Phase 4: Application Use Case

- [ ] Create `src/application/use_cases/batch_import_from_zotero.py`:
  - Two-phase import workflow (download then process)
  - Checkpoint management
  - Progress reporting coordination
  - Error handling and retries

### Phase 5: CLI Commands

- [ ] Create `src/infrastructure/cli/commands/zotero.py`:
  - `list-collections` command
  - `browse-collection` command
  - `list-tags` command
  - `recent-items` command
- [ ] Enhance `src/infrastructure/cli/commands/ingest.py`:
  - Add `--zotero-collection` option
  - Add `--resume` flag
  - Add `--zotero-tags` and `--exclude-tags` options
  - Add `--keep-checkpoints` and `--cleanup-checkpoints` flags
  - Wire to `BatchImportFromZotero` use case

### Phase 6: MCP Tool Enhancement

- [ ] Update `src/infrastructure/mcp/tools.py`:
  - Replace `NOT_IMPLEMENTED` placeholder for Zotero import in `ingest_from_source`
  - Support `collection_key` option
  - Support tag filters

## Common Patterns

### Rate Limiting with pyzotero

```python
from pyzotero import zotero
import time

class ZoteroClientWrapper:
    MIN_REQUEST_INTERVAL = 0.5  # 2 requests per second max
    
    def __init__(self, library_id, library_type, api_key=None, local=False):
        self.zot = zotero.Zotero(library_id, library_type, api_key, local=local)
        self.local = local
        self._last_request_time = 0.0
    
    def _rate_limit(self):
        if self.local:
            return  # No rate limiting for local API
        
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        
        if time_since_last < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - time_since_last)
        
        self._last_request_time = time.time()
    
    def items(self, **kwargs):
        self._rate_limit()
        return self.zot.items(**kwargs)
```

### Atomic Checkpoint Write

```python
import json
import tempfile
from pathlib import Path

def save_checkpoint_atomic(checkpoint: IngestionCheckpoint, path: Path) -> None:
    """Write checkpoint atomically to prevent corruption."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix('.tmp')
    
    with temp_path.open('w') as f:
        json.dump(checkpoint.to_dict(), f, indent=2)
    
    temp_path.replace(path)  # Atomic rename (atomic on POSIX, best-effort on Windows)
```

### Rich Progress Bars

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

def create_progress_bar() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

# Usage:
with create_progress_bar() as progress:
    task = progress.add_task("Processing documents", total=100)
    # ... process documents ...
    progress.update(task, advance=1)
```

### Tag-Based Filtering

```python
def matches_tag_filter(item_tags: list[str], include_tags: list[str], exclude_tags: list[str]) -> bool:
    """Case-insensitive partial matching for tag filters."""
    item_tags_lower = [tag.lower() for tag in item_tags]
    
    # Include tags: OR logic (any match)
    if include_tags:
        if not any(
            any(include_tag.lower() in item_tag for item_tag in item_tags_lower)
            for include_tag in include_tags
        ):
            return False
    
    # Exclude tags: ANY-match logic (any exclude tag excludes item)
    if exclude_tags:
        if any(
            any(exclude_tag.lower() in item_tag for item_tag in item_tags_lower)
            for exclude_tag in exclude_tags
        ):
            return False
    
    return True
```

## Testing Strategy

### Unit Tests

- Domain models: Test validation rules, state transitions, serialization
- Value objects: Test format validation

### Integration Tests

- `test_zotero_importer.py`: Test pyzotero integration, rate limiting, retry logic
- `test_checkpoint_manager.py`: Test checkpoint I/O, atomic writes, validation
- `test_progress_indication.py`: Test Rich progress bars, non-interactive fallback

### End-to-End Tests

- Test full import workflow: Browse collection → Import → Resume
- Test tag-based filtering
- Test two-phase import (download then process)

## Validation Scenarios

1. **Import small collection (10 documents)**: Verify download, conversion, chunking, embedding, storage
2. **Resume interrupted import**: Start import, interrupt at document 5, resume with `--resume` flag
3. **Tag-based filtering**: Import with `--zotero-tags "ML" --exclude-tags "Draft"`
4. **Progress indication**: Verify progress bars show document count, stages, time estimates
5. **Two-phase import**: Download collection, interrupt processing, retry with `--process-downloads`

## Next Steps

After completing this quickstart checklist, proceed to `/speckit.tasks` to generate detailed implementation tasks organized by user story.

