import typer

from ...adapters.fastembed_embeddings import FastEmbedAdapter
from ...adapters.qdrant_index import QdrantIndexAdapter

app = typer.Typer(help="Validate environment and configuration")


@app.command()
def run():
    # Simple checks: model load and qdrant client init
    embed = FastEmbedAdapter()
    vec = embed.embed(["hello"], model_id=None)
    ok_embed = len(vec) == 1 and isinstance(vec[0], list)

    q = QdrantIndexAdapter()
    q.upsert([], project_id="citeloom/validate", model_id="test")
    ok_q = True

    typer.echo(f"Embeddings: {'OK' if ok_embed else 'FAIL'}; Qdrant client: {'OK' if ok_q else 'FAIL'}")
