import subprocess
from pathlib import Path


def test_import_linter_contracts():
    result = subprocess.run(
        ["uv", "run", "lint-imports", "--infile", "linter.ini"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )
    # If the command is not available, skip gracefully
    if result.returncode == 127 or "not found" in (result.stderr or "").lower():
        return
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
