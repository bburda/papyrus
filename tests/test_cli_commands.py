"""Integration tests for CLI commands."""
from pathlib import Path

from click.testing import CliRunner

from papyrus.cli import cli


def test_init_creates_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    result = runner.invoke(cli, ["init", str(ws)])
    assert result.exit_code == 0, result.output
    assert (ws / "conf.py").is_file()
    assert (ws / "memory" / "facts.rst").is_file()


def test_init_idempotent(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    (ws / "memory" / "facts.rst").write_text("custom")
    result = runner.invoke(cli, ["init", str(ws)])
    assert result.exit_code == 0
    assert (ws / "memory" / "facts.rst").read_text() == "custom"


def test_add_creates_memory_in_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    result = runner.invoke(
        cli,
        [
            "--workspace", str(ws),
            "add", "fact", "Persistency uses Bazel",
            "--body", "Observed in MODULE.bazel files",
            "--tags", "topic:score,topic:bazel",
            "--confidence", "high",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "FACT_" in result.output  # id echoed back


def test_add_requires_initialized_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "empty"
    runner = CliRunner()
    result = runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "x"])
    assert result.exit_code != 0


def test_recall_lists_added_memories(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "Alpha"])
    runner.invoke(cli, ["--workspace", str(ws), "add", "dec", "Beta"])
    result = runner.invoke(cli, ["--workspace", str(ws), "recall"])
    assert result.exit_code == 0, result.output
    assert "FACT_" in result.output
    assert "DEC_" in result.output


def test_recall_filter_by_tag(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "A", "--tags", "topic:x"])
    runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "B", "--tags", "topic:y"])
    result = runner.invoke(cli, ["--workspace", str(ws), "recall", "--tag", "topic:x"])
    assert "FACT_a" in result.output
    assert "FACT_b" not in result.output


def test_recall_compact_format_shows_tags(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "Gamma", "--tags", "topic:visible"])
    result = runner.invoke(cli, ["--workspace", str(ws), "recall", "--format", "compact"])
    assert "topic:visible" in result.output


def test_get_existing_id(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "Alpha", "--body", "detail"])
    result = runner.invoke(cli, ["--workspace", str(ws), "get", "FACT_alpha"])
    assert result.exit_code == 0
    assert "Alpha" in result.output
    assert "detail" in result.output


def test_get_unknown_id_errors(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    result = runner.invoke(cli, ["--workspace", str(ws), "get", "NONE_x"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


def test_full_roundtrip_init_add_recall_get(tmp_path: Path) -> None:
    """Complete end-to-end exercise of init/add/recall/get."""
    ws = tmp_path / "ws"
    runner = CliRunner()

    # init
    r = runner.invoke(cli, ["init", str(ws)])
    assert r.exit_code == 0

    # add several memories
    for t, title, tags in [
        ("fact", "Score uses Bazel", "topic:arch"),
        ("dec", "Pick atomic-rollback for partial writes", "topic:persistency"),
        ("mem", "Logging filter impl uses exclusion lists", "topic:logging"),
    ]:
        r = runner.invoke(cli, ["--workspace", str(ws), "add", t, title, "--tags", tags])
        assert r.exit_code == 0, r.output

    # recall brief lists all 3
    r = runner.invoke(cli, ["--workspace", str(ws), "recall"])
    assert r.exit_code == 0
    assert all(pfx in r.output for pfx in ("FACT_", "DEC_", "MEM_"))

    # recall filter by tag narrows
    r = runner.invoke(cli, ["--workspace", str(ws), "recall", "--tag", "topic:logging"])
    assert "MEM_" in r.output
    assert "FACT_" not in r.output

    # get on a specific id
    r = runner.invoke(cli, ["--workspace", str(ws), "get", "DEC_pick_atomic_rollback_for_partial_writes"])
    assert r.exit_code == 0
    assert "atomic-rollback" in r.output.lower()


def test_cli_promote_moves_need(tmp_path: Path) -> None:
    runner = CliRunner()
    (tmp_path / "papyrus.toml").write_text(f"""
[papyrus]
preset = "custom"
default_write = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/local_ws"
scope = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/prog_ws"
scope = "program"

[papyrus.promote]
to_program_requires_confidence = "medium"
""")
    runner.invoke(cli, ["init", str(tmp_path / "local_ws")])
    runner.invoke(cli, ["init", str(tmp_path / "prog_ws")])
    runner.invoke(
        cli,
        ["--workspace", str(tmp_path / "local_ws"), "add", "fact", "Promotable", "--confidence", "high"],
    )
    result = runner.invoke(
        cli,
        ["--config", str(tmp_path / "papyrus.toml"), "promote", "FACT_promotable", "--to", "program"],
    )
    assert result.exit_code == 0, result.output
    assert "promoted" in result.output.lower()


def test_cli_promote_rejects_low_confidence(tmp_path: Path) -> None:
    runner = CliRunner()
    (tmp_path / "papyrus.toml").write_text(f"""
[papyrus]
preset = "custom"
default_write = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/local_ws"
scope = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/prog_ws"
scope = "program"

[papyrus.promote]
to_program_requires_confidence = "high"
""")
    runner.invoke(cli, ["init", str(tmp_path / "local_ws")])
    runner.invoke(cli, ["init", str(tmp_path / "prog_ws")])
    runner.invoke(
        cli,
        ["--workspace", str(tmp_path / "local_ws"), "add", "fact", "LowConf", "--confidence", "low"],
    )
    result = runner.invoke(
        cli,
        ["--config", str(tmp_path / "papyrus.toml"), "promote", "FACT_lowconf", "--to", "program"],
    )
    assert result.exit_code != 0
    assert "confidence" in result.output.lower()


def test_cli_recall_shows_scope_annotation_in_multi_workspace(tmp_path: Path) -> None:
    runner = CliRunner()
    (tmp_path / "papyrus.toml").write_text(f"""
[papyrus]
preset = "custom"
default_write = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/local_ws"
scope = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/prog_ws"
scope = "program"
""")
    runner.invoke(cli, ["init", str(tmp_path / "local_ws")])
    runner.invoke(cli, ["init", str(tmp_path / "prog_ws")])
    runner.invoke(cli, ["--workspace", str(tmp_path / "local_ws"), "add", "fact", "Local Thing"])
    runner.invoke(cli, ["--workspace", str(tmp_path / "prog_ws"), "add", "fact", "Prog Thing"])

    result = runner.invoke(cli, ["--config", str(tmp_path / "papyrus.toml"), "recall"])
    assert result.exit_code == 0
    assert "[from: local]" in result.output
    assert "[from: program]" in result.output


def test_multi_workspace_full_roundtrip_with_promote(tmp_path: Path) -> None:
    """init 2 workspaces -> add to local -> promote to program -> recall shows scopes -> get works."""
    runner = CliRunner()
    (tmp_path / "papyrus.toml").write_text(f"""
[papyrus]
preset = "custom"
default_write = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/local_ws"
scope = "local"

[[papyrus.workspaces]]
path = "{tmp_path}/prog_ws"
scope = "program"

[papyrus.promote]
to_program_requires_confidence = "medium"
""")
    cfg_args = ["--config", str(tmp_path / "papyrus.toml")]

    runner.invoke(cli, ["init", str(tmp_path / "local_ws")])
    runner.invoke(cli, ["init", str(tmp_path / "prog_ws")])

    for title, conf in [("Alpha", "high"), ("Beta", "medium")]:
        r = runner.invoke(
            cli,
            ["--workspace", str(tmp_path / "local_ws"), "add", "fact", title, "--confidence", conf],
        )
        assert r.exit_code == 0

    r = runner.invoke(cli, [*cfg_args, "recall"])
    assert "FACT_alpha" in r.output and "FACT_beta" in r.output
    assert r.output.count("[from: local]") == 2

    r = runner.invoke(cli, [*cfg_args, "promote", "FACT_alpha", "--to", "program"])
    assert r.exit_code == 0, r.output

    r = runner.invoke(cli, [*cfg_args, "recall"])
    lines = {ln for ln in r.output.splitlines() if ln.strip()}
    assert any("FACT_alpha" in ln and "[from: program]" in ln for ln in lines)
    assert any("FACT_beta" in ln and "[from: local]" in ln for ln in lines)

    r = runner.invoke(cli, [*cfg_args, "get", "FACT_alpha"])
    assert r.exit_code == 0
    assert "program" in r.output


def test_cli_mcp_serve_help() -> None:
    runner = CliRunner()
    result = runner.invoke(cli, ["mcp-serve", "--help"])
    assert result.exit_code == 0
    assert "mcp" in result.output.lower()


def test_add_duplicate_id_reports_cleanly(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    # First add succeeds
    r1 = runner.invoke(cli, ["--workspace", str(ws), "add", "dec", "Same Title"])
    assert r1.exit_code == 0
    # Second add with same auto-id should fail cleanly (no traceback)
    r2 = runner.invoke(cli, ["--workspace", str(ws), "add", "dec", "Same Title"])
    assert r2.exit_code != 0
    assert "already exists" in r2.output.lower()
    # No traceback artifacts
    assert "Traceback" not in r2.output
    assert "ValueError" not in r2.output


def test_recall_semantic_flag_without_extra_errors_cleanly(tmp_path: Path, monkeypatch) -> None:
    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])

    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: False)
    result = runner.invoke(
        cli,
        ["--workspace", str(ws), "recall", "--semantic", "-q", "temperature"],
    )
    assert result.exit_code != 0
    assert "papyrus[semantic]" in result.output


def test_recall_semantic_returns_related(tmp_path: Path, monkeypatch) -> None:
    from papyrus.semantic import FakeEncoder, SemanticIndex

    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    runner.invoke(
        cli,
        ["--workspace", str(ws), "add", "fact", "sensor celsius reading"],
    )
    runner.invoke(
        cli,
        ["--workspace", str(ws), "add", "dec", "use bcrypt password"],
    )

    encoder = FakeEncoder(
        axes=["thermal", "auth"],
        keyword_map={
            "thermal": ["temperature", "celsius", "hot"],
            "auth": ["password"],
        },
    )
    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    monkeypatch.setattr(
        "papyrus.semantic.build_default_index",
        lambda ws_path: SemanticIndex(ws_path / ".papyrus", encoder=encoder, model_name="fake"),
    )
    # rebuild-index now uses the monkeypatched FakeEncoder to persist vectors
    runner.invoke(cli, ["--workspace", str(ws), "rebuild-index"])

    result = runner.invoke(
        cli,
        ["--workspace", str(ws), "recall", "--semantic", "-q", "temperature", "--top-k", "2"],
    )
    assert result.exit_code == 0, result.output
    assert "sensor celsius reading" in result.output
    # The thermally-related need should rank above the password decision.
    assert result.output.index("sensor celsius") < result.output.index("password")


def test_recall_semantic_show_scores_prints_numbers(tmp_path: Path, monkeypatch) -> None:
    from papyrus.semantic import FakeEncoder, SemanticIndex

    ws = tmp_path / "ws"
    runner = CliRunner()
    runner.invoke(cli, ["init", str(ws)])
    runner.invoke(cli, ["--workspace", str(ws), "add", "fact", "about temperature"])

    encoder = FakeEncoder(axes=["x"], keyword_map={"x": ["temperature"]})
    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    monkeypatch.setattr(
        "papyrus.semantic.build_default_index",
        lambda ws_path: SemanticIndex(ws_path / ".papyrus", encoder=encoder, model_name="fake"),
    )
    # rebuild-index now uses the monkeypatched FakeEncoder to persist vectors
    runner.invoke(cli, ["--workspace", str(ws), "rebuild-index"])

    result = runner.invoke(
        cli,
        ["--workspace", str(ws), "recall", "--semantic", "-q", "temperature", "--show-scores"],
    )
    assert result.exit_code == 0, result.output
    first_line = result.output.strip().splitlines()[0]
    # brief format with scores: "<score>  <id>..." — first token parses as a float digit sequence.
    assert first_line.split()[0].replace(".", "").isdigit()
