"""papyrus.toml configuration loader.

Resolves per-project workspace chain: where memory lives (local, program, org),
forgetting policies, autocapture flags, promote gating rules.

Falls back to a safe default (single local workspace at cwd) when papyrus.toml
is absent — keeps single-workspace usage zero-config.
"""
from __future__ import annotations

import tomllib
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from papyrus.models import Confidence, Scope


class ConfigError(ValueError):
    """Raised on malformed or semantically-invalid papyrus.toml."""


class Preset(str, Enum):
    SILOS = "silos"
    PROGRAM = "program"
    OSS_FRIENDLY = "oss-friendly"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class WorkspaceSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    path: str = Field(min_length=1)
    scope: Scope

    def resolved_path(self, base: Path) -> Path:
        raw = self.path
        if raw.startswith("~"):
            return Path(raw).expanduser().resolve()
        p = Path(raw)
        if p.is_absolute():
            return p.resolve()
        return (base / p).resolve()


class ForgettingConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mem_review_days: int = 30
    fact_review_days: int = 180
    pref_review_days: int = 365
    dec_never_expire: bool = True


class AutocaptureConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    on_events: list[str] = Field(default_factory=list)
    min_confidence: Confidence = Confidence.MEDIUM


class PromoteConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    to_program_requires_confidence: Confidence = Confidence.HIGH
    to_org_requires_confidence: Confidence = Confidence.HIGH
    to_org_requires_human_review: bool = True


class ExternalWorkspaceSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    pharaoh_workspace: str = Field(min_length=1)
    needs_json: str = "needs.json"

    def resolved_needs_json(self, base: Path) -> Path:
        raw = self.pharaoh_workspace
        if raw.startswith("~"):
            root = Path(raw).expanduser()
        elif Path(raw).is_absolute():
            root = Path(raw)
        else:
            root = base / raw
        return (root / self.needs_json).resolve()


_PRESET_CHAINS: dict[Preset, list[WorkspaceSpec]] = {
    Preset.SILOS: [WorkspaceSpec(path=".papyrus", scope=Scope.LOCAL)],
    Preset.PROGRAM: [
        WorkspaceSpec(path=".papyrus", scope=Scope.LOCAL),
        WorkspaceSpec(path="../papyrus", scope=Scope.PROGRAM),
    ],
    Preset.OSS_FRIENDLY: [
        WorkspaceSpec(path="../papyrus", scope=Scope.PROGRAM),
    ],
    Preset.ENTERPRISE: [
        WorkspaceSpec(path=".papyrus", scope=Scope.LOCAL),
        WorkspaceSpec(path="../papyrus", scope=Scope.PROGRAM),
        WorkspaceSpec(path="~/useblocks-papyrus", scope=Scope.ORG),
    ],
}


class PapyrusConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    preset: Preset = Preset.SILOS
    default_write: Scope = Scope.LOCAL
    workspaces: list[WorkspaceSpec] = Field(default_factory=list)
    forgetting: ForgettingConfig = Field(default_factory=ForgettingConfig)
    autocapture: AutocaptureConfig = Field(default_factory=AutocaptureConfig)
    promote: PromoteConfig = Field(default_factory=PromoteConfig)
    external: ExternalWorkspaceSpec | None = None

    @field_validator("workspaces")
    @classmethod
    def _at_least_one_workspace(cls, v: list[WorkspaceSpec]) -> list[WorkspaceSpec]:
        if not v:
            raise ValueError("at least one workspace is required")
        return v

    @model_validator(mode="after")
    def _default_write_resolvable(self) -> PapyrusConfig:
        scopes = {ws.scope for ws in self.workspaces}
        if self.default_write not in scopes:
            raise ValueError(
                f"default_write={self.default_write.value!r} is not among configured workspaces {sorted(s.value for s in scopes)}"
            )
        return self


def _apply_preset(preset: Preset, explicit_workspaces: list[WorkspaceSpec]) -> list[WorkspaceSpec]:
    if preset == Preset.CUSTOM or explicit_workspaces:
        return explicit_workspaces
    return list(_PRESET_CHAINS[preset])


def load_config(path_or_dir: Path) -> PapyrusConfig:
    """Load papyrus.toml from a file path or directory containing one.

    When no papyrus.toml exists, returns a default config pointing at the dir
    with silos preset (single local workspace rooted there).
    """
    path = Path(path_or_dir)
    toml_path = path / "papyrus.toml" if path.is_dir() else path

    if not toml_path.is_file():
        default_root = path if path.is_dir() else path.parent
        # Store absolute so resolved_path(base) doesn't double-apply the base
        # when the caller passed a relative --workspace.
        return PapyrusConfig(
            preset=Preset.SILOS,
            default_write=Scope.LOCAL,
            workspaces=[WorkspaceSpec(path=str(default_root.resolve()), scope=Scope.LOCAL)],
        )

    try:
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f"invalid TOML in {toml_path}: {e}") from e

    papyrus_section = raw.get("papyrus", {}) or {}
    preset_str = papyrus_section.get("preset", "silos")
    raw_workspaces = papyrus_section.get("workspaces", []) or []

    try:
        preset = Preset(preset_str)
        explicit = [WorkspaceSpec(path=w["path"], scope=Scope(w["scope"])) for w in raw_workspaces]
    except (ValueError, KeyError) as e:
        raise ConfigError(f"invalid workspace entry in {toml_path}: {e}") from e

    workspaces = _apply_preset(preset, explicit)

    # default_write: use explicit value if provided, otherwise first workspace's scope
    if "default_write" in papyrus_section:
        try:
            default_write = Scope(papyrus_section["default_write"])
        except ValueError as e:
            raise ConfigError(f"invalid default_write in {toml_path}: {e}") from e
    else:
        default_write = workspaces[0].scope if workspaces else Scope.LOCAL

    try:
        return PapyrusConfig(
            preset=preset,
            default_write=default_write,
            workspaces=workspaces,
            forgetting=ForgettingConfig(**papyrus_section.get("forgetting", {})),
            autocapture=AutocaptureConfig(**papyrus_section.get("autocapture", {})),
            promote=PromoteConfig(**papyrus_section.get("promote", {})),
            external=(
                ExternalWorkspaceSpec(**papyrus_section["external"])
                if "external" in papyrus_section
                else None
            ),
        )
    except ValueError as e:
        raise ConfigError(str(e)) from e
