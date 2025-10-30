import typer

app = typer.Typer(help="Ingest documents into CiteLoom")


@app.command()
def run(
    project: str = typer.Option(..., help="Project id, e.g. citeloom/clean-arch"),
    source: str = typer.Argument(..., help="Path to source document (e.g., PDF)"),
):
    typer.echo(f"Ingest stub: project={project} source={source}")
