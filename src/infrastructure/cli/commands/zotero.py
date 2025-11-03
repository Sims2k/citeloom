"""Zotero library browsing and exploration commands."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from src.application.ports.zotero_importer import ZoteroImporterPort
from src.domain.errors import (
    ZoteroAPIError,
    ZoteroConnectionError,
    ZoteroDatabaseLockedError,
    ZoteroDatabaseNotFoundError,
    ZoteroProfileNotFoundError,
)
from src.infrastructure.adapters.zotero_importer import ZoteroImporterAdapter
from src.infrastructure.adapters.zotero_local_db import LocalZoteroDbAdapter
from src.infrastructure.config.environment import load_environment_variables
from src.infrastructure.config.settings import Settings

app = typer.Typer(help="Browse and explore Zotero library structure")
console = Console()
logger = logging.getLogger(__name__)


def _get_zotero_adapter(config_path: str = "citeloom.toml") -> ZoteroImporterPort:
    """
    Initialize and return Zotero adapter for offline browsing.
    
    Tries local database adapter first (offline-capable), falls back to web adapter.
    """
    load_environment_variables()
    
    # Try local adapter first for offline browsing
    try:
        settings = Settings.from_toml(config_path)
        zotero_settings = settings.zotero
        
        db_path = None
        if zotero_settings.db_path:
            db_path = Path(zotero_settings.db_path)
        
        storage_dir = None
        if zotero_settings.storage_dir:
            storage_dir = Path(zotero_settings.storage_dir)
        
        local_adapter = LocalZoteroDbAdapter(db_path=db_path, storage_dir=storage_dir)
        logger.info("Using local Zotero database adapter for offline browsing")
        return local_adapter
    except (ZoteroProfileNotFoundError, ZoteroDatabaseNotFoundError, ZoteroDatabaseLockedError) as e:
        # Local adapter unavailable, fall back to web adapter
        logger.warning(f"Local adapter unavailable: {e}, falling back to web adapter")
        error_msg = str(e)
        console.print(f"[yellow]Note: Local database unavailable ({error_msg}), using web API[/yellow]")
    except Exception as e:
        # Other errors - log but continue to try web adapter
        logger.warning(f"Failed to initialize local adapter: {e}, falling back to web adapter")
    
    # Fallback to web adapter
    try:
        web_adapter = ZoteroImporterAdapter()
        logger.info("Using web Zotero API adapter")
        return web_adapter
    except ZoteroConnectionError as e:
        console.print(f"[red]Zotero connection error: {e.message}[/red]")
        if e.reason:
            console.print(f"[yellow]Reason: {e.reason}[/yellow]")
        console.print("[yellow]Please verify:")
        console.print("  - Zotero is installed and has been run (for local access)")
        console.print("  - ZOTERO_LIBRARY_ID environment variable is set (for web access)")
        console.print("  - ZOTERO_API_KEY is set (for web access)")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Failed to initialize Zotero client: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def list_collections(
    subcollections: bool = typer.Option(True, "--subcollections/--no-subcollections", "-s/-S", help="Show subcollection hierarchy (default: True)"),
) -> None:
    """
    List all collections in Zotero library with hierarchical structure and item counts.
    
    By default, shows all collections including subcollections. Use --no-subcollections to show only top-level collections.
    
    Examples:
        citeloom zotero list-collections
        citeloom zotero list-collections --no-subcollections
        citeloom zotero list-collections -S
    """
    adapter = _get_zotero_adapter()
    
    try:
        collections = adapter.list_collections()
        
        if not collections:
            console.print("[yellow]No collections found in Zotero library[/yellow]")
            return
        
        # Fetch item counts for each collection
        collection_map: dict[str, dict[str, Any]] = {}
        for coll in collections:
            key = coll.get("key", "")
            if key:
                collection_map[key] = coll
                # Initialize item_count if not present
                if "item_count" not in coll:
                    coll["item_count"] = 0
        
        # Count items in each collection
        console.print("[dim]Counting items in collections...[/dim]")
        for coll_key, coll_data in collection_map.items():
            try:
                # Count items in this collection (not including subcollections for the count)
                items = list(adapter.get_collection_items(coll_key, include_subcollections=False))
                coll_data["item_count"] = len(items)
            except Exception as e:
                logger.warning(f"Failed to count items for collection {coll_key}: {e}")
                coll_data["item_count"] = 0
        
        # Build parent-child relationships
        children_map: dict[str, list[dict[str, Any]]] = {}
        top_level: list[dict[str, Any]] = []
        
        for coll in collections:
            parent_key = coll.get("parentCollection")
            if parent_key:
                if parent_key not in children_map:
                    children_map[parent_key] = []
                children_map[parent_key].append(coll)
            else:
                top_level.append(coll)
        
        def build_hierarchy(coll: dict[str, Any], depth: int = 0) -> list[tuple[dict[str, Any], int]]:
            """Recursively build hierarchy with depth."""
            result = [(coll, depth)]
            key = coll.get("key", "")
            if key in children_map:
                for child in sorted(children_map[key], key=lambda x: x.get("name", "")):
                    result.extend(build_hierarchy(child, depth + 1))
            return result
        
        if subcollections:
            # Display hierarchical structure with indentation
            table = Table(
                title="Zotero Collections (with hierarchy)",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Collection Name", style="green")
            table.add_column("Key", style="cyan")
            table.add_column("Items", justify="right", style="blue")
            
            # Sort top-level collections by name
            top_level_sorted = sorted(top_level, key=lambda x: x.get("name", ""))
            
            for coll in top_level_sorted:
                hierarchy = build_hierarchy(coll)
                for coll_item, depth in hierarchy:
                    indent = "  " * depth
                    name = coll_item.get("name", "")
                    key = coll_item.get("key", "")
                    item_count = coll_item.get("item_count", 0)
                    # Use ASCII-safe characters for Windows compatibility
                    prefix = "`- " if depth > 0 else ""
                    table.add_row(
                        f"{indent}{prefix}{name}",
                        key,
                        str(item_count) if item_count > 0 else "0",
                    )
        else:
            # Simple list of top-level collections only with item counts
            table = Table(
                title=f"Zotero Collections ({len(top_level)} found)",
                show_header=True,
                header_style="bold magenta",
            )
            table.add_column("Collection Name", style="green")
            table.add_column("Key", style="cyan")
            table.add_column("Items", justify="right", style="blue")
            
            # Sort by name
            top_level_sorted = sorted(top_level, key=lambda x: x.get("name", ""))
            for coll in top_level_sorted:
                item_count = coll.get("item_count", 0)
                table.add_row(
                    coll.get("name", ""),
                    coll.get("key", ""),
                    str(item_count) if item_count > 0 else "0",
                )
        
        console.print(table)
        
    except ZoteroAPIError as e:
        console.print(f"[red]Zotero API error: {e.message}[/red]")
        if e.details:
            console.print(f"[yellow]Details: {e.details}[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Failed to list collections: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def browse_collection(
    collection: str = typer.Option(..., "--collection", "-c", help="Collection name or key"),
    include_subcollections: bool = typer.Option(False, "--subcollections", "-s", help="Include items from subcollections"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum number of items to display (default: 20)"),
) -> None:
    """
    Browse items in a Zotero collection.
    
    Examples:
        citeloom zotero browse-collection --collection "Machine Learning Papers"
        citeloom zotero browse-collection -c ABC12345 --subcollections --limit 50
    """
    adapter = _get_zotero_adapter()
    
    try:
        # Find collection by name or use key directly
        collection_key = collection
        collection_name = collection
        
        # Try to find by name first (if not a valid key format)
        if len(collection) > 8 or not collection.isalnum():
            found = adapter.find_collection_by_name(collection)
            if found:
                collection_key = found.get("key", "")
                collection_name = found.get("name", "")
            else:
                console.print(f"[yellow]Collection '{collection}' not found by name, trying as key...[/yellow]")
        
        # Get items
        all_items = list(adapter.get_collection_items(collection_key, include_subcollections=include_subcollections))
        items = all_items[:limit]  # Limit items displayed
        
        if not all_items:
            console.print(f"[yellow]No items found in collection '{collection_name}'[/yellow]")
            return
        
        total_count = len(all_items)
        displayed_count = len(items)
        
        if displayed_count < total_count:
            console.print(f"[yellow]Showing first {displayed_count} items (use --limit to change)[/yellow]")
        
        title_suffix = f"({displayed_count} of {total_count} shown)" if displayed_count < total_count else f"({total_count} found)"
        
        table = Table(
            title=f"Items in '{collection_name}' {title_suffix}",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Title", style="green")
        table.add_column("Authors", style="cyan")
        table.add_column("Year", style="yellow")
        table.add_column("Type", style="blue")
        table.add_column("Attachments", justify="right", style="magenta")
        table.add_column("Date Added", style="white")
        
        for item in items:
            item_data = item.get("data", {})
            title = item_data.get("title", "(No title)")
            item_type = item_data.get("itemType", "unknown")
            item_key = item.get("key", "")
            
            # Get metadata for enhanced display
            try:
                metadata = adapter.get_item_metadata(item_key)
                
                # Extract creators (authors)
                creators = metadata.get("creators", [])
                if isinstance(creators, list) and creators:
                    creators_str = ", ".join(
                        [
                            f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                            if isinstance(c, dict)
                            else str(c)
                            for c in creators[:2]
                        ]
                    )
                    if len(creators) > 2:
                        creators_str += f" (+{len(creators) - 2})"
                else:
                    creators_str = "-"
                
                # Extract year
                year = metadata.get("year")
                year_str = str(year) if year else "-"
            except Exception:
                # Fallback to item_data if metadata unavailable
                creators_list = item_data.get("creators", [])
                if isinstance(creators_list, list) and creators_list:
                    creators_str = ", ".join(
                        [
                            f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                            if isinstance(c, dict)
                            else str(c)
                            for c in creators_list[:2]
                        ]
                    )
                    if len(creators_list) > 2:
                        creators_str += f" (+{len(creators_list) - 2})"
                else:
                    creators_str = "-"
                
                # Try to extract year from date field
                date_str = item_data.get("date", "")
                year_str = "-"
                if date_str:
                    # Try to extract year from date string (YYYY-MM-DD or YYYY format)
                    try:
                        year_int = int(date_str[:4]) if len(date_str) >= 4 else None
                        if year_int:
                            year_str = str(year_int)
                    except (ValueError, TypeError):
                        pass
            
            # Get attachment count
            try:
                attachments = adapter.get_item_attachments(item_key)
                attachment_count = len(attachments)
            except Exception:
                attachment_count = 0
            
            # Get date added
            date_added = item_data.get("dateAdded", "")
            if date_added:
                try:
                    # Parse ISO format datetime
                    dt = datetime.fromisoformat(date_added.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_str = date_added[:10] if len(date_added) >= 10 else date_added
            else:
                date_str = "-"
            
            table.add_row(title, creators_str, year_str, item_type, str(attachment_count), date_str)
        
        console.print(table)
        
        # Show metadata summary for first few items (up to 5)
        summary_items = items[:5]
        if len(summary_items) > 0:
            console.print("\n[bold]Metadata Summary:[/bold]")
            for item in summary_items:
                item_data = item.get("data", {})
                metadata = adapter.get_item_metadata(item.get("key", ""))
                console.print(f"\n[cyan]{metadata.get('title', '(No title)')}[/cyan]")
                if metadata.get("creators"):
                    creators_str = ", ".join(
                        [
                            f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
                            for c in metadata.get("creators", [])[:3]
                        ]
                    )
                    console.print(f"  Authors: {creators_str}")
                if metadata.get("year"):
                    console.print(f"  Year: {metadata.get('year')}")
                if metadata.get("DOI"):
                    console.print(f"  DOI: {metadata.get('DOI')}")
                if metadata.get("tags"):
                    tags_str = ", ".join(metadata.get("tags", [])[:5])
                    console.print(f"  Tags: {tags_str}")
        
    except ZoteroConnectionError as e:
        console.print(f"[red]Zotero connection error: {e.message}[/red]")
        if e.details and e.details.get("reason"):
            console.print(f"[yellow]Reason: {e.details.get('reason')}[/yellow]")
        console.print("[yellow]Please verify Zotero configuration and connectivity[/yellow]")
        raise typer.Exit(code=1)
    except ZoteroAPIError as e:
        console.print(f"[red]Zotero API error: {e.message}[/red]")
        if e.details:
            console.print(f"[yellow]Details: {e.details}[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Failed to browse collection: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def recent_items(
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of items to display"),
) -> None:
    """
    Display recently added items to Zotero library.
    
    Examples:
        citeloom zotero recent-items
        citeloom zotero recent-items --limit 20
    """
    adapter = _get_zotero_adapter()
    
    try:
        items = adapter.get_recent_items(limit=limit)
        
        if not items:
            console.print("[yellow]No recent items found in Zotero library[/yellow]")
            return
        
        table = Table(
            title=f"Recently Added Items ({len(items)} shown)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Title", style="green")
        table.add_column("Type", style="cyan")
        table.add_column("Date Added", style="yellow")
        table.add_column("Collections", style="blue")
        
        for item in items:
            item_data = item.get("data", {})
            title = item_data.get("title", "(No title)")
            item_type = item_data.get("itemType", "unknown")
            
            # Get date added
            date_added = item_data.get("dateAdded", "")
            if date_added:
                try:
                    dt = datetime.fromisoformat(date_added.replace("Z", "+00:00"))
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_str = date_added[:16] if len(date_added) >= 16 else date_added
            else:
                date_str = "-"
            
            # Get collections
            try:
                metadata = adapter.get_item_metadata(item.get("key", ""))
                collections = metadata.get("collections", [])
                collections_str = ", ".join(collections[:3]) if collections else "-"
                if len(collections) > 3:
                    collections_str += f" (+{len(collections) - 3} more)"
            except Exception:
                collections_str = "-"
            
            table.add_row(title, item_type, date_str, collections_str)
        
        console.print(table)
        
    except ZoteroConnectionError as e:
        console.print(f"[red]Zotero connection error: {e.message}[/red]")
        if e.details and e.details.get("reason"):
            console.print(f"[yellow]Reason: {e.details.get('reason')}[/yellow]")
        console.print("[yellow]Please verify Zotero configuration and connectivity[/yellow]")
        raise typer.Exit(code=1)
    except ZoteroAPIError as e:
        console.print(f"[red]Zotero API error: {e.message}[/red]")
        if e.details:
            console.print(f"[yellow]Details: {e.details}[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Failed to get recent items: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def list_tags() -> None:
    """
    List all tags used in Zotero library with usage counts.
    
    Examples:
        citeloom zotero list-tags
    """
    adapter = _get_zotero_adapter()
    
    try:
        tags = adapter.list_tags()
        
        if not tags:
            console.print("[yellow]No tags found in Zotero library[/yellow]")
            return
        
        # Sort by usage count (if available) or tag name
        # Handle both local adapter format (count) and web adapter format (meta.numItems)
        def sort_key(tag: dict[str, Any]) -> tuple[int, str]:
            # Try local adapter format first (direct count field)
            count = tag.get("count", 0)
            if count == 0:
                # Try web adapter format (nested meta.numItems)
                meta = tag.get("meta", {})
                count = meta.get("numItems", 0) if isinstance(meta, dict) else 0
            tag_name = tag.get("tag", "")
            return (-count, tag_name.lower())  # Negative for descending
        
        sorted_tags = sorted(tags, key=sort_key)
        
        table = Table(
            title=f"Zotero Tags ({len(sorted_tags)} found)",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Tag", style="green")
        table.add_column("Usage Count", justify="right", style="cyan")
        
        for tag in sorted_tags:
            tag_name = tag.get("tag", "")
            # Handle both local adapter format (count) and web adapter format (meta.numItems)
            count = tag.get("count", 0)
            if count == 0:
                meta = tag.get("meta", {})
                count = meta.get("numItems", 0) if isinstance(meta, dict) else 0
            table.add_row(tag_name, str(count) if count > 0 else "-")
        
        console.print(table)
        
    except ZoteroConnectionError as e:
        console.print(f"[red]Zotero connection error: {e.message}[/red]")
        if e.details and e.details.get("reason"):
            console.print(f"[yellow]Reason: {e.details.get('reason')}[/yellow]")
        console.print("[yellow]Please verify Zotero configuration and connectivity[/yellow]")
        raise typer.Exit(code=1)
    except ZoteroAPIError as e:
        console.print(f"[red]Zotero API error: {e.message}[/red]")
        if e.details:
            console.print(f"[yellow]Details: {e.details}[/yellow]")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Failed to list tags: {e}[/red]")
        raise typer.Exit(code=1)

