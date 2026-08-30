"""Adversarial local artifact receipt loading tests."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from bioml_data._artifact_receipts import (
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import ArtifactCache, ArtifactManifest, ArtifactRequest


def _store(cache_root: Path, content: bytes = b"trusted artifact") -> Path:
    digest = sha256(content).hexdigest()
    receipt = ArtifactCache(cache_root).store(
        ArtifactRequest(
            logical_name="fixture.bin",
            source_uri="https://example.test/fixture.bin",
            accession="SECURITY-TEST",
            release="v1",
            retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
            expected_byte_size=len(content),
            expected_sha256=digest,
            tool_version="test",
        ),
        (content,),
    )
    return receipt.manifest_path


def test_valid_canonical_receipt_reopens_after_blob_verification(
    tmp_path: Path,
) -> None:
    # Given: a canonical cache entry produced by the artifact cache.
    manifest_path = _store(tmp_path / "cache")

    # When: the local receipt is reopened at the trust boundary.
    receipt = load_artifact_receipt(manifest_path)

    # Then: the verified sibling blob and manifest are returned.
    assert receipt.manifest_path == manifest_path
    assert receipt.content_path.read_bytes() == b"trusted artifact"


def test_tampered_blob_is_rejected(tmp_path: Path) -> None:
    # Given: a canonical receipt whose blob was modified after publication.
    manifest_path = _store(tmp_path / "cache")
    _ = (manifest_path.parent / "blob").write_bytes(b"tampered")

    # When: the receipt is reopened.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(manifest_path)

    # Then: content integrity fails closed.
    assert captured.value.reason.value == "content_integrity"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("byte_size", 999),
        ("artifact_id", "sha256:" + "f" * 64),
    ],
)
def test_forged_manifest_size_or_identity_is_rejected(
    tmp_path: Path,
    field: str,
    value: int | str,
) -> None:
    # Given: a canonical blob whose manifest fields were forged.
    manifest_path = _store(tmp_path / "cache")
    manifest = ArtifactManifest.model_validate_json(
        manifest_path.read_text(encoding="utf-8")
    )
    _ = manifest_path.write_text(
        manifest.model_copy(update={field: value}).model_dump_json(),
        encoding="utf-8",
    )

    # When: the forged receipt is reopened.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(manifest_path)

    # Then: manifest/content identity is rejected.
    assert captured.value.reason.value == "content_integrity"


def test_forged_manifest_hash_is_rejected_at_its_claimed_address(
    tmp_path: Path,
) -> None:
    # Given: a self-consistent claimed address whose blob has a different digest.
    source_manifest = _store(tmp_path / "source")
    manifest = ArtifactManifest.model_validate_json(
        source_manifest.read_text(encoding="utf-8")
    )
    forged_digest = "0" * 64
    target = (
        tmp_path
        / "cache"
        / "sha256"
        / forged_digest[:2]
        / forged_digest
        / "manifest.json"
    )
    target.parent.mkdir(parents=True)
    _ = target.write_text(
        manifest.model_copy(
            update={
                "artifact_id": f"sha256:{forged_digest}",
                "sha256": forged_digest,
            }
        ).model_dump_json(),
        encoding="utf-8",
    )
    _ = (target.parent / "blob").write_bytes(b"trusted artifact")

    # When: the forged receipt is reopened.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(target)

    # Then: the streamed digest comparison fails closed.
    assert captured.value.reason.value == "content_integrity"


def test_manifest_outside_canonical_cache_layout_is_rejected(tmp_path: Path) -> None:
    # Given: valid receipt files copied outside their content-addressed layout.
    source = _store(tmp_path / "source")
    target = tmp_path / "cache" / "wrong" / "manifest.json"
    target.parent.mkdir(parents=True)
    _ = target.write_bytes(source.read_bytes())
    _ = (target.parent / "blob").write_bytes((source.parent / "blob").read_bytes())

    # When: the non-canonical manifest path is loaded.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(target)

    # Then: layout validation rejects it.
    assert captured.value.reason.value == "invalid_layout"


def test_symlink_manifest_is_rejected(tmp_path: Path) -> None:
    # Given: a manifest path that aliases a valid cache entry.
    source = _store(tmp_path / "cache")
    link = tmp_path / "manifest-link.json"
    link.symlink_to(source)

    # When: the aliased manifest is loaded.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(link)

    # Then: the manifest symlink is rejected before parsing.
    assert captured.value.reason.value == "symlink"


def test_symlink_blob_is_rejected(tmp_path: Path) -> None:
    # Given: a canonical manifest whose sibling blob was replaced by a symlink.
    manifest_path = _store(tmp_path / "cache")
    blob_path = manifest_path.parent / "blob"
    external = tmp_path / "external.bin"
    _ = external.write_bytes(blob_path.read_bytes())
    blob_path.unlink()
    blob_path.symlink_to(external)

    # When: the receipt is reopened.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(manifest_path)

    # Then: the content symlink is rejected before streaming.
    assert captured.value.reason.value == "symlink"
