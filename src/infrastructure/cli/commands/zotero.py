"""Zotero library browsing and exploration commands."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ...domain.errors import ZoteroConnectionError, ZoteroAPIError
from ...infrastructure.adapters.zotero_importer import ZoteroImporterAdapter
from ...infrastructure.config.environment import load_environment_variables

app = typer.Typer(help="Browse and explore Zotero library structure")
console = Console()
logger = logging.getLogger(__name__)


def _get_zotero_adapter() -> ZoteroImporterAdapter:
    """Initialize and return Zotero adapter with proper error handling."""
    load_environment_variables()
    try:
        return ZoteroImporterAdapter()
    except ZoteroConnectionError as e:
        console.print(f"[red]Zotero connection error: {e.message}[/red]")
        if e.reason:
            console.print(f"[yellow]Reason: {e.reason}[/yellow]")
        console.print("[yellow]Please verify:")
        console.print("  - ZOTERO_LIBRARY_ID environment variable is set")
        console.print("  - ZOTERO_API_KEY is set (for remote access)")
        console.print("  - ZOTERO_LOCAL=true (for local access, Zotero must be running)")
        console.print("  - Zotero is running with local API enabled (if using local access)")
        raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[red]Failed to initialize Zotero client: {e}[/red]")
        raise typer.Exit(code=1)


@app.command()
def list_collections(
    subcollections: bool = typer.Option(False, "--subcollections", "-s", help="Show subcollection hierarchy"),
) -> None:
    """
    List all top-level collections in Zotero library.
    
    Examples:
        citeloom zotero list-collections
        citeloom zotero list-collections --subcollections
    """
    adapter = _get_zotero_adapter()
    
    try:
        collections = adapter.list_collections()
        
        if not collections:
            console.print("[yellow]No collections found in Zotero library[/yellow]")
            return
        
        # Filter top-level collections (no parent)
        top_level = [c for c in collections if not c.get("parentCollection")]
        
        if subcollections:
            # Build hierarchy
            table = Table(title="Zotero Collections (with hierarchy)", show_header=True, header_style="bold magenta")
            table.add_column("Collection Name", style="green")
            table.add_column("Key", style="cyan")
            table.add_column("Parent", style="yellow")
            
            # Add top-level collections
            for coll in top_level:
                table.add_row(coll.get("name", ""), coll.get("key", ""), "")
            
            # Add subcollections
            for coll in collections:
                parent_key = coll.get("parentCollection")
                if parent_key:
                    # Find parent name
                    parent_name = ""
                    for parent_coll in collections:
                        if parent_coll.get("key") == parent_key:
                            parent_name = parent_coll.get("name", "")
                            break
                    table.add_row(coll.get("name", ""), coll.get("key", ""), parent_name)
        else:
            # Simple list of top-level collections only
            table = Table(title=f"Zotero Collections ({len(top_level)} found)", show_header=True, header_style="bold magenta")
            table.add_column("Collection Name", style="green")
            table.add_column("Key", style="cyan")
            
            for coll in top_level:
                table.add_row(coll.get("name", ""), coll.get("key", ""))
        
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
        table.add_column("Type", style="cyan")
        table.add_column("Key", style="yellow")
        table.add_column("Attachments", justify="right", style="blue")
        table.add_column("Date Added", style="white")
        
        for item in items:
            item_data = item.get("data", {})
            title = item_data.get("title", "(No title)")
            item_type = item_data.get("itemType", "unknown")
            item_key = item.get("key", "")
            
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
            
            table.add_row(title, item_type, item_key, str(attachment_count), date_str)
        
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
        if e.reason:
            console.print(f"[yellow]Reason: {e.reason}[/yellow]")
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
        if e.reason:
            console.print(f"[yellow]Reason: {e.reason}[/yellow]")
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
        def sort_key(tag: dict[str, Any]) -> tuple[int, str]:
            meta = tag.get("meta", {})
            num_items = meta.get("numItems", 0) if isinstance(meta, dict) else 0
            tag_name = tag.get("tag", "")
            return (-num_items, tag_name.lower())  # Negative for descending
        
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
            meta = tag.get("meta", {})
            num_items = meta.get("numItems", 0) if isinstance(meta, dict) else 0
            table.add_row(tag_name, str(num_items) if num_items > 0 else "-")
        
        console.print(table)
        
    except ZoteroConnectionError as e:
        console.print(f"[red]Zotero connection error: {e.message}[/red]")
        if e.reason:
            console.print(f"[yellow]Reason: {e.reason}[/yellow]")
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

