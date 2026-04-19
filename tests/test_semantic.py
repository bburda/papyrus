"""Tests for papyrus.semantic. FakeEncoder keeps tests dep-free."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from papyrus.models import Need, NeedType
from papyrus.semantic import (
    Encoder,
    FakeEncoder,
    SemanticIndex,
    VectorStore,
    content_hash,
    semantic_available,
)


def _need(nid: str, ntype: NeedType, **extra: object) -> Need:
    now = datetime.now(UTC)
    return Need(
        id=nid,
        type=ntype,
        title=nid.replace("_", " "),
        created_at=now,
        updated_at=now,
        **extra,  # type: ignore[arg-type]
    )


def test_content_hash_stable_for_same_inputs() -> None:
    n = _need("FACT_temp", NeedType.FACT, body="sensor reads celsius", tags=["topic:thermal"])
    assert content_hash(n) == content_hash(n)


def test_content_hash_changes_on_body_change() -> None:
    a = _need("FACT_temp", NeedType.FACT, body="sensor reads celsius")
    b = _need("FACT_temp", NeedType.FACT, body="sensor reads fahrenheit")
    assert content_hash(a) != content_hash(b)


def test_content_hash_independent_of_tag_order() -> None:
    a = _need("FACT_temp", NeedType.FACT, tags=["topic:a", "topic:b"])
    b = _need("FACT_temp", NeedType.FACT, tags=["topic:b", "topic:a"])
    assert content_hash(a) == content_hash(b)


def test_content_hash_handles_tags_with_commas() -> None:
    a = _need("FACT_temp", NeedType.FACT, tags=["a,b", "c"])
    b = _need("FACT_temp", NeedType.FACT, tags=["a", "b,c"])
    assert content_hash(a) != content_hash(b)


def test_content_hash_handles_newlines_in_title_and_body() -> None:
    """Newlines in title/body must not forge field boundaries (NUL delimiter enforces this)."""
    now = datetime.now(UTC)
    a = Need(id="FACT_x", type=NeedType.FACT, title="T\n", body="X", created_at=now, updated_at=now)
    b = Need(id="FACT_x", type=NeedType.FACT, title="T", body="\nX", created_at=now, updated_at=now)
    assert content_hash(a) != content_hash(b)


def test_vectorstore_survives_corrupt_npy_file(tmp_path) -> None:
    """Truncated/garbage vectors.npy must not crash VectorStore(); index resets silently."""
    base = tmp_path / ".papyrus"
    store = VectorStore(base, model="fake", dim=4)
    store.upsert([("FACT_a", np.array([1, 0, 0, 0], dtype=np.float32), "h1")])
    store.save()

    # Corrupt the binary file (truncate to a few bytes that aren't a valid npy header).
    (base / "vectors.npy").write_bytes(b"\x00\x01\x02\x03")

    reopened = VectorStore(base, model="fake", dim=4)
    assert reopened.ids() == []
    assert reopened.matrix().shape == (0, 4)


def test_vectorstore_empty_when_missing(tmp_path) -> None:
    store = VectorStore(tmp_path / ".papyrus", model="all-MiniLM-L6-v2", dim=4)
    assert store.ids() == []
    assert store.matrix().shape == (0, 4)


def test_vectorstore_roundtrip(tmp_path) -> None:
    store = VectorStore(tmp_path / ".papyrus", model="all-MiniLM-L6-v2", dim=4)
    v1 = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    store.upsert([("FACT_a", v1, "hash-a"), ("FACT_b", v2, "hash-b")])
    store.save()

    reopened = VectorStore(tmp_path / ".papyrus", model="all-MiniLM-L6-v2", dim=4)
    assert reopened.ids() == ["FACT_a", "FACT_b"]
    assert reopened.hash_of("FACT_a") == "hash-a"
    np.testing.assert_array_equal(reopened.matrix()[0], v1)


def test_vectorstore_upsert_replaces(tmp_path) -> None:
    store = VectorStore(tmp_path / ".papyrus", model="all-MiniLM-L6-v2", dim=4)
    store.upsert([("FACT_a", np.array([1, 0, 0, 0], dtype=np.float32), "h1")])
    store.upsert([("FACT_a", np.array([0, 1, 0, 0], dtype=np.float32), "h2")])
    assert store.ids() == ["FACT_a"]
    assert store.hash_of("FACT_a") == "h2"
    np.testing.assert_array_equal(store.matrix()[0], np.array([0, 1, 0, 0], dtype=np.float32))


def test_vectorstore_delete(tmp_path) -> None:
    store = VectorStore(tmp_path / ".papyrus", model="all-MiniLM-L6-v2", dim=4)
    store.upsert([
        ("FACT_a", np.array([1, 0, 0, 0], dtype=np.float32), "h1"),
        ("FACT_b", np.array([0, 1, 0, 0], dtype=np.float32), "h2"),
    ])
    store.delete(["FACT_a"])
    assert store.ids() == ["FACT_b"]
    assert store.matrix().shape == (1, 4)


def test_vectorstore_model_mismatch_clears_on_load(tmp_path) -> None:
    store = VectorStore(tmp_path / ".papyrus", model="model-v1", dim=4)
    store.upsert([("FACT_a", np.array([1, 0, 0, 0], dtype=np.float32), "h1")])
    store.save()

    reopened = VectorStore(tmp_path / ".papyrus", model="model-v2", dim=4)
    assert reopened.ids() == []


def test_fake_encoder_matches_keywords_deterministically() -> None:
    enc = FakeEncoder(
        axes=["thermal", "auth", "network"],
        keyword_map={"thermal": ["temperature", "celsius", "hot", "cold", "fahrenheit"],
                     "auth": ["password", "login", "credential"],
                     "network": ["tcp", "socket", "packet"]},
    )
    v1 = enc.encode(["sensor reads temperature in celsius"])[0]
    v2 = enc.encode(["user entered wrong password"])[0]
    assert v1.shape == (3,)
    # thermal axis dominates v1
    assert v1[0] > v1[1] and v1[0] > v1[2]
    # auth axis dominates v2
    assert v2[1] > v2[0] and v2[1] > v2[2]


def test_fake_encoder_is_l2_normalised() -> None:
    enc = FakeEncoder(axes=["a", "b"], keyword_map={"a": ["x"], "b": ["y"]})
    vecs = enc.encode(["x y", "x x"])
    norms = np.linalg.norm(vecs, axis=1)
    np.testing.assert_allclose(norms, 1.0, atol=1e-6)


def test_encoder_protocol_structural() -> None:
    enc: Encoder = FakeEncoder(axes=["a"], keyword_map={"a": ["x"]})
    assert enc.dim == 1
    out = enc.encode(["x"])
    assert out.shape == (1, 1)


def test_semantic_index_reindex_embeds_all(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    needs = [
        _need("FACT_temp", NeedType.FACT, body="sensor reads celsius and fahrenheit"),
        _need("DEC_auth", NeedType.DEC, body="use password hashing"),
    ]
    changed = idx.reindex(needs)
    assert changed == 2
    assert set(idx.store.ids()) == {"FACT_temp", "DEC_auth"}


def test_semantic_index_reindex_is_incremental(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    n1 = _need("FACT_temp", NeedType.FACT, body="celsius")
    n2 = _need("DEC_auth", NeedType.DEC, body="password")
    idx.reindex([n1, n2])
    # second call with unchanged needs: nothing re-embedded
    assert idx.reindex([n1, n2]) == 0


def test_semantic_index_reindex_reembeds_changed(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    n1 = _need("FACT_temp", NeedType.FACT, body="celsius")
    idx.reindex([n1])

    n1_mod = _need("FACT_temp", NeedType.FACT, body="fahrenheit and hot")
    assert idx.reindex([n1_mod]) == 1


def test_semantic_index_reindex_removes_orphans(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    n1 = _need("FACT_temp", NeedType.FACT, body="celsius")
    n2 = _need("DEC_auth", NeedType.DEC, body="password")
    idx.reindex([n1, n2])
    idx.reindex([n1])  # n2 gone
    assert idx.store.ids() == ["FACT_temp"]


def _thermal_encoder() -> FakeEncoder:
    return FakeEncoder(
        axes=["thermal", "auth", "other"],
        keyword_map={
            "thermal": ["temperature", "celsius", "fahrenheit", "hot", "cold", "thermal"],
            "auth": ["password", "login", "credential"],
            "other": ["foo", "bar"],
        },
    )


def test_semantic_search_returns_related_ids(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    idx.reindex([
        _need("FACT_temp", NeedType.FACT, body="sensor reads celsius and fahrenheit"),
        _need("DEC_auth", NeedType.DEC, body="use password hashing"),
        _need("RISK_hot", NeedType.RISK, body="enclosure gets hot in summer"),
    ])
    hits = idx.search("temperature", top_k=5)
    ids = [h.id for h in hits]
    # Both thermal-axis needs should rank before the auth need
    assert ids.index("FACT_temp") < ids.index("DEC_auth")
    assert ids.index("RISK_hot") < ids.index("DEC_auth")
    # Scores are in [0,1] descending
    assert all(0 <= h.score <= 1 for h in hits)
    assert hits == sorted(hits, key=lambda h: -h.score)


def test_semantic_search_respects_id_filter(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    idx.reindex([
        _need("FACT_temp", NeedType.FACT, body="celsius"),
        _need("DEC_auth", NeedType.DEC, body="password"),
    ])
    hits = idx.search("temperature", top_k=5, filter_ids={"DEC_auth"})
    assert [h.id for h in hits] == ["DEC_auth"]


def test_semantic_search_top_k(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    idx.reindex([
        _need("FACT_a", NeedType.FACT, body="celsius"),
        _need("FACT_b", NeedType.FACT, body="fahrenheit"),
        _need("FACT_c", NeedType.FACT, body="hot"),
    ])
    assert len(idx.search("temperature", top_k=2)) == 2


def test_semantic_search_empty_index_returns_empty(tmp_path) -> None:
    encoder = _thermal_encoder()
    idx = SemanticIndex(tmp_path / ".papyrus", encoder=encoder, model_name="fake")
    assert idx.search("anything") == []


def test_semantic_available_false_when_extra_missing(monkeypatch) -> None:
    # Simulate missing sentence_transformers
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert semantic_available() is False


def test_semantic_available_true_when_stubbed(monkeypatch) -> None:
    # Minimal stub: just importing sentence_transformers must succeed
    import sys
    import types
    stub = types.ModuleType("sentence_transformers")

    class _M:
        def __init__(self, *_: object, **__: object) -> None: ...
        def get_sentence_embedding_dimension(self) -> int: return 4
        def encode(self, *_: object, **__: object) -> object: ...

    stub.SentenceTransformer = _M  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", stub)
    assert semantic_available() is True
