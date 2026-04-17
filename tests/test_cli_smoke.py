"""Smoke test: verify the CLI is installed and --version works."""
from click.testing import CliRunner

from papyrus import __version__
from papyrus.cli import cli


def test_version_flag_prints_version() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_version_matches_pyproject() -> None:
    # Keep __version__ in sync with pyproject.toml; hard-code here as canonical.
    assert __version__ == "0.1.0"
