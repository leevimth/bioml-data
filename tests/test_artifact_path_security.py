"""Adversarial ancestor-symlink tests for artifact filesystem boundaries."""

import os
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

import bioml_data._artifact_paths as artifact_paths
from bioml_data._artifact_receipts import (
    ArtifactReceiptLoadError,
    load_artifact_receipt,
)
from bioml_data._artifacts import (
    ArtifactCache,
    ArtifactCollisionError,
    ArtifactRequest,
)


def _request(content: bytes) -> ArtifactRequest:
    return ArtifactRequest(
        logical_name="fixture.bin",
        source_uri="https://example.test/fixture.bin",
        accession="PATH-SECURITY",
        release="v1",
        retrieved_at=datetime(2026, 8, 30, tzinfo=UTC),
        expected_byte_size=len(content),
        expected_sha256=sha256(content).hexdigest(),
        tool_version="test",
    )


def _store(cache_root: Path, content: bytes) -> Path:
    return ArtifactCache(cache_root).store(_request(content), (content,)).manifest_path


def test_loader_rejects_symlinked_cache_root(tmp_path: Path) -> None:
    # Given: a valid cache reached through a symlink used as the cache root.
    content = b"root alias payload"
    real_root = tmp_path / "real-cache"
    manifest = _store(real_root, content)
    alias_root = tmp_path / "cache-alias"
    alias_root.symlink_to(real_root, target_is_directory=True)
    aliased_manifest = alias_root / manifest.relative_to(real_root)

    # When: the aliased receipt is loaded.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(aliased_manifest)

    # Then: the ancestor symlink fails closed.
    assert captured.value.reason.value == "symlink"


def test_loader_rejects_symlink_above_cache_root(tmp_path: Path) -> None:
    # Given: a canonical cache whose parent directory is reached through a symlink.
    content = b"ancestor alias payload"
    real_parent = tmp_path / "real-parent"
    real_root = real_parent / "cache"
    manifest = _store(real_root, content)
    alias_parent = tmp_path / "parent-alias"
    alias_parent.symlink_to(real_parent, target_is_directory=True)
    aliased_manifest = alias_parent / "cache" / manifest.relative_to(real_root)

    # When: the receipt is loaded through the aliased parent.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(aliased_manifest)

    # Then: the higher ancestor symlink fails closed.
    assert captured.value.reason.value == "symlink"


@pytest.mark.parametrize("link_index", [0, 1, 2])
def test_loader_rejects_symlinked_content_address_component(
    tmp_path: Path,
    link_index: int,
) -> None:
    # Given: sha256, prefix, or digest directory is a symlink into a valid cache.
    content = b"intermediate alias payload"
    real_root = tmp_path / "real-cache"
    manifest = _store(real_root, content)
    relative = manifest.relative_to(real_root)
    alias_root = tmp_path / "alias-cache"
    link_path = alias_root.joinpath(
        *relative.parts[:link_index], relative.parts[link_index]
    )
    link_path.parent.mkdir(parents=True, exist_ok=True)
    link_path.symlink_to(
        real_root.joinpath(*relative.parts[: link_index + 1]),
        target_is_directory=True,
    )
    aliased_manifest = alias_root / relative

    # When: the receipt is loaded through the aliased address component.
    with pytest.raises(ArtifactReceiptLoadError) as captured:
        _ = load_artifact_receipt(aliased_manifest)

    # Then: every intermediate symlink fails closed.
    assert captured.value.reason.value == "symlink"


def test_cache_rejects_symlinked_root_before_publication(tmp_path: Path) -> None:
    # Given: an empty real directory reached through a symlinked cache root.
    content = b"new publication"
    real_root = tmp_path / "real-cache"
    real_root.mkdir()
    alias_root = tmp_path / "cache-alias"
    alias_root.symlink_to(real_root, target_is_directory=True)

    # When: publication is attempted through the alias.
    with pytest.raises(ArtifactCollisionError):
        _ = ArtifactCache(alias_root).store(_request(content), (content,))

    # Then: no content address is created in the aliased target.
    assert tuple(real_root.rglob("blob")) == ()


def test_cache_rejects_existing_address_through_intermediate_symlink(
    tmp_path: Path,
) -> None:
    # Given: an existing valid address reached through a symlinked sha256 directory.
    content = b"existing payload"
    real_root = tmp_path / "real-cache"
    _ = _store(real_root, content)
    alias_root = tmp_path / "alias-cache"
    alias_root.mkdir()
    (alias_root / "sha256").symlink_to(
        real_root / "sha256",
        target_is_directory=True,
    )

    # When: the cache tries to reuse the existing digest through the alias.
    with pytest.raises(ArtifactCollisionError):
        _ = ArtifactCache(alias_root).store(_request(content), (content,))

    # Then: the symlinked existing address is never accepted as a cache hit.


def test_publication_rename_uses_pinned_parent_descriptors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an observer around the platform rename primitive.
    content = b"descriptor-pinned publication"
    original_rename = os.rename
    observed_descriptors: list[tuple[int | None, int | None]] = []

    def observe_rename(
        source: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        target: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        **directory_fds: int | None,
    ) -> None:
        src_dir_fd = directory_fds.get("src_dir_fd")
        dst_dir_fd = directory_fds.get("dst_dir_fd")
        observed_descriptors.append((src_dir_fd, dst_dir_fd))
        original_rename(
            source,
            target,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "rename", observe_rename)

    # When: the cache atomically publishes a new digest directory.
    _ = ArtifactCache(tmp_path / "cache").store(_request(content), (content,))

    # Then: both lookup roots are pinned instead of resolved by pathname at rename.
    assert observed_descriptors
    assert all(descriptor is not None for descriptor in observed_descriptors[-1])


def test_race_winner_digest_symlink_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a concurrent winner replaces the target digest directory with a symlink.
    content = b"race alias payload"
    cache = ArtifactCache(tmp_path / "cache")
    attacker = tmp_path / "attacker"
    original_publish = artifact_paths.publish_directory_nofollow
    race_injected = False

    def publish_symlink(source: Path, target: Path) -> None:
        nonlocal race_injected
        if source.name.startswith(".artifact-") and not race_injected:
            attacker.mkdir()
            _ = (attacker / "blob").write_bytes((source / "blob").read_bytes())
            _ = (attacker / "manifest.json").write_bytes(
                (source / "manifest.json").read_bytes()
            )
            target.symlink_to(attacker, target_is_directory=True)
            race_injected = True
            raise FileExistsError(target)
        original_publish(source, target)

    monkeypatch.setattr(
        artifact_paths,
        "publish_directory_nofollow",
        publish_symlink,
    )

    # When: the store verifies the apparent concurrent winner.
    with pytest.raises(ArtifactCollisionError):
        _ = cache.store(_request(content), (content,))

    # Then: the digest-directory symlink is rejected rather than reopened.
    assert race_injected
