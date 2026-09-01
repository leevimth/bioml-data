"""Content-addressed artifact cache contract tests."""

from collections.abc import Iterable
from datetime import UTC, datetime
from functools import partial
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data as bio
import bioml_data._artifact_paths as artifact_paths
import bioml_data._artifacts as artifacts


def _request(content: bytes, logical_name: str) -> artifacts.ArtifactRequest:
    return artifacts.ArtifactRequest(
        logical_name=logical_name,
        source_uri="https://example.test/public/fixture.bin",
        accession="TEST-001",
        release="v1",
        retrieved_at=datetime(2026, 8, 30, 12, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="bioml-data/0.0.0",
    )


def test_same_request_reuses_artifact_identity(tmp_path: Path) -> None:
    # Given: content already stored from a verified download stream.
    content = b"same biological payload"
    cache = artifacts.ArtifactCache(tmp_path / "cache")
    request = _request(content, "first.bin")
    first = cache.store(request, (content,))

    # When: the exact pinned object arrives again in differently sized chunks.
    second = cache.store(request, (content[:5], content[5:]))

    # Then: content identity and its deterministic cache location are reused.
    assert second.artifact_id == first.artifact_id
    assert second.content_path == first.content_path


def test_same_name_with_different_content_creates_distinct_artifacts(
    tmp_path: Path,
) -> None:
    # Given: one source filename has already been stored.
    cache = artifacts.ArtifactCache(tmp_path / "cache")
    first_content = b"first release"
    first = cache.store(_request(first_content, "matrix.h5ad"), (first_content,))
    second_content = b"corrected release"

    # When: different bytes arrive with the same filename.
    second = cache.store(_request(second_content, "matrix.h5ad"), (second_content,))

    # Then: the contents occupy separate immutable artifact identities.
    assert second.artifact_id != first.artifact_id
    assert second.content_path != first.content_path


def test_checksum_mismatch_never_registers_an_artifact(tmp_path: Path) -> None:
    # Given: a download request pinned to a checksum different from its bytes.
    content = b"unexpected bytes"
    cache_root = tmp_path / "cache"
    cache = artifacts.ArtifactCache(cache_root)
    request = _request(content, "fixture.bin").model_copy(
        update={"expected_sha256": "0" * 64},
    )

    # When: the stream is registered against the pinned checksum.
    with pytest.raises(artifacts.ChecksumMismatchError) as captured:
        _ = cache.store(request, (content,))

    # Then: the typed error reports both digests and no valid blob is published.
    assert captured.value.expected == "0" * 64
    assert captured.value.actual == sha256(content).hexdigest()
    assert tuple(cache_root.rglob("blob")) == ()


def test_incomplete_stream_never_registers_an_artifact(tmp_path: Path) -> None:
    # Given: a source advertises more bytes than the stream delivers.
    complete = b"complete payload"
    partial_content = complete[:-3]
    cache_root = tmp_path / "cache"
    cache = artifacts.ArtifactCache(cache_root)

    # When: registration reaches the end of the truncated stream.
    with pytest.raises(artifacts.IncompleteDownloadError) as captured:
        _ = cache.store(_request(complete, "fixture.bin"), (partial_content,))

    # Then: expected and received sizes are typed and no blob is published.
    assert captured.value.expected == len(complete)
    assert captured.value.actual == len(partial_content)
    assert tuple(cache_root.rglob("blob")) == ()


def test_oversize_stream_aborts_before_consuming_more_chunks(tmp_path: Path) -> None:
    # Given: a decoded stream whose first chunk already exceeds the pinned size.
    expected = b"abc"
    cache_root = tmp_path / "cache"
    consumed_later_chunk = False

    def oversize_chunks() -> Iterable[bytes]:
        nonlocal consumed_later_chunk
        yield b"abcd"
        consumed_later_chunk = True
        yield b"must-not-be-consumed"

    # When: the cache observes the oversize first chunk.
    with pytest.raises(bio.OversizedDownloadError) as captured:
        _ = artifacts.ArtifactCache(cache_root).store(
            _request(expected, "fixture.bin"),
            oversize_chunks(),
        )

    # Then: iteration stops immediately and no blob is published.
    assert captured.value.actual == 4
    assert not consumed_later_chunk
    assert tuple(cache_root.rglob("blob")) == ()


def test_manifest_json_round_trips(tmp_path: Path) -> None:
    # Given: a verified artifact manifest serialized at the filesystem boundary.
    content = b"manifest payload"
    receipt = artifacts.ArtifactCache(tmp_path / "cache").store(
        _request(content, "fixture.bin"),
        (content,),
    )
    payload = receipt.manifest.model_dump_json()

    # When: the JSON is parsed back into the frozen manifest model.
    parsed = artifacts.ArtifactManifest.model_validate_json(payload)

    # Then: provenance and identity survive the round trip exactly.
    assert parsed == receipt.manifest


def test_derived_artifact_links_parent_and_transform_protocol(tmp_path: Path) -> None:
    # Given: a verified parent and a versioned transformation identity.
    cache = artifacts.ArtifactCache(tmp_path / "cache")
    parent_content = b"raw matrix"
    parent = cache.store(_request(parent_content, "raw.h5ad"), (parent_content,))
    derivation = artifacts.ArtifactDerivation(
        parent_artifacts=(parent.artifact_id,),
        transform_protocol=artifacts.TransformProtocolId("canonical-single-cell-v1"),
        parameters=(
            artifacts.ArtifactDerivationParameter(
                name="expression_input",
                value="raw.X",
            ),
        ),
    )
    child_content = b"canonical matrix"
    request = _request(child_content, "canonical.parquet").model_copy(
        update={"derivation": derivation},
    )

    # When: the derived byte stream is stored.
    child = cache.store(request, (child_content,))

    # Then: its manifest links both the parent identity and transform protocol.
    assert child.manifest.derivation == derivation
    reopened = artifacts.ArtifactManifest.model_validate_json(
        child.manifest.model_dump_json(),
    )
    assert reopened.derivation is not None
    assert reopened.derivation.parameters == derivation.parameters


def test_legacy_derivation_without_parameters_remains_parseable() -> None:
    # Given: a pre-parameter derivation JSON receipt.
    payload = (
        '{"parent_artifacts":["sha256:'
        + "1" * 64
        + '"],"transform_protocol":"legacy-v1"}'
    )

    # When: the generic derivation boundary parses the legacy receipt.
    parsed = artifacts.ArtifactDerivation.model_validate_json(payload)

    # Then: compatibility is explicit through the immutable empty default.
    assert parsed.parameters == ()


def test_cache_refuses_to_overwrite_a_corrupted_blob(tmp_path: Path) -> None:
    # Given: an existing content-addressed blob was modified outside the cache API.
    content = b"immutable payload"
    cache = artifacts.ArtifactCache(tmp_path / "cache")
    receipt = cache.store(_request(content, "fixture.bin"), (content,))
    _ = receipt.content_path.write_bytes(b"tampered")

    # When: the original verified content is offered again.
    with pytest.raises(artifacts.ArtifactCollisionError):
        _ = cache.store(_request(content, "fixture.bin"), (content,))

    # Then: the cache reports the collision without overwriting the existing bytes.
    assert receipt.content_path.read_bytes() == b"tampered"


def test_same_digest_concurrent_publish_reopens_verified_winner(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: another writer publishes identical staged files just before rename.
    content = b"concurrent immutable payload"
    cache = artifacts.ArtifactCache(tmp_path / "cache")
    original_publish = artifact_paths.publish_directory_nofollow
    race_injected = False

    def publish_winner(source: Path, target: Path) -> None:
        nonlocal race_injected
        if source.name.startswith(".artifact-") and not race_injected:
            target.mkdir(parents=True)
            _ = (target / "blob").write_bytes((source / "blob").read_bytes())
            _ = (target / "manifest.json").write_bytes(
                (source / "manifest.json").read_bytes()
            )
            race_injected = True
            raise FileExistsError(target)
        original_publish(source, target)

    monkeypatch.setattr(
        artifact_paths,
        "publish_directory_nofollow",
        publish_winner,
    )

    # When: publication loses the atomic directory-rename race.
    receipt = cache.store(_request(content, "fixture.bin"), (content,))

    # Then: the verified winner is returned instead of leaking FileExistsError.
    assert race_injected
    assert receipt.content_path.read_bytes() == content
    assert receipt.artifact_id == f"sha256:{sha256(content).hexdigest()}"


def test_local_file_stream_is_stored_at_the_content_address(tmp_path: Path) -> None:
    # Given: a small local download fixture opened as a bounded byte stream.
    content = b"local fixture payload"
    source_path = tmp_path / "fixture.bin"
    _ = source_path.write_bytes(content)
    cache = artifacts.ArtifactCache(tmp_path / "cache")

    # When: the fixture is streamed into the artifact cache.
    with source_path.open("rb") as source:
        receipt = cache.store(
            _request(content, source_path.name),
            iter(partial(source.read, 4), b""),
        )

    # Then: the immutable blob path is derived only from its SHA-256 identity.
    digest = sha256(content).hexdigest()
    assert receipt.artifact_id == f"sha256:{digest}"
    assert receipt.content_path == (
        tmp_path / "cache" / "sha256" / digest[:2] / digest / "blob"
    )


def test_cache_lookup_reuses_a_fully_verified_artifact(tmp_path: Path) -> None:
    # Given: one artifact already published at its expected content address.
    content = b"cached immutable payload"
    cache = artifacts.ArtifactCache(tmp_path / "selected-data-directory")
    request = _request(content, "fixture.bin")
    stored = cache.store(request, (content,))

    # When: the expected request is resolved without another byte stream.
    resolved = cache.lookup(request)

    # Then: the same verified identity and paths are returned.
    assert resolved == stored


def test_cache_lookup_reuses_a_record_across_retrieval_times_and_tool_versions(
    tmp_path: Path,
) -> None:
    # Given: an artifact first acquired by an earlier package version.
    content = b"pinned source payload"
    cache = artifacts.ArtifactCache(tmp_path / "selected-data-directory")
    request = _request(content, "fixture.bin")
    stored = cache.store(request, (content,))
    later_request = request.model_copy(
        update={
            "retrieved_at": datetime(2026, 9, 1, 12, tzinfo=UTC),
            "tool_version": "bioml-data/0.1.0",
        },
    )

    # When: the same pinned upstream object is requested after an upgrade.
    resolved = cache.lookup(later_request)

    # Then: acquisition metadata does not invalidate the verified source cache.
    assert resolved == stored


def test_cache_lookup_returns_none_for_a_missing_address(tmp_path: Path) -> None:
    # Given: an empty caller-selected cache directory.
    content = b"not downloaded"
    cache = artifacts.ArtifactCache(tmp_path / "selected-data-directory")

    # When: the expected content address is queried.
    resolved = cache.lookup(_request(content, "fixture.bin"))

    # Then: absence is explicit and no cache directories are created.
    assert resolved is None
    assert not cache.root.exists()


def test_cache_lookup_rejects_corruption_without_overwriting(tmp_path: Path) -> None:
    # Given: a cached blob that was modified outside the cache boundary.
    content = b"original immutable payload"
    cache = artifacts.ArtifactCache(tmp_path / "selected-data-directory")
    request = _request(content, "fixture.bin")
    stored = cache.store(request, (content,))
    _ = stored.content_path.write_bytes(b"corrupt immutable payload")

    # When: lookup re-verifies the occupied address.
    with pytest.raises(artifacts.ArtifactCollisionError):
        _ = cache.lookup(request)

    # Then: the corrupt bytes remain untouched for explicit operator recovery.
    assert stored.content_path.read_bytes() == b"corrupt immutable payload"
