from typer.testing import CliRunner

from infrastructure.cli.main import app


def test_ingest_prints_correlation_id():
    runner = CliRunner()
    result = runner.invoke(app, [
        "ingest",
        "run",
        "--project",
        "citeloom/test",
        "--references",
        "references/clean-arch.json",
        "assets/raw/clean-arch.pdf",
    ])
    assert result.exit_code == 0
    assert "correlation_id=" in result.stdout
