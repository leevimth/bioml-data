"""Immutable content-addressed artifact storage."""

from collections.abc import Iterable
from dataclasses import dataclass
from functools import partial
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, ClassVar

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

import bioml_data._artifact_paths as artifact_paths
from bioml_data._artifact_errors import (
    ArtifactCollisionError,
    ChecksumMismatchError,
    IncompleteDownloadError,
    OversizedDownloadError,
)
from bioml_data._artifact_paths import (
    ArtifactPathIntegrityError,
    ensure_no_symlink_components,
    open_binary_nofollow,
)
from bioml_data._artifact_types import (
    ArtifactId,
    ByteSize,
    NonEmptyText,
    Sha256Hex,
    SourceUri,
    TransformProtocolId,
)

__all__ = [
    "ArtifactCache",
    "ArtifactCollisionError",
    "ArtifactDerivation",
    "ArtifactId",
    "ArtifactManifest",
    "ArtifactReceipt",
    "ArtifactRequest",
    "ChecksumMismatchError",
    "IncompleteDownloadError",
    "OversizedDownloadError",
    "TransformProtocolId",
]


class ArtifactDerivation(BaseModel):
    """Versioned transform edge from one or more parent artifacts."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    parent_artifacts: Annotated[tuple[ArtifactId, ...], Field(min_length=1)]
    transform_protocol: TransformProtocolId


class _ArtifactProvenance(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    logical_name: NonEmptyText
    source_uri: SourceUri
    accession: NonEmptyText
    release: NonEmptyText
    retrieved_at: AwareDatetime
    tool_version: NonEmptyText
    derivation: ArtifactDerivation | None = None


class ArtifactRequest(_ArtifactProvenance):
    """Pinned expectations for one downloaded artifact stream."""

    expected_byte_size: ByteSize
    expected_sha256: Sha256Hex


class ArtifactManifest(_ArtifactProvenance):
    """Validated JSON provenance stored beside immutable content."""

    artifact_id: ArtifactId
    byte_size: ByteSize
    sha256: Sha256Hex


@dataclass(frozen=True, slots=True)
class ArtifactReceipt:
    """Resolved paths and manifest for a cached artifact."""

    manifest: ArtifactManifest
    content_path: Path
    manifest_path: Path

    @property
    def artifact_id(self) -> ArtifactId:
        """Return the content-derived artifact identity."""
        return self.manifest.artifact_id


@dataclass(frozen=True, slots=True)
class ArtifactCache:
    """Filesystem cache that atomically publishes verified artifact streams."""

    root: Path

    def lookup(self, request: ArtifactRequest) -> ArtifactReceipt | None:
        """Return a fully reverified cached receipt for an expected address."""
        artifact_id = ArtifactId(f"sha256:{request.expected_sha256}")
        directory = (
            self.root / "sha256" / request.expected_sha256[:2] / request.expected_sha256
        )
        try:
            ensure_no_symlink_components(directory)
        except ArtifactPathIntegrityError as error:
            raise ArtifactCollisionError(
                artifact_id=artifact_id,
                path=directory,
            ) from error
        if not directory.exists():
            return None
        return _verified_existing_receipt(directory, request)

    def store(
        self, request: ArtifactRequest, chunks: Iterable[bytes]
    ) -> ArtifactReceipt:
        """Verify and publish a byte stream under its SHA-256 address."""
        expected_id = ArtifactId(f"sha256:{request.expected_sha256}")
        try:
            ensure_no_symlink_components(self.root)
            self.root.mkdir(parents=True, exist_ok=True)
            ensure_no_symlink_components(self.root)
        except (ArtifactPathIntegrityError, OSError) as error:
            raise ArtifactCollisionError(
                artifact_id=expected_id,
                path=self.root,
            ) from error
        with TemporaryDirectory(prefix=".artifact-", dir=self.root) as temporary:
            staged_directory = Path(temporary)
            staged_content = staged_directory / "blob"
            digest_builder = sha256()
            byte_size = 0
            with staged_content.open("wb") as destination:
                for chunk in chunks:
                    next_byte_size = byte_size + len(chunk)
                    if next_byte_size > request.expected_byte_size:
                        raise OversizedDownloadError(
                            expected=request.expected_byte_size,
                            actual=next_byte_size,
                        )
                    _ = destination.write(chunk)
                    digest_builder.update(chunk)
                    byte_size = next_byte_size

            if byte_size != request.expected_byte_size:
                raise IncompleteDownloadError(
                    expected=request.expected_byte_size,
                    actual=byte_size,
                )

            digest = digest_builder.hexdigest()
            if digest != request.expected_sha256:
                raise ChecksumMismatchError(
                    expected=request.expected_sha256,
                    actual=digest,
                )

            artifact_id = ArtifactId(f"sha256:{digest}")
            manifest = ArtifactManifest(
                artifact_id=artifact_id,
                logical_name=request.logical_name,
                source_uri=request.source_uri,
                accession=request.accession,
                release=request.release,
                retrieved_at=request.retrieved_at,
                byte_size=byte_size,
                sha256=digest,
                tool_version=request.tool_version,
                derivation=request.derivation,
            )
            staged_manifest = staged_directory / "manifest.json"
            _ = staged_manifest.write_text(
                manifest.model_dump_json(indent=2),
                encoding="utf-8",
            )

            final_directory = self.root / "sha256" / digest[:2] / digest
            content_path = final_directory / "blob"
            manifest_path = final_directory / "manifest.json"
            try:
                final_directory.parent.mkdir(parents=True, exist_ok=True)
                ensure_no_symlink_components(final_directory.parent)
            except (ArtifactPathIntegrityError, OSError) as error:
                raise ArtifactCollisionError(
                    artifact_id=artifact_id,
                    path=final_directory.parent,
                ) from error

            if final_directory.exists():
                return _verified_existing_receipt(final_directory, request)

            try:
                artifact_paths.publish_directory_nofollow(
                    staged_directory,
                    final_directory,
                )
            except FileExistsError:
                return _verified_existing_receipt(final_directory, request)
            except ArtifactPathIntegrityError as error:
                raise ArtifactCollisionError(
                    artifact_id=artifact_id,
                    path=final_directory,
                ) from error
            return ArtifactReceipt(
                manifest=manifest,
                content_path=content_path,
                manifest_path=manifest_path,
            )


def _verified_existing_receipt(
    directory: Path,
    request: ArtifactRequest,
) -> ArtifactReceipt:
    digest = request.expected_sha256
    artifact_id = ArtifactId(f"sha256:{digest}")
    content_path = directory / "blob"
    manifest_path = directory / "manifest.json"
    existing_digest = sha256()
    byte_size = 0
    try:
        ensure_no_symlink_components(directory)
        with open_binary_nofollow(content_path) as existing_content:
            for block in iter(partial(existing_content.read, 1024 * 1024), b""):
                byte_size += len(block)
                existing_digest.update(block)
        with open_binary_nofollow(manifest_path) as existing_manifest_source:
            existing_manifest = ArtifactManifest.model_validate_json(
                existing_manifest_source.read().decode("utf-8"),
            )
    except (
        ArtifactPathIntegrityError,
        UnicodeDecodeError,
        ValidationError,
    ) as error:
        raise ArtifactCollisionError(artifact_id=artifact_id, path=directory) from error
    if (
        existing_digest.hexdigest() != digest
        or existing_manifest.artifact_id != artifact_id
        or existing_manifest.sha256 != digest
        or existing_manifest.byte_size != byte_size
        or byte_size != request.expected_byte_size
        or not _has_requested_provenance(existing_manifest, request)
    ):
        raise ArtifactCollisionError(artifact_id=artifact_id, path=directory)
    return ArtifactReceipt(
        manifest=existing_manifest,
        content_path=content_path,
        manifest_path=manifest_path,
    )


def _has_requested_provenance(
    manifest: ArtifactManifest,
    request: ArtifactRequest,
) -> bool:
    """Match the immutable source and transformation identity of a request.

    ``retrieved_at`` records when this cache entry was first acquired, while
    every request supplies a new current timestamp. ``tool_version`` records
    the acquiring client and does not make a verified upstream artifact stale
    after a package upgrade. The remaining fields identify its source or
    derivation and must remain exact for cache reuse.
    """
    return (
        manifest.logical_name == request.logical_name
        and manifest.source_uri == request.source_uri
        and manifest.accession == request.accession
        and manifest.release == request.release
        and manifest.derivation == request.derivation
    )
