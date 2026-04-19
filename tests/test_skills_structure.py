"""Tests for atomic skills + shared docs + agent structure."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SKILLS_DIR = ROOT / "skills"
AGENTS_DIR = ROOT / "agents"
PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"

ATOMIC_SKILLS = [
    "papyrus-deprecate",
    "papyrus-detect-stale",
    "papyrus-drill",
    "papyrus-impact",
    "papyrus-init",
    "papyrus-link",
    "papyrus-promote",
    "papyrus-query",
    "papyrus-rebuild-index",
    "papyrus-trace",
    "papyrus-update-metadata",
    "papyrus-validate-links",
    "papyrus-write",
]

SHARED_DOCS = [
    "apply-memory.md",
    "impact-analysis.md",
    "link-types.md",
    "memory-types.md",
    "scopes-and-promote.md",
    "when-to-capture.md",
    "when-to-recall.md",
]

AGENTS = ["memory-curator"]

REQUIRED_SKILL_SECTIONS = [
    "## Atomicity",
    "## Input / Output",
    "## Success criterion",
    "## Workflow",
]


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_skill_has_skillmd(skill: str) -> None:
    path = SKILLS_DIR / skill / "SKILL.md"
    assert path.is_file(), f"missing {path}"
    assert path.stat().st_size > 500, f"{path} suspiciously short"


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_skill_has_frontmatter_with_name_and_description(skill: str) -> None:
    content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    assert content.startswith("---\n"), f"{skill} lacks YAML frontmatter"
    head = content[: content.find("\n---\n", 4) + 5]
    assert "name:" in head
    assert "description:" in head


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_skill_has_atomicity_sections(skill: str) -> None:
    content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    for section in REQUIRED_SKILL_SECTIONS:
        assert section in content, f"{skill} missing section '{section}'"


@pytest.mark.parametrize("skill", ATOMIC_SKILLS)
def test_skill_atomicity_section_covers_criteria(skill: str) -> None:
    """Each SKILL.md must mention all 5 criteria (a)-(e) in its Atomicity section."""
    content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
    atomicity_start = content.find("## Atomicity")
    next_section = content.find("\n## ", atomicity_start + 1)
    atomicity_block = content[atomicity_start:next_section]
    for letter in "abcde":
        assert f"({letter})" in atomicity_block, (
            f"{skill}/SKILL.md Atomicity section missing criterion ({letter})"
        )


@pytest.mark.parametrize("doc", SHARED_DOCS)
def test_shared_doc_exists(doc: str) -> None:
    path = SKILLS_DIR / "shared" / doc
    assert path.is_file(), f"missing {path}"
    assert path.stat().st_size > 300


@pytest.mark.parametrize("agent", AGENTS)
def test_agent_has_md(agent: str) -> None:
    path = AGENTS_DIR / agent / f"{agent}.md"
    assert path.is_file(), f"missing {path}"
    assert path.stat().st_size > 300


def test_plugin_json_valid() -> None:
    data = json.loads(PLUGIN_JSON.read_text())
    assert data["name"] == "papyrus"
    assert "version" in data


def test_skills_reference_real_cli_commands() -> None:
    """Every 'papyrus <subcmd>' mention must be a real CLI subcommand."""
    valid_subcommands = {
        "init", "add", "recall", "get", "promote",
        "mcp-serve", "verify", "query", "drill",
        "link", "impact", "trace", "rebuild-index",
        "--version", "--help", "--config", "--workspace",
    }
    # \b before "papyrus" ensures we don't match ".papyrus\n" (dot-prefixed paths).
    cmd_re = re.compile(r"(?<![./-])papyrus\s+(?:--\S+\s+\S+\s+)*([a-z][a-z-]*)\b")
    for skill in ATOMIC_SKILLS:
        content = (SKILLS_DIR / skill / "SKILL.md").read_text(encoding="utf-8")
        for match in cmd_re.finditer(content):
            cmd = match.group(1)
            if cmd.startswith("-") or cmd in {"toml", "config", "chain"}:
                continue
            assert cmd in valid_subcommands, (
                f"{skill}/SKILL.md references unknown subcommand: 'papyrus {cmd}'"
            )


def test_impact_analysis_shared_doc_exists():
    from pathlib import Path
    p = Path(__file__).parents[1] / "skills" / "shared" / "impact-analysis.md"
    assert p.is_file()
    content = p.read_text(encoding="utf-8")
    for keyword in ["papyrus impact", "papyrus trace", "papyrus link"]:
        assert keyword in content, f"impact-analysis.md missing {keyword!r}"


def test_papyrus_write_skill_mentions_linking():
    from pathlib import Path
    p = Path(__file__).parents[1] / "skills" / "papyrus-write" / "SKILL.md"
    assert p.is_file()
    content = p.read_text(encoding="utf-8")
    assert "link" in content.lower()
    assert "satisfies" in content.lower() or "requirement" in content.lower()
