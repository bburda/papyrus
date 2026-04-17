"""Tests for the `papyrus link` CLI command."""
from datetime import UTC, datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from papyrus.cli import cli
from papyrus.models import Link, LinkType, Need, NeedType
from papyrus.storage.rst import RSTBackend


def _seed(ws: Path) -> None:
    be = RSTBackend(ws)
    be.init_workspace(ws)
    now = datetime.now(UTC)
    be.append_need(Need(id="DEC_a", type=NeedType.DEC, title="a", created_at=now, updated_at=now))
    be.append_need(Need(id="FACT_b", type=NeedType.FACT, title="b", created_at=now, updated_at=now))


def test_link_adds_edge(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = CliRunner().invoke(
        cli, ["--workspace", str(tmp_path), "link", "DEC_a", "FACT_b", "--as", "satisfies"]
    )
    assert result.exit_code == 0, result.output
    need = RSTBackend(tmp_path).find_by_id("DEC_a")
    assert need is not None
    assert Link(type=LinkType.SATISFIES, target="FACT_b") in need.links


def test_link_rejects_unknown_mem(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = CliRunner().invoke(
        cli, ["--workspace", str(tmp_path), "link", "DEC_ghost", "FACT_b", "--as", "relates"]
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_link_rejects_unknown_target_local_only(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = CliRunner().invoke(
        cli, ["--workspace", str(tmp_path), "link", "DEC_a", "REQ_missing", "--as", "satisfies"]
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_link_is_idempotent(tmp_path: Path) -> None:
    _seed(tmp_path)
    runner = CliRunner()
    for _ in range(2):
        result = runner.invoke(
            cli, ["--workspace", str(tmp_path), "link", "DEC_a", "FACT_b", "--as", "satisfies"]
        )
        assert result.exit_code == 0, result.output
    need = RSTBackend(tmp_path).find_by_id("DEC_a")
    assert need is not None
    satisfies_edges = [lk for lk in need.links if lk.type == LinkType.SATISFIES and lk.target == "FACT_b"]
    assert len(satisfies_edges) == 1


def test_link_accepts_external_target(tmp_path: Path) -> None:
    ws = tmp_path / "papyrus"
    pharaoh = tmp_path / "pharaoh"
    pharaoh.mkdir()
    (pharaoh / "needs.json").write_text(
        '{"versions": {"1.0": {"needs": '
        '{"REQ_auth": {"id": "REQ_auth", "type": "req", "title": "Auth req", "links": [], "satisfies": []}}'
        '}}}'
    )
    (tmp_path / "papyrus.toml").write_text(
        """
[papyrus]
preset = "silos"

[[papyrus.workspaces]]
path = "papyrus"
scope = "local"

[papyrus.external]
pharaoh_workspace = "pharaoh"
"""
    )
    be = RSTBackend(ws)
    be.init_workspace(ws)
    now = datetime.now(UTC)
    be.append_need(Need(id="DEC_a", type=NeedType.DEC, title="a", created_at=now, updated_at=now))

    result = CliRunner().invoke(
        cli,
        ["--config", str(tmp_path / "papyrus.toml"), "link", "DEC_a", "REQ_auth", "--as", "satisfies"],
    )
    assert result.exit_code == 0, result.output
    stored = RSTBackend(ws).find_by_id("DEC_a")
    assert stored is not None
    assert Link(type=LinkType.SATISFIES, target="REQ_auth") in stored.links


def test_link_rejects_target_missing_in_both(tmp_path: Path) -> None:
    ws = tmp_path / "papyrus"
    pharaoh = tmp_path / "pharaoh"
    pharaoh.mkdir()
    (pharaoh / "needs.json").write_text(
        '{"versions": {"1.0": {"needs": {}}}}'
    )
    (tmp_path / "papyrus.toml").write_text(
        """
[papyrus]
preset = "silos"

[[papyrus.workspaces]]
path = "papyrus"
scope = "local"

[papyrus.external]
pharaoh_workspace = "pharaoh"
"""
    )
    be = RSTBackend(ws)
    be.init_workspace(ws)
    now = datetime.now(UTC)
    be.append_need(Need(id="DEC_a", type=NeedType.DEC, title="a", created_at=now, updated_at=now))

    result = CliRunner().invoke(
        cli,
        ["--config", str(tmp_path / "papyrus.toml"), "link", "DEC_a", "REQ_ghost", "--as", "satisfies"],
    )
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
