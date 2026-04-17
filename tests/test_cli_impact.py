"""Tests for the `papyrus impact` CLI command (internal graph only)."""
from datetime import UTC, datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from papyrus.cli import cli
from papyrus.models import Link, LinkType, Need, NeedType
from papyrus.storage.rst import RSTBackend


def _make(nid: str, ntype: NeedType, *links: Link) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid, created_at=now, updated_at=now, links=list(links))


def test_impact_reports_self_at_depth_zero(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    be.append_need(_make("DEC_a", NeedType.DEC))

    result = CliRunner().invoke(cli, ["--workspace", str(tmp_path), "impact", "DEC_a", "--depth", "0"])
    assert result.exit_code == 0, result.output
    assert "DEC_a" in result.output


def test_impact_follows_satisfies_edges(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    be.append_need(_make("FACT_req", NeedType.FACT))
    be.append_need(_make("DEC_a", NeedType.DEC, Link(type=LinkType.SATISFIES, target="FACT_req")))
    be.append_need(_make("RISK_r", NeedType.RISK, Link(type=LinkType.RELATES, target="DEC_a")))

    # Starting from FACT_req, depth 2 should find DEC_a (reverse satisfies) and RISK_r.
    result = CliRunner().invoke(
        cli, ["--workspace", str(tmp_path), "impact", "FACT_req", "--depth", "2"]
    )
    assert result.exit_code == 0, result.output
    assert "DEC_a" in result.output
    assert "RISK_r" in result.output


def test_impact_respects_link_type_filter(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    be.append_need(_make("FACT_req", NeedType.FACT))
    be.append_need(_make("DEC_a", NeedType.DEC, Link(type=LinkType.SATISFIES, target="FACT_req")))
    be.append_need(_make("MEM_o", NeedType.MEM, Link(type=LinkType.RELATES, target="FACT_req")))

    result = CliRunner().invoke(
        cli,
        ["--workspace", str(tmp_path), "impact", "FACT_req", "--depth", "1", "--link-type", "satisfies"],
    )
    assert result.exit_code == 0, result.output
    assert "DEC_a" in result.output
    assert "MEM_o" not in result.output


def test_impact_rejects_unknown_id(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    result = CliRunner().invoke(cli, ["--workspace", str(tmp_path), "impact", "DEC_ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_impact_marks_external_nodes_with_kind(tmp_path: Path) -> None:
    ws = tmp_path / "papyrus"
    pharaoh = tmp_path / "pharaoh"
    pharaoh.mkdir()
    (pharaoh / "needs.json").write_text(
        '{"versions": {"1.0": {"needs": '
        '{"REQ_x": {"id": "REQ_x", "type": "req", "title": "X", "links": [], "satisfies": []}}'
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
    be.append_need(_make("DEC_a", NeedType.DEC, Link(type=LinkType.SATISFIES, target="REQ_x")))

    result = CliRunner().invoke(
        cli, ["--config", str(tmp_path / "papyrus.toml"), "impact", "DEC_a", "--depth", "1"]
    )
    assert result.exit_code == 0, result.output
    assert "[external]" in result.output
    assert "REQ_x" in result.output


def test_impact_crosses_into_external_when_configured(tmp_path: Path) -> None:
    # Papyrus workspace + external pharaoh workspace side by side.
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
    be.append_need(_make("DEC_a", NeedType.DEC, Link(type=LinkType.SATISFIES, target="REQ_auth")))

    result = CliRunner().invoke(
        cli, ["--config", str(tmp_path / "papyrus.toml"), "impact", "DEC_a", "--depth", "1"]
    )
    assert result.exit_code == 0, result.output
    assert "DEC_a" in result.output
    assert "REQ_auth" in result.output
