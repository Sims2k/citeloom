import typer

app = typer.Typer(help="Query chunks from CiteLoom")


@app.command()
def run(
    project: str = typer.Option(..., help="Project id"),
    q: str = typer.Option(..., help="Query text"),
    k: int = typer.Option(6, help="Top-k results"),
):
    typer.echo(f"Query stub: project={project} q={q} k={k}")
