import typer

app = typer.Typer(help="Inspect stored chunks")


@app.command()
def sample(project: str = typer.Option(..., help="Project id"), n: int = 5):
    typer.echo(f"Inspect stub: project={project} sample={n}")
