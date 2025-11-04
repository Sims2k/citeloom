from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from src.application.dto.query import QueryRequest
from src.application.use_cases.query_chunks import query_chunks
from src.application.ports.embeddings import EmbeddingPort
from src.application.ports.vector_index import VectorIndexPort
from src.domain.errors import ProjectNotFound, HybridNotSupported
from src.infrastructure.adapters.fastembed_embeddings import FastEmbedAdapter
from src.infrastructure.adapters.qdrant_index import QdrantIndexAdapter
from src.infrastructure.config.settings import Settings

app = typer.Typer(help="Query chunks from CiteLoom")
console = Console()


@app.command()
def run(
    project: str = typer.Option(..., "--project", "-p", help="Project ID (e.g., citeloom/clean-arch)"),
    query: str = typer.Option(..., "--query", "-q", help="Query text"),
    top_k: int = typer.Option(6, "--top-k", "-k", help="Maximum number of results"),
    hybrid: bool = typer.Option(False, "--hybrid", help="Enable hybrid search (full-text + vector)"),
    filters: str = typer.Option(None, "--filters", help="Additional filters (JSON format)"),
) -> None:
    """
    Query chunks from a project with semantic or hybrid search.
    
    Examples:
        citeloom query -p citeloom/clean-arch -q "clean architecture layers"
        citeloom query -p citeloom/clean-arch -q "repository pattern" --hybrid --top-k 10
    """
    # Parse filters if provided
    parsed_filters: dict[str, Any] | None = None
    if filters:
        try:
            parsed_filters = json.loads(filters)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing filters JSON: {e}[/red]")
            raise typer.Exit(code=1)
    
    # Load settings for project configuration
    try:
        settings = Settings.from_toml()
        project_settings = settings.get_project(project)
    except KeyError:
        console.print(f"[red]Project '{project}' not found in configuration[/red]")
        raise typer.Exit(code=1)
    
    # Create request
    request = QueryRequest(
        project_id=project,
        query_text=query,
        top_k=top_k,
        hybrid=hybrid or project_settings.hybrid_enabled,
        filters=parsed_filters,
    )
    
    # Initialize adapters
    embedder: EmbeddingPort = FastEmbedAdapter()
    index: VectorIndexPort = QdrantIndexAdapter(
        url=settings.qdrant.url,
        create_fulltext_index=settings.qdrant.create_fulltext_index,
    )
    
    # Execute query
    try:
        result = query_chunks(request, embedder, index)
    except ProjectNotFound as e:
        console.print(f"[red]Project not found: {project}[/red]")
        console.print(f"[yellow]Note: If using in-memory fallback (Qdrant not running), data doesn't persist between commands.[/yellow]")
        console.print(f"[yellow]Start Qdrant server or use Qdrant Cloud for persistent storage.[/yellow]")
        raise typer.Exit(code=1)
    except HybridNotSupported as e:
        # T047, T048a: Improve error message when query fails due to model binding
        console.print(f"[red]Hybrid search not supported for project '{project}': {e.reason}[/red]")
        
        # Provide actionable guidance based on the reason
        if "model not bound" in str(e.reason).lower() or "set_model" in str(e.reason).lower():
            console.print(f"\n[yellow]Model binding issue detected.[/yellow]")
            console.print(f"[cyan]Resolution options:[/cyan]")
            console.print(f"  1. [bold]Automatic fix (recommended):[/bold] Re-run ingestion to auto-bind model:")
            console.print(f"     [dim]citeloom ingest run --project {project}[/dim]")
            console.print(f"  2. [bold]Manual fix:[/bold] Bind model using Qdrant client or API")
            console.print(f"  3. [bold]Check configuration:[/bold] Verify embedding model in project settings")
            console.print(f"\n[dim]Note: Model binding is now automatic during ingestion. If you see this error,")
            console.print(f"it may indicate the collection was created before auto-binding was implemented.[/dim]")
        elif "full-text index not enabled" in str(e.reason).lower():
            console.print(f"\n[yellow]Full-text index not enabled for hybrid search.[/yellow]")
            console.print(f"[cyan]Resolution:[/cyan] Enable full-text index in project settings or Qdrant configuration")
        else:
            console.print(f"\n[cyan]Check project configuration for hybrid search settings.[/cyan]")
        raise typer.Exit(code=1)
    except Exception as e:
        error_msg = str(e)
        console.print(f"[red]Query failed: {error_msg}[/red]")
        
        # T047, T048a: Provide actionable guidance for model binding errors
        if "model not bound" in error_msg.lower() or "set_model" in error_msg.lower():
            console.print(f"\n[yellow]Model binding issue detected.[/yellow]")
            console.print(f"[cyan]Resolution options:[/cyan]")
            console.print(f"  1. [bold]Automatic fix (recommended):[/bold] Re-run ingestion to auto-bind model:")
            console.print(f"     [dim]citeloom ingest run --project {project}[/dim]")
            console.print(f"  2. [bold]Manual fix:[/bold] Bind model using Qdrant client or API")
            console.print(f"  3. [bold]Check configuration:[/bold] Verify embedding model in project settings")
            console.print(f"\n[dim]Note: Model binding is now automatic during ingestion. If you see this error,")
            console.print(f"it may indicate the collection was created before auto-binding was implemented.[/dim]")
        
        raise typer.Exit(code=1)
    
    # Format and display results
    if not result.items:
        console.print(f"[yellow]No results found for query: {query}[/yellow]")
        return
    
    # Format output: (citekey, pp. x–y, section) format
    table = Table(title=f"Query Results ({len(result.items)} found)", show_header=True, header_style="bold magenta")
    table.add_column("Score", justify="right", style="cyan")
    table.add_column("Citation", style="green")
    table.add_column("Pages", style="yellow")
    table.add_column("Section", style="blue")
    table.add_column("Text Preview", style="white")
    
    for item in result.items:
        # Format citation: citekey or "unknown"
        citation_str = item.citekey or "unknown"
        
        # Format pages: "pp. x–y" or "-"
        if item.page_span:
            page_str = f"pp. {item.page_span[0]}–{item.page_span[1]}"
        else:
            page_str = "-"
        
        # Format section: section heading or section path or "-"
        if item.section:
            section_str = item.section
        elif item.section_path:
            section_str = " > ".join(item.section_path)
        else:
            section_str = "-"
        
        # Truncate text preview
        text_preview = item.text[:100] + "..." if len(item.text) > 100 else item.text
        
        table.add_row(
            f"{item.score:.3f}",
            citation_str,
            page_str,
            section_str,
            text_preview,
        )
    
    console.print(table)
    
    # Also print detailed format for each result
    console.print("\n[bold]Detailed Results:[/bold]")
    for idx, item in enumerate(result.items, 1):
        console.print(f"\n[cyan][{idx}][/cyan] Score: {item.score:.4f}")
        if item.citekey:
            console.print(f"  Citation: [green]{item.citekey}[/green]")
        if item.page_span:
            console.print(f"  Pages: [yellow]pp. {item.page_span[0]}–{item.page_span[1]}[/yellow]")
        if item.section:
            console.print(f"  Section: [blue]{item.section}[/blue]")
        if item.section_path:
            console.print(f"  Path: [blue]{' > '.join(item.section_path)}[/blue]")
        if item.doi:
            console.print(f"  DOI: {item.doi}")
        console.print(f"  Text: {item.text}")
