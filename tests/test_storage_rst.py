"""Tests for RSTBackend (sphinx-needs RST files + filelock concurrency)."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timezone
from pathlib import Path

import pytest

from papyrus.models import Confidence, Link, LinkType, Need, NeedType, Scope, Status
from papyrus.storage.rst import RSTBackend


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    backend = RSTBackend(ws)
    backend.init_workspace(ws)
    return ws


def _need(nid: str, ntype: NeedType, **extra: object) -> Need:
    now = datetime.now(UTC)
    return Need(id=nid, type=ntype, title=nid.replace("_", " "), created_at=now, updated_at=now, **extra)  # type: ignore[arg-type]


def test_init_workspace_creates_expected_files(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    backend = RSTBackend(ws)
    backend.init_workspace(ws)
    assert (ws / "conf.py").is_file()
    assert (ws / "index.rst").is_file()
    for typ in ("observations", "decisions", "facts", "preferences", "risks", "goals", "questions"):
        assert (ws / "memory" / f"{typ}.rst").is_file()


def test_init_workspace_is_idempotent(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    backend = RSTBackend(ws)
    backend.init_workspace(ws)
    (ws / "memory" / "facts.rst").write_text("custom content")
    # Second init must not overwrite user content
    backend.init_workspace(ws)
    assert (ws / "memory" / "facts.rst").read_text() == "custom content"


def test_load_empty_workspace(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    assert backend.load_needs() == []


def test_append_and_reload_single_need(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    n = _need("FACT_hello", NeedType.FACT, body="hello world", tags=["topic:demo"])
    backend.append_need(n)
    loaded = backend.load_needs()
    assert len(loaded) == 1
    assert loaded[0].id == "FACT_hello"
    assert loaded[0].body == "hello world"
    assert "topic:demo" in loaded[0].tags


def test_append_duplicate_id_raises(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    n = _need("DEC_a", NeedType.DEC)
    backend.append_need(n)
    with pytest.raises(ValueError, match="already exists"):
        backend.append_need(n)


def test_append_preserves_links(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    a = _need("FACT_a", NeedType.FACT)
    b = _need(
        "DEC_b",
        NeedType.DEC,
        links=[Link(type=LinkType.RELATES, target="FACT_a")],
    )
    backend.append_need(a)
    backend.append_need(b)
    loaded = {n.id: n for n in backend.load_needs()}
    assert len(loaded["DEC_b"].links) == 1
    assert loaded["DEC_b"].links[0].target == "FACT_a"


def test_append_writes_to_type_specific_file(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    backend.append_need(_need("FACT_x", NeedType.FACT))
    backend.append_need(_need("DEC_y", NeedType.DEC))
    assert "FACT_x" in (workspace / "memory" / "facts.rst").read_text()
    assert "DEC_y" in (workspace / "memory" / "decisions.rst").read_text()
    assert "FACT_x" not in (workspace / "memory" / "decisions.rst").read_text()


def test_update_need_changes_body(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    backend.append_need(_need("FACT_a", NeedType.FACT, body="old"))
    updated = backend.update_need("FACT_a", body="new")
    assert updated.body == "new"
    reloaded = backend.find_by_id("FACT_a")
    assert reloaded is not None and reloaded.body == "new"


def test_update_need_refreshes_updated_at(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    backend.append_need(_need("DEC_a", NeedType.DEC))
    before = backend.find_by_id("DEC_a")
    assert before is not None
    updated = backend.update_need("DEC_a", status=Status.PROMOTED)
    assert updated.updated_at > before.updated_at


def test_update_need_unknown_id_raises(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    with pytest.raises(KeyError):
        backend.update_need("NONEXISTENT_id", body="x")


def test_update_need_rejects_immutable_fields(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    backend.append_need(_need("FACT_a", NeedType.FACT))
    with pytest.raises(ValueError, match="immutable"):
        backend.update_need("FACT_a", id="FACT_b")
    with pytest.raises(ValueError, match="immutable"):
        backend.update_need("FACT_a", type=NeedType.DEC)


def test_rebuild_index_emits_json(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    backend.append_need(_need("FACT_a", NeedType.FACT, body="hello"))
    backend.append_need(_need("DEC_b", NeedType.DEC))
    count = backend.rebuild_index()
    assert count == 2
    index_path = workspace / ".papyrus" / "index.json"
    assert index_path.is_file()
    data = json.loads(index_path.read_text())
    ids = {n["id"] for n in data["needs"]}
    assert ids == {"FACT_a", "DEC_b"}


def test_rebuild_index_empty_workspace(workspace: Path) -> None:
    backend = RSTBackend(workspace)
    count = backend.rebuild_index()
    assert count == 0
    index_path = workspace / ".papyrus" / "index.json"
    assert index_path.is_file()
    assert json.loads(index_path.read_text())["needs"] == []


def test_update_need_is_atomic_on_write_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulate crash during update: original file must be untouched."""
    backend = RSTBackend(tmp_path)
    backend.init_workspace(tmp_path)
    n = Need(
        id="DEC_orig",
        type=NeedType.DEC,
        title="Original",
        body="keep me",
        tags=[],
        confidence=Confidence.MEDIUM,
        scope=Scope.LOCAL,
        status=Status.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        review_after=None,
        source="",
        links=[],
    )
    backend.append_need(n)
    original_text = (tmp_path / "memory" / "decisions.rst").read_text()

    # Simulate crash during replace step
    replace_calls: list[tuple[Path, object]] = []
    def spy_replace(self: Path, target: object) -> None:
        replace_calls.append((self, target))
        raise OSError("simulated disk full")
    monkeypatch.setattr(Path, "replace", spy_replace)

    with pytest.raises(OSError):
        backend.update_need("DEC_orig", title="Updated")

    assert len(replace_calls) == 1, "atomic tmp+replace path was not taken"

    # Critical: original file must be intact
    assert (tmp_path / "memory" / "decisions.rst").read_text() == original_text
    reloaded = backend.find_by_id("DEC_orig")
    assert reloaded is not None
    assert reloaded.title == "Original"


def test_rebuild_index_also_runs_semantic_reindex_when_available(tmp_path, monkeypatch) -> None:
    from papyrus.storage.rst import RSTBackend
    from papyrus.models import NeedType
    from datetime import UTC, datetime

    backend = RSTBackend(tmp_path)
    backend.init_workspace(tmp_path)
    now = datetime.now(UTC)
    backend.append_need(Need(
        id="FACT_temp", type=NeedType.FACT, title="temperature", body="celsius",
        created_at=now, updated_at=now,
    ))

    calls: list[list[str]] = []

    class FakeIndex:
        def reindex(self, needs):
            calls.append([n.id for n in needs])
            return len(needs)

    def fake_factory(path):
        return FakeIndex()

    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: True)
    monkeypatch.setattr("papyrus.semantic.build_default_index", fake_factory)

    count = backend.rebuild_index()
    assert count == 1
    assert calls == [["FACT_temp"]]


def test_rebuild_index_skips_semantic_when_extra_missing(tmp_path, monkeypatch) -> None:
    from papyrus.storage.rst import RSTBackend

    backend = RSTBackend(tmp_path)
    backend.init_workspace(tmp_path)

    monkeypatch.setattr("papyrus.semantic.semantic_available", lambda: False)
    called = False

    def boom(_path):
        nonlocal called
        called = True
        raise AssertionError("factory should not be called when extra missing")

    monkeypatch.setattr("papyrus.semantic.build_default_index", boom)
    backend.rebuild_index()  # must not raise
    assert called is False
