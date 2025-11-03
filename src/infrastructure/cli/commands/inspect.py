"""Inspect collection contents and configuration."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.domain.errors import ProjectNotFound
from src.infrastructure.adapters.qdrant_index import QdrantIndexAdapter
from src.infrastructure.config.settings import Settings

app = typer.Typer(help="Inspect stored chunks and collection configuration")
console = Console()


@app.command()
def collection(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (e.g., citeloom/clean-arch)"),
    sample: int = typer.Option(0, "--sample", "-s", help="Number of sample chunks to display (0-10)"),
    show_embedding_model: bool = typer.Option(False, "--show-embedding-model", help="Display embedding model information for the collection"),
    config_path: str = typer.Option("citeloom.toml", help="Path to citeloom.toml configuration file"),
) -> None:
    """
    Inspect collection statistics, configuration, and sample data.
    
    Displays:
    - Collection size (number of chunks)
    - Embedding model identifiers
    - Payload schema sample
    - Index presence confirmation
    - Optional sample chunk data
    
    Examples:
        citeloom inspect collection --project citeloom/clean-arch
        citeloom inspect collection --project citeloom/clean-arch --sample 5
        citeloom inspect collection --project citeloom/clean-arch --show-embedding-model
    """
    # Load settings
    try:
        settings = Settings.from_toml(config_path)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)
    
    # Get project settings
    try:
        project_settings = settings.get_project(project)
    except KeyError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    
    collection_name = f"proj-{project.replace('/', '-')}"
    
    # Initialize Qdrant adapter
    index = QdrantIndexAdapter(url=settings.qdrant.url)
    
    if index._client is None:
        console.print(f"[red]Error: Could not connect to Qdrant at {settings.qdrant.url}[/red]")
        console.print("\n[yellow]Tip:[/yellow] Ensure Qdrant is running:")
        console.print("  docker run -d --name qdrant -p 6333:6333 qdrant/qdrant")
        raise typer.Exit(1)
    
    # T069: Display collection statistics
    try:
        collection_info = index._client.get_collection(collection_name)
    except Exception:
        console.print(f"[red]Error: Collection '{collection_name}' not found[/red]")
        console.print(f"\n[yellow]Tip:[/yellow] Run 'citeloom ingest run --project {project}' to create the collection")
        raise typer.Exit(1)
    
    # Get collection size
    try:
        scroll_result = index._client.scroll(
            collection_name=collection_name,
            limit=0,  # Just get count
            with_payload=False,
            with_vectors=False,
        )
        collection_size = len(scroll_result[0]) if scroll_result[0] else 0
    except Exception as e:
        console.print(f"[yellow]Warning: Could not determine collection size: {e}[/yellow]")
        collection_size = 0
    
    # T070: Get embedding model identifier from collection metadata
    metadata = getattr(collection_info, "metadata", None) or {}
    dense_model_id = metadata.get("dense_model_id") or metadata.get("embed_model") or project_settings.embedding_model
    sparse_model_id = metadata.get("sparse_model_id")
    
    # T100, T101: Display embedding model information if requested
    if show_embedding_model:
        console.print(f"\n[bold cyan]Embedding Model Information[/bold cyan]")
        console.print(f"  Collection: {collection_name}")
        console.print(f"  Project: {project}")
        console.print(f"  Bound Dense Model: [green]{dense_model_id}[/green]")
        if sparse_model_id:
            console.print(f"  Bound Sparse Model: [green]{sparse_model_id}[/green]")
        console.print(f"  Project Config Model: {project_settings.embedding_model}")
        console.print(f"  Hybrid Search: {'Enabled' if project_settings.hybrid_enabled else 'Disabled'}")
        console.print()
    
    # Display collection overview
    console.print(f"\n[bold cyan]Collection: {collection_name}[/bold cyan]")
    console.print(f"  Project: {project}")
    
    # Statistics table
    stats_table = Table(title="Collection Statistics", show_header=False, box=None)
    stats_table.add_column("Metric", style="cyan", width=30)
    stats_table.add_column("Value", style="white")
    
    stats_table.add_row("Collection Size", str(collection_size))
    stats_table.add_row("Dense Model", dense_model_id)
    if sparse_model_id:
        stats_table.add_row("Sparse Model", sparse_model_id)
    stats_table.add_row("Hybrid Enabled", "Yes" if project_settings.hybrid_enabled else "No")
    
    console.print()
    console.print(stats_table)
    
    # T071: Get payload schema sample
    payload_keys = set()
    sample_payloads: list[dict[str, Any]] = []
    
    # T073: Get sample chunk data if requested
    sample_limit = min(max(0, sample), 10)  # Cap at 10 samples
    
    if sample_limit > 0 or collection_size > 0:
        try:
            scroll_limit = sample_limit if sample_limit > 0 else min(1, collection_size)
            scroll_result = index._client.scroll(
                collection_name=collection_name,
                limit=scroll_limit,
                with_payload=True,
                with_vectors=False,
            )
            
            points = scroll_result[0] if scroll_result[0] else []
            
            for point in points[:scroll_limit]:
                payload = point.payload or {}
                payload_keys.update(payload.keys())
                
                if sample_limit > 0:
                    sample_payloads.append({
                        "id": str(point.id),
                        "payload": payload,
                    })
        except Exception as e:
            console.print(f"[yellow]Warning: Could not retrieve sample data: {e}[/yellow]")
    
    # Display payload schema
    console.print()
    console.print("[bold cyan]Payload Schema[/bold cyan]")
    
    # Common payload keys (from contracts)
    common_keys = [
        "project_id", "doc_id", "section_path", "page_start", "page_end",
        "citekey", "doi", "year", "authors", "title", "tags", "source_path",
        "chunk_text", "heading_chain", "embed_model", "version",
    ]
    
    # Merge discovered keys with common keys
    all_keys = sorted(set(common_keys) | payload_keys)
    
    schema_table = Table(title="Payload Fields", show_header=True, header_style="bold magenta")
    schema_table.add_column("Field", style="cyan")
    schema_table.add_column("Type", style="white")
    schema_table.add_column("Indexed", justify="center")
    
    # T072: Index presence confirmation
    keyword_indexes = ["project_id", "doc_id", "citekey", "year", "tags"]
    fulltext_indexes = ["chunk_text"] if (project_settings.hybrid_enabled and settings.qdrant.create_fulltext_index) else []
    
    for key in all_keys:
        is_keyword_indexed = key in keyword_indexes
        is_fulltext_indexed = key in fulltext_indexes
        
        index_status = ""
        if is_keyword_indexed:
            index_status = "[green]keyword[/green]"
        if is_fulltext_indexed:
            if index_status:
                index_status += ", [blue]fulltext[/blue]"
            else:
                index_status = "[blue]fulltext[/blue]"
        if not index_status:
            index_status = "[dim]no[/dim]"
        
        # Infer type from common keys
        field_type = "string"
        if key in ["year", "page_start", "page_end"]:
            field_type = "int"
        elif key in ["authors", "tags", "section_path"]:
            field_type = "list"
        elif key == "chunk_text":
            field_type = "text"
        
        schema_table.add_row(key, field_type, index_status)
    
    console.print()
    console.print(schema_table)
    
    # T072: Display index summary
    console.print()
    console.print("[bold cyan]Indexes[/bold cyan]")
    
    indexes_table = Table(title="Payload Indexes", show_header=True, header_style="bold magenta")
    indexes_table.add_column("Index Type", style="cyan")
    indexes_table.add_column("Fields", style="white")
    
    indexes_table.add_row(
        "[green]Keyword[/green]",
        ", ".join(keyword_indexes),
    )
    
    if fulltext_indexes:
        indexes_table.add_row(
            "[blue]Full-Text[/blue]",
            ", ".join(fulltext_indexes),
        )
    else:
        indexes_table.add_row(
            "[dim]Full-Text[/dim]",
            "[dim]Not enabled[/dim]",
        )
    
    console.print()
    console.print(indexes_table)
    
    # T073: Display sample chunk data if requested
    if sample_payloads:
        console.print()
        console.print(f"[bold cyan]Sample Chunks ({len(sample_payloads)})[/bold cyan]")
        
        for i, sample in enumerate(sample_payloads, 1):
            payload = sample["payload"]
            
            # Extract key information
            chunk_info = {
                "id": sample["id"],
                "doc_id": payload.get("doc_id", "N/A"),
                "title": payload.get("title", "N/A"),
                "citekey": payload.get("citekey", "N/A"),
                "page_start": payload.get("page_start", "N/A"),
                "page_end": payload.get("page_end", "N/A"),
                "section_path": payload.get("section_path", []),
                "chunk_text_preview": str(payload.get("chunk_text", ""))[:200] + "..." if payload.get("chunk_text") else "N/A",
            }
            
            panel_content = f"""[bold]Chunk {i}[/bold]
ID: {chunk_info['id']}
Document: {chunk_info['doc_id']}
Title: {chunk_info['title']}
Citekey: {chunk_info['citekey']}
Pages: {chunk_info['page_start']}-{chunk_info['page_end']}
Section: {' > '.join(chunk_info['section_path']) if chunk_info['section_path'] else 'N/A'}
Text Preview: {chunk_info['chunk_text_preview']}"""
            
            console.print(Panel(panel_content, border_style="blue"))
    
    console.print()


@app.command()
def sample(
    project: str = typer.Option(..., "--project", "-p", help="Project ID"),
    n: int = typer.Option(5, "--count", "-n", help="Number of samples"),
) -> None:
    """
    Legacy command for backward compatibility - use 'inspect collection' instead.
    
    This command is deprecated. Use 'citeloom inspect collection --project <project> --sample <n>' instead.
    """
    console.print("[yellow]This command is deprecated.[/yellow]")
    console.print(f"Use: [cyan]citeloom inspect collection --project {project} --sample {n}[/cyan]")
    collection(project=project, sample=n)
