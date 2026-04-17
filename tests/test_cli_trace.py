"""Tests for the `papyrus trace` CLI command."""
from datetime import UTC, datetime, timezone
from pathlib import Path

from click.testing import CliRunner

from papyrus.cli import cli
from papyrus.models import Link, LinkType, Need, NeedType
from papyrus.storage.rst import RSTBackend


def _make(nid: str, ntype: NeedType, *links: Link) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid, created_at=now, updated_at=now, links=list(links))


def test_trace_shows_direct_links(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    be.append_need(_make("FACT_req", NeedType.FACT))
    be.append_need(_make("DEC_a", NeedType.DEC, Link(type=LinkType.SATISFIES, target="FACT_req")))

    result = CliRunner().invoke(cli, ["--workspace", str(tmp_path), "trace", "DEC_a"])
    assert result.exit_code == 0, result.output
    assert "DEC_a" in result.output
    assert "satisfies" in result.output
    assert "FACT_req" in result.output


def test_trace_follows_supersedes_chain(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    be.append_need(_make("DEC_v1", NeedType.DEC))
    be.append_need(_make("DEC_v2", NeedType.DEC, Link(type=LinkType.SUPERSEDES, target="DEC_v1")))
    be.append_need(_make("DEC_v3", NeedType.DEC, Link(type=LinkType.SUPERSEDES, target="DEC_v2")))

    result = CliRunner().invoke(cli, ["--workspace", str(tmp_path), "trace", "DEC_v3"])
    assert result.exit_code == 0, result.output
    assert "DEC_v3" in result.output
    assert "DEC_v2" in result.output
    assert "DEC_v1" in result.output


def test_trace_rejects_unknown_id(tmp_path: Path) -> None:
    be = RSTBackend(tmp_path)
    be.init_workspace(tmp_path)
    result = CliRunner().invoke(cli, ["--workspace", str(tmp_path), "trace", "DEC_ghost"])
    assert result.exit_code != 0


def test_trace_surfaces_external_continuation(tmp_path: Path) -> None:
    """When a supersession link targets an external pharaoh id, trace must
    print a marker instead of silently ending the chain."""
    ws = tmp_path / "papyrus"
    pharaoh = tmp_path / "pharaoh"
    pharaoh.mkdir()
    (pharaoh / "needs.json").write_text(
        '{"versions": {"1.0": {"needs": '
        '{"REQ_ext_old": {"id": "REQ_ext_old", "type": "req", "title": "Old external req", "links": []}}'
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
    be.append_need(
        _make(
            "DEC_replacement_for_external",
            NeedType.DEC,
            Link(type=LinkType.SUPERSEDES, target="REQ_ext_old"),
        )
    )

    result = CliRunner().invoke(
        cli,
        [
            "--config",
            str(tmp_path / "papyrus.toml"),
            "trace",
            "DEC_replacement_for_external",
        ],
    )
    assert result.exit_code == 0, result.output
    # The external id must appear in the supersession chain section with an
    # explicit marker — not only in the direct-links section (which would
    # leave the chain silently truncated).
    assert "REQ_ext_old" in result.output
    assert "external" in result.output.lower()
    assert "continues" in result.output.lower() or "pharaoh" in result.output.lower()
