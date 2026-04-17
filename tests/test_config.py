"""Tests for papyrus.toml config loading."""
from pathlib import Path

import pytest

from papyrus.config import (
    ConfigError,
    PapyrusConfig,
    Preset,
    WorkspaceSpec,
    load_config,
)
from papyrus.models import Confidence, Scope


def _write(path: Path, content: str) -> None:
    path.write_text(content)


def test_load_explicit_workspaces(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "custom"
default_write = "local"

[[papyrus.workspaces]]
path = ".papyrus"
scope = "local"

[[papyrus.workspaces]]
path = "../prog"
scope = "program"
""")
    cfg = load_config(tmp_path)
    assert cfg.preset == Preset.CUSTOM
    assert cfg.default_write == Scope.LOCAL
    assert [ws.scope for ws in cfg.workspaces] == [Scope.LOCAL, Scope.PROGRAM]
    assert [ws.path for ws in cfg.workspaces] == [".papyrus", "../prog"]


def test_preset_silos_expands_to_local_only(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "silos"
""")
    cfg = load_config(tmp_path)
    assert cfg.preset == Preset.SILOS
    assert [ws.scope for ws in cfg.workspaces] == [Scope.LOCAL]
    assert cfg.default_write == Scope.LOCAL


def test_preset_program_defaults(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "program"
""")
    cfg = load_config(tmp_path)
    assert {ws.scope for ws in cfg.workspaces} == {Scope.LOCAL, Scope.PROGRAM}
    assert cfg.default_write == Scope.LOCAL


def test_missing_toml_returns_default_single_workspace(tmp_path: Path) -> None:
    # No papyrus.toml in tmp_path — should fall back to a single local workspace at .
    cfg = load_config(tmp_path)
    assert cfg.preset == Preset.SILOS
    assert [ws.scope for ws in cfg.workspaces] == [Scope.LOCAL]
    assert cfg.workspaces[0].path == str(tmp_path)


def test_missing_toml_absolutizes_relative_workspace_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: when load_config is called with a relative path, the fallback
    # workspace spec must be stored as absolute so WorkspaceSpec.resolved_path(base)
    # doesn't later double-apply the base and produce e.g. "foo/foo".
    (tmp_path / "ws").mkdir()
    monkeypatch.chdir(tmp_path)

    cfg = load_config(Path("ws"))
    resolved = cfg.workspaces[0].resolved_path(Path("ws"))
    assert resolved == (tmp_path / "ws").resolve()


def test_forgetting_config_parsed(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "silos"

[papyrus.forgetting]
mem_review_days = 15
fact_review_days = 200
dec_never_expire = false
""")
    cfg = load_config(tmp_path)
    assert cfg.forgetting.mem_review_days == 15
    assert cfg.forgetting.fact_review_days == 200
    assert cfg.forgetting.dec_never_expire is False


def test_promote_config_parsed(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "silos"

[papyrus.promote]
to_program_requires_confidence = "high"
to_org_requires_human_review = true
""")
    cfg = load_config(tmp_path)
    assert cfg.promote.to_program_requires_confidence == Confidence.HIGH
    assert cfg.promote.to_org_requires_human_review is True


def test_invalid_scope_raises(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "custom"

[[papyrus.workspaces]]
path = "."
scope = "nonsense"
""")
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_default_write_must_match_existing_workspace(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "custom"
default_write = "org"

[[papyrus.workspaces]]
path = "."
scope = "local"
""")
    with pytest.raises(ConfigError, match="default_write"):
        load_config(tmp_path)


def test_workspace_paths_expanded(tmp_path: Path) -> None:
    _write(tmp_path / "papyrus.toml", """
[papyrus]
preset = "custom"

[[papyrus.workspaces]]
path = "~/papyrus-org"
scope = "org"
""")
    cfg = load_config(tmp_path)
    # Raw path preserved; expansion is consumer's responsibility but spec helper must be available.
    assert cfg.workspaces[0].path == "~/papyrus-org"
    expanded = cfg.workspaces[0].resolved_path(tmp_path)
    assert expanded.is_absolute()
    assert "~" not in str(expanded)


def test_config_without_external_has_none(tmp_path: Path) -> None:
    from papyrus.config import Preset
    from papyrus.models import Scope
    cfg = PapyrusConfig(
        preset=Preset.SILOS,
        default_write=Scope.LOCAL,
        workspaces=[WorkspaceSpec(path=".", scope=Scope.LOCAL)],
    )
    assert cfg.external is None


def test_config_with_external_resolves_paths(tmp_path: Path) -> None:
    from papyrus.config import load_config
    (tmp_path / "papyrus.toml").write_text(
        """
[papyrus]
preset = "silos"

[papyrus.external]
pharaoh_workspace = "pharaoh"
needs_json = "custom-needs.json"
"""
    )
    cfg = load_config(tmp_path)
    assert cfg.external is not None
    assert cfg.external.pharaoh_workspace == "pharaoh"
    assert cfg.external.needs_json == "custom-needs.json"
    resolved = cfg.external.resolved_needs_json(tmp_path)
    assert resolved == (tmp_path / "pharaoh" / "custom-needs.json").resolve()


def test_config_external_defaults_needs_json_filename(tmp_path: Path) -> None:
    from papyrus.config import load_config
    (tmp_path / "papyrus.toml").write_text(
        """
[papyrus]
preset = "silos"

[papyrus.external]
pharaoh_workspace = "../phar"
"""
    )
    cfg = load_config(tmp_path)
    assert cfg.external is not None
    assert cfg.external.needs_json == "needs.json"
