import typer

from .commands import (
    ingest as ingest_cmd,
    query as query_cmd,
    inspect as inspect_cmd,
    validate as validate_cmd,
    zotero as zotero_cmd,
)
from ..mcp.server import main as mcp_server_main

app = typer.Typer(help="CiteLoom CLI")

app.add_typer(ingest_cmd.app, name="ingest")
app.add_typer(query_cmd.app, name="query")
app.add_typer(inspect_cmd.app, name="inspect")
app.add_typer(validate_cmd.app, name="validate")
app.add_typer(zotero_cmd.app, name="zotero")


@app.command()
def mcp_server() -> None:
    """Run MCP server for editor integration."""
    mcp_server_main()


if __name__ == "__main__":
    app()
