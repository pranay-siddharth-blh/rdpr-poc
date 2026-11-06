"""
Integrity: the chatbot only ever READS the warehouse, the semantic layer and the example library, so their SHA-256
hashes must still equal the ones build_semantic_layer.py recorded in semantic/integrity_manifest.json.

A failure here means one of two things, both worth knowing: the app (or a stray script) wrote to a file it may only
read, or the warehouse / semantic layer was rebuilt and the manifest was not regenerated. Re-run
`python semantic/build_semantic_layer.py` after a legitimate rebuild.
"""
import hashlib
import json

import pytest

from app.config import PROJECT_ROOT, SEMANTIC_DIR

MANIFEST_PATH = SEMANTIC_DIR / "integrity_manifest.json"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def manifest():
    assert MANIFEST_PATH.exists(), f"{MANIFEST_PATH} is missing; run python semantic/build_semantic_layer.py"
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_covers_the_read_only_inputs(manifest):
    """The database, the semantic layer and the example library are all hashed."""
    covered = set(manifest["files"])
    assert "DB/rdpr_star.sqlite" in covered
    assert "semantic/semantic_layer.json" in covered
    assert "semantic/example_queries.sql" in covered


def test_inputs_are_unchanged(manifest):
    """Every hashed file still has the hash the build recorded."""
    changed = []
    for rel, expected in manifest["files"].items():
        path = PROJECT_ROOT / rel
        assert path.exists(), f"{rel} is in the manifest but missing from disk"
        actual = _sha256(path)
        if actual != expected:
            changed.append(f"{rel}\n    manifest: {expected}\n    on disk:  {actual}")
    assert not changed, ("These read-only inputs no longer match the manifest. Either something wrote to them, or they "
                         "were rebuilt without regenerating the manifest (python semantic/build_semantic_layer.py):\n  "
                         + "\n  ".join(changed))


def test_asking_a_question_does_not_change_the_database(ask, manifest):
    """The end-to-end check behind the claim: a full pipeline run leaves the warehouse byte-identical."""
    db_rel = "DB/rdpr_star.sqlite"
    before = _sha256(PROJECT_ROOT / db_rel)
    assert before == manifest["files"][db_rel]
    ask("How many GPs are there in Mysuru zilla?")
    assert _sha256(PROJECT_ROOT / db_rel) == before, "the database changed while answering a question"
